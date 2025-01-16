from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs.common import reports
from pcs.common.services.interfaces import ServiceManagerInterface
from pcs.lib import cluster_property as lib_cluster_property
from pcs.lib.cib.tools import IdProvider
from pcs.lib.resource_agent.facade import ResourceAgentFacade
from pcs.lib.resource_agent.types import (
    ResourceAgentMetadata,
    ResourceAgentParameter,
)
from pcs.lib.xml_tools import etree_to_str

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs_test.tools.custom_mock import get_runner_mock

TEMPLATE_CRM_CONFIG = """
<cib validate-with="pacemaker-3.8">
    <configuration>
        <crm_config>
            {property_sets}
        </crm_config>
    </configuration>
</cib>
"""

FIXTURE_TWO_PROPERTY_SETS = TEMPLATE_CRM_CONFIG.format(
    property_sets="""
        <cluster_property_set id="first">
            <nvpair id="first-have-watchdog" name="have-watchdog"
                value="false"/>
        </cluster_property_set>
        <cluster_property_set id="second">
            <nvpair id="second-maintenance-mode" name="maintenance-mode"
                value="false"/>
        </cluster_property_set>
    """
)


FIXTURE_NO_SET = TEMPLATE_CRM_CONFIG.format(property_sets="")

FORBIDDEN_OPTIONS_LIST = [
    "cluster-infrastructure",
    "cluster-name",
    "dc-version",
    "have-watchdog",
    "last-lrm-refresh",
]

PARAMETER_DEFINITIONS = [
    ("bool_param", "bool", "false", None),
    ("integer_param", "integer", "9", None),
    ("percentage_param", "percentage", "80%", None),
    ("select_param", "select", "s1", ["s1", "s2", "s3"]),
    ("time_param", "time", "30s", None),
    ("stonith-watchdog-timeout", "time", "0", None),
    ("cluster-infrastructure", "string", "corosync", None),
    ("cluster-name", "string", "(null)", None),
    ("dc-version", "string", "none", None),
    ("have-watchdog", "boolean", "false", None),
    ("duration_param", "duration", "P15S", None),
    ("nonnegative_param", "nonnegative_integer", "9", None),
    ("port_param", "port", "1234", None),
    ("score_param", "score", "INFINITY", None),
    ("timeout_param", "timeout", "60s", None),
]

ALLOWED_PROPERTIES = [
    "bool_param",
    "duration_param",
    "integer_param",
    "nonnegative_param",
    "percentage_param",
    "port_param",
    "score_param",
    "select_param",
    "stonith-watchdog-timeout",
    "time_param",
    "timeout_param",
]

FIXTURE_VALID_OPTIONS_DICT = {
    "bool_param": "true",
    "duration_param": "P1S",
    "integer_param": "10",
    "nonnegative_param": "9",
    "percentage_param": "20%",
    "port_param": "1234",
    "score_param": "-INFINITY",
    "select_param": "s3",
    "stonith-watchdog-timeout": "0",
    "time_param": "5min",
    "timeout_param": "5",
}

FIXTURE_INVALID_OPTIONS_DICT = {
    "bool_param": "Falsch",
    "duration_param": "Pxy",
    "integer_param": "3.14",
    "nonnegative_param": "-1",
    "percentage_param": "20",
    "port_param": "70000",
    "score_param": "xyz",
    "select_param": "not-in-enum-values",
    "time_param": "10x",
    "timeout_param": "P1S",
    "unknown": "value",
    "have-watchdog": "100",
}

STONITH_WATCHDOG_TIMEOUT_UNSET_VALUES = ["", "0", "0s"]


def _fixture_parameter(name, param_type, default, enum_values):
    return ResourceAgentParameter(
        name,
        shortdesc=None,
        longdesc=None,
        type=param_type,
        default=default,
        enum_values=enum_values,
        required=False,
        advanced=False,
        deprecated=False,
        deprecated_by=[],
        deprecated_desc=None,
        unique_group=None,
        reloadable=False,
    )


FIXTURE_PARAMETER_LIST = [
    _fixture_parameter(*parameter) for parameter in PARAMETER_DEFINITIONS
]


