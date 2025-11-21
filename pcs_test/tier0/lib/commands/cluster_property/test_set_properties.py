from unittest import TestCase, mock

from pcs import settings
from pcs.common import reports
from pcs.lib.commands import cluster_property

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc

from .crm_attribute_mixins import (
    CrmAttributeLoadMetadataMixin,
    CrmAttributeMetadataErrorMixin,
)
from .fixtures import fixture_crm_config_properties

ALLOWED_PROPERTIES = [
    "batch-limit",
    "cluster-delay",
    "cluster-ipc-limit",
    "cluster-recheck-interval",
    "concurrent-fencing",
    "dc-deadtime",
    "election-timeout",
    "enable-acl",
    "enable-startup-probes",
    "fence-reaction",
    "fencing-enabled",
    "join-finalization-timeout",
    "join-integration-timeout",
    "load-threshold",
    "maintenance-mode",
    "migration-limit",
    "no-quorum-policy",
    "node-action-limit",
    "node-health-base",
    "node-health-green",
    "node-health-red",
    "node-health-strategy",
    "node-health-yellow",
    "node-pending-timeout",
    "pe-error-series-max",
    "pe-input-series-max",
    "pe-warn-series-max",
    "placement-strategy",
    "priority-fencing-delay",
    "remove-after-stop",
    "shutdown-escalation",
    "shutdown-lock",
    "shutdown-lock-limit",
    "start-failure-is-fatal",
    "startup-fencing",
    "stonith-action",
    "stonith-enabled",
    "stonith-max-attempts",
    "stonith-timeout",
    "stonith-watchdog-timeout",
    "stop-all-resources",
    "stop-orphan-actions",
    "stop-orphan-resources",
    "symmetric-cluster",
    "transition-delay",
]


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestPropertySetCrmAttribute(
    CrmAttributeLoadMetadataMixin,
    CrmAttributeMetadataErrorMixin,
    TestCase,
):
    _load_cib_when_metadata_error = True

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def command(self, prop_dict, force_codes=None):
        cluster_property.set_properties(
            self.env_assist.get_env(),
            prop_dict,
            [] if force_codes is None else force_codes,
        )

    def metadata_error_command(self):
        return self.command({}, [])

    def test_no_properties_specified(self):
        self.config.runner.cib.load()
        self.load_fake_agent_metadata()
        self.env_assist.assert_raise_library_error(lambda: self.command({}))
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_ITEMS_NOT_SPECIFIED,
                    force_code=reports.codes.FORCE,
                    container_type="property_set",
                    item_type="property",
                    container_id="cib-bootstrap-options",
                )
            ]
        )

    def test_no_properties_specified_forced(self):
        self.config.runner.cib.load()
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {})]
            )
        )

        self.command({}, [reports.codes.FORCE])
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.ADD_REMOVE_ITEMS_NOT_SPECIFIED,
                    container_type="property_set",
                    item_type="property",
                    container_id="cib-bootstrap-options",
                )
            ]
        )

    def test_no_sets_and_cib_bootstrap_options_id_taken(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive class="ocf" id="cib-bootstrap-options"
                        provider="pacemaker" type="Dummy"/>
                </resources>
            """
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.command({"no-quorum-policy": "freeze"}),
            reports=[
                fixture.error(
                    reports.codes.CANNOT_CREATE_DEFAULT_CLUSTER_PROPERTY_SET,
                    nvset_id="cib-bootstrap-options",
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports([])

    def test_create_cib_bootstrap_options(self):
        self.config.runner.cib.load()
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"maintenance-mode": "false"})]
            )
        )

        cluster_property.set_properties(
            self.env_assist.get_env(),
            {"maintenance-mode": "false"},
            [],
        )
        self.env_assist.assert_reports([])

    def _readonly_properties(self, force):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    (
                        "cib-bootstrap-options",
                        {
                            "cluster-infrastructure": "corosync",
                            "cluster-name": "ClusterName",
                            "dc-version": "2.1.4-5.el9-dc6eb4362e",
                        },
                    )
                ]
            )
        )
        self.load_fake_agent_metadata()
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {
                    "cluster-name": "HACluster",
                    "dc-version": "",
                    "have-watchdog": "yes",
                },
                [reports.codes.FORCE] if force else [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=[
                        "cluster-name",
                        "dc-version",
                        "have-watchdog",
                    ],
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                )
            ]
        )

    def test_readonly_properties(self):
        self._readonly_properties(False)

    def test_readonly_properties_forced(self):
        self._readonly_properties(True)

    def test_success(self):
        orig_properties = {
            "batch-limit": "10",
            "enable-acl": "true",
            "stonith-enabled": "true",
        }
        new_properties = {
            "enable-acl": "false",
            "stonith-enabled": "true",
            "maintenance-mode": "false",
        }

        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    ("first-set", orig_properties),
                    ("second-set", orig_properties),
                ]
            )
        )
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [
                    ("first-set", new_properties),
                    ("second-set", orig_properties),
                ]
            )
        )

        cluster_property.set_properties(
            self.env_assist.get_env(),
            {
                "batch-limit": "",
                "enable-acl": "false",
                "maintenance-mode": "false",
            },
            [],
        )
        self.env_assist.assert_reports([])

    def test_validator_errors(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    ("cib-bootstrap-options", {}),
                ]
            )
        )
        self.load_fake_agent_metadata()

        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {
                    "unknown": "property",
                    "enable-acl": "Falsch",
                    "batch-limit": "",
                    "non-existing": "",
                },
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    force_code=reports.codes.FORCE,
                    option_names=["unknown"],
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    force_code=reports.codes.FORCE,
                    option_name="enable-acl",
                    option_value="Falsch",
                    allowed_values=(
                        "a pacemaker boolean value: '0', '1', 'false', 'n', "
                        "'no', "
                        "'off', 'on', 'true', 'y', 'yes'"
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.ADD_REMOVE_CANNOT_REMOVE_ITEMS_NOT_IN_THE_CONTAINER,
                    force_code=reports.codes.FORCE,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_PROPERTY,
                    container_id="cib-bootstrap-options",
                    item_list=["batch-limit", "non-existing"],
                ),
            ]
        )

    def test_validator_errors_forced(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    ("cib-bootstrap-options", {}),
                ]
            )
        )
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [
                    (
                        "cib-bootstrap-options",
                        {
                            "unknown": "property",
                            "enable-acl": "Falsch",
                            "batch-limit": "",
                            "non-existing": "",
                        },
                    ),
                ]
            )
        )

        cluster_property.set_properties(
            self.env_assist.get_env(),
            {
                "unknown": "property",
                "enable-acl": "Falsch",
                "batch-limit": "",
                "non-existing": "",
            },
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["unknown"],
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                ),
                fixture.warn(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="enable-acl",
                    option_value="Falsch",
                    allowed_values=(
                        "a pacemaker boolean value: '0', '1', 'false', 'n', "
                        "'no', "
                        "'off', 'on', 'true', 'y', 'yes'"
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    reports.codes.ADD_REMOVE_CANNOT_REMOVE_ITEMS_NOT_IN_THE_CONTAINER,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_PROPERTY,
                    container_id="cib-bootstrap-options",
                    item_list=["batch-limit", "non-existing"],
                ),
            ]
        )

    def test_disable_fencing_warning(self):
        new_properties = {
            "stonith-enabled": "false",
            "fencing-enabled": "false",
        }

        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties([("id1", {})])
        )
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties([("id1", new_properties)])
        )

        cluster_property.set_properties(
            self.env_assist.get_env(),
            new_properties,
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.DEPRECATED_OPTION,
                    option_name="stonith-enabled",
                    replaced_by=["fencing-enabled"],
                    option_type="property",
                ),
                fixture.warn(
                    reports.codes.NO_STONITH_MEANS_WOULD_BE_LEFT_DUE_TO_PROPERTIES,
                    property_map=new_properties,
                ),
            ]
        )