FIXTURE_ERROR_REPORTS = [
    fixture.error(
        reports.codes.INVALID_OPTIONS,
        force_code=reports.codes.FORCE,
        option_names=["unknown"],
        allowed=ALLOWED_PROPERTIES,
        option_type="cluster property",
        allowed_patterns=[],
    ),
    fixture.error(
        reports.codes.INVALID_OPTIONS,
        force_code=None,
        option_names=["have-watchdog"],
        allowed=ALLOWED_PROPERTIES,
        option_type="cluster property",
        allowed_patterns=[],
    ),
    fixture.error(
        reports.codes.INVALID_OPTION_VALUE,
        force_code=reports.codes.FORCE,
        option_name="duration_param",
        option_value="Pxy",
        allowed_values="time interval (e.g. 1, 2s, 3m, 4h, PT1H2M3S, ...)",
        cannot_be_empty=False,
        forbidden_characters=None,
    ),
    fixture.error(
        reports.codes.INVALID_OPTION_VALUE,
        force_code=reports.codes.FORCE,
        option_name="integer_param",
        option_value="3.14",
        allowed_values="an integer or INFINITY or -INFINITY",
        cannot_be_empty=False,
        forbidden_characters=None,
    ),
    fixture.error(
        reports.codes.INVALID_OPTION_VALUE,
        force_code=reports.codes.FORCE,
        option_name="nonnegative_param",
        option_value="-1",
        allowed_values="a positive integer or INFINITY",
        cannot_be_empty=False,
        forbidden_characters=None,
    ),
    fixture.error(
        reports.codes.INVALID_OPTION_VALUE,
        force_code=reports.codes.FORCE,
        option_name="percentage_param",
        option_value="20",
        allowed_values=(
            "a non-negative integer followed by '%' (e.g. 0%, 50%, 200%, ...)"
        ),
        cannot_be_empty=False,
        forbidden_characters=None,
    ),
    fixture.error(
        reports.codes.INVALID_OPTION_VALUE,
        force_code=reports.codes.FORCE,
        option_name="port_param",
        option_value="70000",
        allowed_values=("a port number (1..65535)"),
        cannot_be_empty=False,
        forbidden_characters=None,
    ),
    fixture.error(
        reports.codes.INVALID_OPTION_VALUE,
        force_code=reports.codes.FORCE,
        option_name="score_param",
        option_value="xyz",
        allowed_values="an integer or INFINITY or -INFINITY",
        cannot_be_empty=False,
        forbidden_characters=None,
    ),
    fixture.error(
        reports.codes.INVALID_OPTION_VALUE,
        force_code=reports.codes.FORCE,
        option_name="select_param",
        option_value="not-in-enum-values",
        allowed_values=["s1", "s2", "s3"],
        cannot_be_empty=False,
        forbidden_characters=None,
    ),
    fixture.error(
        reports.codes.INVALID_OPTION_VALUE,
        force_code=reports.codes.FORCE,
        option_name="time_param",
        option_value="10x",
        allowed_values="time interval (e.g. 1, 2s, 3m, 4h, PT1H2M3S, ...)",
        cannot_be_empty=False,
        forbidden_characters=None,
    ),
    fixture.error(
        reports.codes.INVALID_OPTION_VALUE,
        force_code=reports.codes.FORCE,
        option_name="timeout_param",
        option_value="P1S",
        allowed_values="time interval (e.g. 1, 2s, 3m, 4h, ...)",
        cannot_be_empty=False,
        forbidden_characters=None,
    ),
]


def warning_reports(report_list):
    warning_report_list = []
    for item_tuple in report_list:
        item_list = list(item_tuple)
        if item_list[3] is not None:
            item_list[0] = reports.ReportItemSeverity.WARNING
            item_list[3] = None
        warning_report_list.append(tuple(item_list))
    return warning_report_list


class TestValidateSetClusterProperties(TestCase):
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.mock_service_manager = mock.Mock(spec=ServiceManagerInterface)
        self.mock_facade_list = [
            mock.Mock(
                spec=ResourceAgentFacade,
                metadata=mock.Mock(
                    spec=ResourceAgentMetadata,
                    parameters=FIXTURE_PARAMETER_LIST[
                        0 : int(len(FIXTURE_PARAMETER_LIST) / 2)
                    ],
                ),
            ),
            mock.Mock(
                spec=ResourceAgentFacade,
                metadata=mock.Mock(
                    spec=ResourceAgentMetadata,
                    parameters=FIXTURE_PARAMETER_LIST[
                        int(len(FIXTURE_PARAMETER_LIST) / 2) :
                    ],
                ),
            ),
        ]
        self.patcher_is_sbd_enabled = mock.patch("pcs.lib.sbd.is_sbd_enabled")
        self.patcher_sbd_devices = mock.patch(
            "pcs.lib.sbd.get_local_sbd_device_list"
        )
        self.patcher_sbd_timeout = mock.patch(
            "pcs.lib.sbd._get_local_sbd_watchdog_timeout"
        )
        self.mock_is_sbd_enabled = self.patcher_is_sbd_enabled.start()
        self.mock_sbd_devices = self.patcher_sbd_devices.start()
        self.mock_sbd_timeout = self.patcher_sbd_timeout.start()

    def tearDown(self):
        self.patcher_is_sbd_enabled.stop()
        self.patcher_sbd_devices.stop()
        self.patcher_sbd_timeout.stop()

    def assert_validate_set(
        self,
        configured_properties,
        new_properties,
        expected_report_list,
        *,
        sbd_enabled=False,
        sbd_devices=False,
        force=False,
        valid_value=True,
        returncode=0,
    ):
        # pylint: disable=too-many-arguments
        self.mock_is_sbd_enabled.return_value = sbd_enabled
        self.mock_sbd_devices.return_value = ["devices"] if sbd_devices else []
        self.mock_sbd_timeout.return_value = 10
        assert_report_item_list_equal(
            lib_cluster_property.validate_set_cluster_properties(
                get_runner_mock(returncode=returncode),
                self.mock_facade_list,
                "property-set-id",
                configured_properties,
                new_properties,
                self.mock_service_manager,
                force=force,
            ),
            expected_report_list,
        )
        if (
            "stonith-watchdog-timeout" in new_properties
            and (
                new_properties["stonith-watchdog-timeout"]
                or "stonith-watchdog-timeout" in configured_properties
            )
            and valid_value
        ):
            self.mock_is_sbd_enabled.assert_called_once_with(
                self.mock_service_manager
            )
            if sbd_enabled:
                self.mock_sbd_devices.assert_called_once_with()
                if sbd_devices or (
                    new_properties["stonith-watchdog-timeout"]
                    in STONITH_WATCHDOG_TIMEOUT_UNSET_VALUES
                ):
                    self.mock_sbd_timeout.assert_not_called()
                else:
                    self.mock_sbd_timeout.assert_called_once_with()
                self.mock_sbd_devices.reset_mock()
            else:
                self.mock_sbd_devices.assert_not_called()
                self.mock_sbd_timeout.assert_not_called()
        else:
            self.mock_is_sbd_enabled.assert_not_called()
            self.mock_sbd_devices.assert_not_called()
            self.mock_sbd_timeout.assert_not_called()

        self.mock_is_sbd_enabled.reset_mock()
        self.mock_sbd_devices.reset_mock()
        self.mock_sbd_timeout.reset_mock()

    def test_no_properties_to_set_or_unset(self):
        self.assert_validate_set(
            [],
            {},
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_ITEMS_NOT_SPECIFIED,
                    force_code=reports.codes.FORCE,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_PROPERTY,
                    container_id="property-set-id",
                )
            ],
        )

    def test_no_properties_to_set_or_unset_forced(self):
        self.assert_validate_set(
            [],
            {},
            [
                fixture.warn(
                    reports.codes.ADD_REMOVE_ITEMS_NOT_SPECIFIED,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_PROPERTY,
                    container_id="property-set-id",
                )
            ],
            force=True,
        )

    def test_set_valid_properties_and_values(self):
        self.assert_validate_set([], FIXTURE_VALID_OPTIONS_DICT, [])

    def test_set_invalid_properties_and_values(self):
        self.assert_validate_set(
            [],
            FIXTURE_INVALID_OPTIONS_DICT,
            FIXTURE_ERROR_REPORTS,
            returncode=1,
        )

    def test_set_invalid_properties_and_values_forced(self):
        self.assert_validate_set(
            [],
            FIXTURE_INVALID_OPTIONS_DICT,
            warning_reports(FIXTURE_ERROR_REPORTS),
            force=True,
            returncode=1,
        )

    def test_unset_stonith_watchdog_timeout_sbd_disabled(self):
        for value in STONITH_WATCHDOG_TIMEOUT_UNSET_VALUES:
            with self.subTest(value=value):
                self.assert_validate_set(
                    ["stonith-watchdog-timeout"],
                    {"stonith-watchdog-timeout": value},
                    [],
                )

    def test_set_stonith_watchdog_timeout_sbd_disabled(self):
        self.assert_validate_set(
            [],
            {"stonith-watchdog-timeout": "5"},
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET,
                    reason="sbd_not_set_up",
                )
            ],
        )

    def test_set_ok_stonith_watchdog_timeout_sbd_enabled_without_devices(self):
        for value in ["15", "15s"]:
            with self.subTest(value=value):
                self.assert_validate_set(
                    [],
                    {"stonith-watchdog-timeout": value},
                    [],
                    sbd_enabled=True,
                )

    def test_set_small_stonith_watchdog_timeout_sbd_enabled_without_devices(
        self,
    ):
        self.assert_validate_set(
            [],
            {"stonith-watchdog-timeout": "9s"},
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_TOO_SMALL,
                    force_code=reports.codes.FORCE,
                    cluster_sbd_watchdog_timeout=10,
                    entered_watchdog_timeout="9s",
                )
            ],
            sbd_enabled=True,
        )

    def test_set_small_stonith_watchdog_timeout_sbd_enabled_without_devices_forced(
        self,
    ):
        self.assert_validate_set(
            [],
            {"stonith-watchdog-timeout": "9"},
            [
                fixture.warn(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_TOO_SMALL,
                    cluster_sbd_watchdog_timeout=10,
                    entered_watchdog_timeout="9",
                )
            ],
            sbd_enabled=True,
            force=True,
        )

    def _set_invalid_value_stonith_watchdog_timeout(
        self, sbd_enabled=False, sbd_devices=False
    ):
        for value in ["invalid", "10x"]:
            with self.subTest(value=value):
                self.assert_validate_set(
                    [],
                    {"stonith-watchdog-timeout": value},
                    [
                        fixture.error(
                            reports.codes.INVALID_OPTION_VALUE,
                            option_name="stonith-watchdog-timeout",
                            option_value=value,
                            allowed_values="time interval (e.g. 1, 2s, 3m, 4h, ...)",
                            cannot_be_empty=False,
                            forbidden_characters=None,
                        )
                    ],
                    sbd_enabled=sbd_enabled,
                    sbd_devices=sbd_devices,
                    valid_value=False,
                )

    def test_set_invalid_value_stonith_watchdog_timeout_sbd_enabled_without_devices(
        self,
    ):
        self._set_invalid_value_stonith_watchdog_timeout(
            sbd_enabled=True, sbd_devices=False
        )

    def test_set_invalid_value_stonith_watchdog_timeout_sbd_enabled_with_devices(
        self,
    ):
        self._set_invalid_value_stonith_watchdog_timeout(
            sbd_enabled=True, sbd_devices=True
        )

    def test_set_invalid_value_stonith_watchdog_timeout_sbd_disabled(
        self,
    ):
        self._set_invalid_value_stonith_watchdog_timeout(
            sbd_enabled=False, sbd_devices=False
        )

    def test_unset_stonith_watchdog_timeout_sbd_enabled_without_devices(
        self,
    ):
        for value in STONITH_WATCHDOG_TIMEOUT_UNSET_VALUES:
            with self.subTest(value=value):
                self.assert_validate_set(
                    ["stonith-watchdog-timeout"],
                    {"stonith-watchdog-timeout": value},
                    [
                        fixture.error(
                            reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET,
                            force_code=reports.codes.FORCE,
                            reason="sbd_set_up_without_devices",
                        )
                    ],
                    sbd_enabled=True,
                )

    def test_unset_stonith_watchdog_timeout_sbd_enabled_without_devices_forced(
        self,
    ):
        for value in STONITH_WATCHDOG_TIMEOUT_UNSET_VALUES:
            with self.subTest(value=value):
                self.assert_validate_set(
                    ["stonith-watchdog-timeout"],
                    {"stonith-watchdog-timeout": value},
                    [
                        fixture.warn(
                            reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET,
                            reason="sbd_set_up_without_devices",
                        )
                    ],
                    force=True,
                    sbd_enabled=True,
                )

    def test_set_stonith_watchdog_timeout_sbd_enabled_with_devices(self):
        self.assert_validate_set(
            [],
            {"stonith-watchdog-timeout": "15"},
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET,
                    force_code=reports.codes.FORCE,
                    reason="sbd_set_up_with_devices",
                )
            ],
            sbd_enabled=True,
            sbd_devices=True,
        )

    def test_set_stonith_watchdog_timeout_sbd_enabled_with_devices_forced(self):
        self.assert_validate_set(
            [],
            {"stonith-watchdog-timeout": "15s"},
            [
                fixture.warn(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET,
                    reason="sbd_set_up_with_devices",
                )
            ],
            sbd_enabled=True,
            sbd_devices=True,
            force=True,
        )

    def test_unset_stonith_watchdog_timeout_sbd_enabled_with_devices(self):
        for value in STONITH_WATCHDOG_TIMEOUT_UNSET_VALUES:
            with self.subTest(value=value):
                self.assert_validate_set(
                    ["stonith-watchdog-timeout"],
                    {"stonith-watchdog-timeout": value},
                    [],
                    sbd_enabled=True,
                    sbd_devices=True,
                )

    def test_remove_not_configured_stonith_watchdog_timeout(self):
        self.assert_validate_set(
            ["a", "b"],
            {"stonith-watchdog-timeout": ""},
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_CANNOT_REMOVE_ITEMS_NOT_IN_THE_CONTAINER,
                    force_code=reports.codes.FORCE,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_PROPERTY,
                    container_id="property-set-id",
                    item_list=["stonith-watchdog-timeout"],
                )
            ],
        )

    def test_remove_valid_configured_options(self):
        self.assert_validate_set(
            ["bool_param", "integer_param", "percentage_param", "a", "b", "c"],
            {"bool_param": "", "integer_param": ""},
            [],
        )

    def test_remove_valid_not_configured_options(self):
        self.assert_validate_set(
            [],
            {"bool_param": "", "integer_param": ""},
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_CANNOT_REMOVE_ITEMS_NOT_IN_THE_CONTAINER,
                    force_code=reports.codes.FORCE,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_PROPERTY,
                    container_id="property-set-id",
                    item_list=["bool_param", "integer_param"],
                )
            ],
        )

    def test_remove_valid_not_configured_options_forced(self):
        self.assert_validate_set(
            [],
            {"bool_param": "", "integer_param": ""},
            [
                fixture.warn(
                    reports.codes.ADD_REMOVE_CANNOT_REMOVE_ITEMS_NOT_IN_THE_CONTAINER,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_PROPERTY,
                    container_id="property-set-id",
                    item_list=["bool_param", "integer_param"],
                )
            ],
            force=True,
        )

    def test_remove_invalid_configured_options(self):
        self.assert_validate_set(
            ["bool_param", "integer_param", "percentage_param", "a", "b", "c"],
            {"a": "", "b": ""},
            [],
        )

    def test_remove_invalid_configured_options_forced(self):
        self.assert_validate_set(
            ["bool_param", "integer_param", "percentage_param", "a", "b", "c"],
            {"a": "", "b": ""},
            [],
            force=True,
        )

    def test_remove_invalid_not_configured_options(self):
        self.assert_validate_set(
            ["a", "b", "c"],
            {"x": "", "y": ""},
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_CANNOT_REMOVE_ITEMS_NOT_IN_THE_CONTAINER,
                    force_code=reports.codes.FORCE,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_PROPERTY,
                    container_id="property-set-id",
                    item_list=["x", "y"],
                ),
            ],
        )

    def test_remove_invalid_not_configured_options_forced(self):
        self.assert_validate_set(
            ["a", "b", "c"],
            {"x": "", "y": ""},
            [
                fixture.warn(
                    reports.codes.ADD_REMOVE_CANNOT_REMOVE_ITEMS_NOT_IN_THE_CONTAINER,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_PROPERTY,
                    container_id="property-set-id",
                    item_list=["x", "y"],
                ),
            ],
            force=True,
        )

    def test_remove_forbidden_options(self):
        self.assert_validate_set(
            FORBIDDEN_OPTIONS_LIST,
            {key: "" for key in FORBIDDEN_OPTIONS_LIST},
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=FORBIDDEN_OPTIONS_LIST,
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                )
            ],
        )

    def test_remove_forbidden_options_forced(self):
        self.assert_validate_set(
            FORBIDDEN_OPTIONS_LIST,
            {key: "" for key in FORBIDDEN_OPTIONS_LIST},
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=FORBIDDEN_OPTIONS_LIST,
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                )
            ],
            force=True,
        )


class TestGetClusterPropertySetElementLegacy(TestCase):
    def test_return_first_set(self):
        # pylint: disable=no-self-use
        cib = etree.fromstring(FIXTURE_TWO_PROPERTY_SETS)
        id_provider = IdProvider(cib)
        set_element = (
            lib_cluster_property.get_cluster_property_set_element_legacy(
                cib, id_provider
            )
        )
        assert_xml_equal(
            etree_to_str(cib.xpath('.//*[@id="first"]')[0]),
            etree_to_str(set_element),
        )

    def test_no_set_create_cib_bootstrap_options_set(self):
        # pylint: disable=no-self-use
        cib = etree.fromstring(FIXTURE_NO_SET)
        id_provider = IdProvider(cib)
        set_element = (
            lib_cluster_property.get_cluster_property_set_element_legacy(
                cib, id_provider
            )
        )
        assert_xml_equal(
            '<cluster_property_set id="cib-bootstrap-options"/>',
            etree_to_str(set_element),
        )
