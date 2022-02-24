import logging
from functools import partial
from unittest import (
    TestCase,
    mock,
)

import pcs.lib.commands.alert as cmd_alert
from pcs.common.reports import ReportItemSeverity as Severities
from pcs.common.reports import codes as report_codes
from pcs.lib.env import LibraryEnvironment

from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.custom_mock import MockLibraryReportProcessor

get_env_tools = partial(
    get_env_tools,
    exception_reports_in_processor_by_default=False,
)


class CreateAlertTest(TestCase):
    fixture_final_alerts = """
        <alerts>
            <alert id="my-alert" path="/my/path" description="my description">
                <meta_attributes id="my-alert-meta_attributes">
                    <nvpair
                        id="my-alert-meta_attributes-meta1"
                        name="meta1"
                        value="val1"
                    />
                </meta_attributes>
                <instance_attributes id="my-alert-instance_attributes">
                    <nvpair
                        id="my-alert-instance_attributes-another"
                        name="another"
                        value="val"
                    />
                    <nvpair
                        id="my-alert-instance_attributes-instance"
                        name="instance"
                        value="value"
                    />
                </instance_attributes>
            </alert>
        </alerts>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_no_path(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_alert.create_alert(
                self.env_assist.get_env(), None, None, None, None
            ),
            [
                (
                    Severities.ERROR,
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    {"option_names": ["path"], "option_type": None},
                    None,
                ),
            ],
        )

    def test_create_no_upgrade(self):
        (
            self.config.runner.cib.load().env.push_cib(
                optional_in_conf=self.fixture_final_alerts
            )
        )
        cmd_alert.create_alert(
            self.env_assist.get_env(),
            "my-alert",
            "/my/path",
            {"instance": "value", "another": "val"},
            {"meta1": "val1"},
            "my description",
        )


class UpdateAlertTest(TestCase):
    fixture_initial_alerts = """
        <alerts>
            <alert id="my-alert" path="/my/path" description="my description">
                <instance_attributes id="my-alert-instance_attributes">
                    <nvpair
                        id="my-alert-instance_attributes-instance"
                        name="instance"
                        value="value"
                    />
                    <nvpair
                        id="my-alert-instance_attributes-another"
                        name="another"
                        value="val"
                    />
                </instance_attributes>
                <meta_attributes id="my-alert-meta_attributes">
                    <nvpair
                        id="my-alert-meta_attributes-meta1"
                        name="meta1"
                        value="val1"
                    />
                </meta_attributes>
            </alert>
        </alerts>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_update_all(self):
        fixture_final_alerts = """
        <alerts>
            <alert id="my-alert" path="/another/one">
                <instance_attributes id="my-alert-instance_attributes">
                    <nvpair
                        id="my-alert-instance_attributes-another"
                        name="another"
                        value="val"
                    />
                    <nvpair
                        id="my-alert-instance_attributes-my-attr"
                        name="my-attr"
                        value="its_val"
                    />
                </instance_attributes>
                <meta_attributes id="my-alert-meta_attributes">
                    <nvpair
                        id="my-alert-meta_attributes-meta1"
                        name="meta1"
                        value="val2"
                    />
                </meta_attributes>
            </alert>
        </alerts>
        """
        (
            self.config.runner.cib.load(
                optional_in_conf=self.fixture_initial_alerts
            ).env.push_cib(
                replace={"./configuration/alerts": fixture_final_alerts}
            )
        )
        cmd_alert.update_alert(
            self.env_assist.get_env(),
            "my-alert",
            "/another/one",
            {"instance": "", "my-attr": "its_val"},
            {"meta1": "val2"},
            "",
        )

    def test_update_instance_attribute(self):
        (
            self.config.runner.cib.load(
                optional_in_conf=self.fixture_initial_alerts
            ).env.push_cib(
                replace={
                    './configuration/alerts/alert[@id="my-alert"]/'
                    'instance_attributes/nvpair[@name="instance"]': """
                        <nvpair
                            id="my-alert-instance_attributes-instance"
                            name="instance"
                            value="new_val"
                        />
                    """
                }
            )
        )
        cmd_alert.update_alert(
            self.env_assist.get_env(),
            "my-alert",
            None,
            {"instance": "new_val"},
            {},
            None,
        )

    def test_alert_doesnt_exist(self):
        (
            self.config.runner.cib.load(
                optional_in_conf="""
                    <alerts>
                        <alert id="alert" path="path"/>
                    </alerts>
                """
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cmd_alert.update_alert(
                self.env_assist.get_env(), "unknown", "test", {}, {}, None
            ),
            [
                (
                    Severities.ERROR,
                    report_codes.ID_NOT_FOUND,
                    {
                        "context_type": "alerts",
                        "context_id": "",
                        "id": "unknown",
                        "expected_types": ["alert"],
                    },
                    None,
                ),
            ],
        )


class RemoveAlertTest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(
            optional_in_conf="""
                <alerts>
                    <alert id="alert1" path="path"/>
                    <alert id="alert2" path="/path"/>
                    <alert id="alert3" path="/path"/>
                    <alert id="alert4" path="/path"/>
                </alerts>
            """
        )

    def test_one_alert(self):
        self.config.env.push_cib(
            remove="./configuration/alerts/alert[@id='alert2']"
        )
        cmd_alert.remove_alert(self.env_assist.get_env(), ["alert2"])

    def test_multiple_alerts(self):
        self.config.env.push_cib(
            remove=[
                "./configuration/alerts/alert[@id='alert1']",
                "./configuration/alerts/alert[@id='alert3']",
                "./configuration/alerts/alert[@id='alert4']",
            ]
        )
        cmd_alert.remove_alert(
            self.env_assist.get_env(), ["alert1", "alert3", "alert4"]
        )

    def test_no_alert(self):
        self.config.env.push_cib()
        cmd_alert.remove_alert(self.env_assist.get_env(), [])

    def test_alerts_dont_exist(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_alert.remove_alert(
                self.env_assist.get_env(),
                ["unknown1", "alert1", "unknown2", "alert2"],
            )
        )
        self.env_assist.assert_reports(
            [
                (
                    Severities.ERROR,
                    report_codes.ID_NOT_FOUND,
                    {
                        "context_type": "alerts",
                        "context_id": "",
                        "id": "unknown1",
                        "expected_types": ["alert"],
                    },
                    None,
                ),
                (
                    Severities.ERROR,
                    report_codes.ID_NOT_FOUND,
                    {
                        "context_type": "alerts",
                        "context_id": "",
                        "id": "unknown2",
                        "expected_types": ["alert"],
                    },
                    None,
                ),
            ]
        )


class AddRecipientTest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(
            optional_in_conf="""
                <alerts>
                    <alert id="alert" path="path">
                        <recipient id="alert-recipient" value="value1"/>
                    </alert>
                </alerts>
            """
        )

    def test_value_not_defined(self):
        self.config.remove("runner.cib.load")
        self.env_assist.assert_raise_library_error(
            lambda: cmd_alert.add_recipient(
                self.env_assist.get_env(), "unknown", "", {}, {}
            ),
            [
                (
                    Severities.ERROR,
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    {"option_names": ["value"], "option_type": None},
                )
            ],
        )

    def test_recipient_already_exists(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_alert.add_recipient(
                self.env_assist.get_env(),
                "alert",
                "value1",
                {},
                {},
                recipient_id="alert-recipient",
            ),
            [
                (
                    Severities.ERROR,
                    report_codes.ID_ALREADY_EXISTS,
                    {"id": "alert-recipient"},
                )
            ],
        )

    def test_without_id(self):
        self.config.env.push_cib(
            replace={
                './/alert[@id="alert"]': """
                <alert id="alert" path="path">
                    <recipient id="alert-recipient" value="value1"/>
                    <recipient id="alert-recipient-1" value="value">
                        <meta_attributes
                            id="alert-recipient-1-meta_attributes"
                        >
                            <nvpair
                                id="alert-recipient-1-meta_attributes-attr1"
                                name="attr1"
                                value="val1"
                            />
                            <nvpair
                                id="alert-recipient-1-meta_attributes-attr2"
                                name="attr2"
                                value="val2"
                            />
                        </meta_attributes>
                        <instance_attributes
                            id="alert-recipient-1-instance_attributes"
                        >
                            <nvpair
                                id="alert-recipient-1-instance_attributes-attr1"
                                name="attr1"
                                value="val1"
                            />
                        </instance_attributes>
                    </recipient>
                </alert>
                """
            }
        )
        cmd_alert.add_recipient(
            self.env_assist.get_env(),
            "alert",
            "value",
            {"attr1": "val1"},
            {"attr2": "val2", "attr1": "val1"},
        )

    def test_with_id(self):
        self.config.env.push_cib(
            replace={
                './/alert[@id="alert"]': """
                <alert id="alert" path="path">
                    <recipient id="alert-recipient" value="value1"/>
                    <recipient id="my-recipient" value="value">
                        <meta_attributes
                            id="my-recipient-meta_attributes"
                        >
                            <nvpair
                                id="my-recipient-meta_attributes-attr1"
                                name="attr1"
                                value="val1"
                            />
                            <nvpair
                                id="my-recipient-meta_attributes-attr2"
                                name="attr2"
                                value="val2"
                            />
                        </meta_attributes>
                        <instance_attributes
                            id="my-recipient-instance_attributes"
                        >
                            <nvpair
                                id="my-recipient-instance_attributes-attr1"
                                name="attr1"
                                value="val1"
                            />
                        </instance_attributes>
                    </recipient>
                </alert>
                """
            }
        )
        cmd_alert.add_recipient(
            self.env_assist.get_env(),
            "alert",
            "value",
            {"attr1": "val1"},
            {"attr2": "val2", "attr1": "val1"},
            recipient_id="my-recipient",
        )


class UpdateRecipientTest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(
            optional_in_conf="""
                <alerts>
                    <alert id="alert" path="path">
                        <recipient id="alert-recipient" value="value1"/>
                        <recipient id="alert-recipient-1" value="value"
                            description="d"
                        >
                            <meta_attributes
                                id="alert-recipient-1-meta_attributes"
                            >
                                <nvpair
                                    id="alert-recipient-1-meta_attributes-attr1"
                                    name="attr1"
                                    value="val1"
                                />
                                <nvpair
                                    id="alert-recipient-1-meta_attributes-attr2"
                                    name="attr2"
                                    value="val2"
                                />
                            </meta_attributes>
                            <instance_attributes
                                id="alert-recipient-1-instance_attributes"
                            >
                                <nvpair
                                    id="alert-recipient-1-instance_attributes-attr1"
                                    name="attr1"
                                    value="val1"
                                />
                            </instance_attributes>
                        </recipient>
                    </alert>
                </alerts>
            """
        )

    def test_empty_value(self):
        self.config.remove("runner.cib.load")
        self.env_assist.assert_raise_library_error(
            lambda: cmd_alert.update_recipient(
                self.env_assist.get_env(),
                "alert-recipient-1",
                {},
                {},
                recipient_value="",
            ),
            [
                (
                    Severities.ERROR,
                    report_codes.CIB_ALERT_RECIPIENT_VALUE_INVALID,
                    {"recipient": ""},
                )
            ],
        )

    def test_recipient_not_found(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_alert.update_recipient(
                self.env_assist.get_env(), "recipient", {}, {}
            ),
            [
                (
                    Severities.ERROR,
                    report_codes.ID_NOT_FOUND,
                    {
                        "id": "recipient",
                        "expected_types": ["recipient"],
                        "context_id": "",
                        "context_type": "alerts",
                    },
                    None,
                )
            ],
        )

    def test_update_all(self):
        self.config.env.push_cib(
            replace={
                './/alert[@id="alert"]': """
                <alert id="alert" path="path">
                    <recipient id="alert-recipient" value="value1"/>
                    <recipient
                        id="alert-recipient-1"
                        value="new_val"
                        description="desc"
                    >
                        <meta_attributes
                            id="alert-recipient-1-meta_attributes"
                        >
                            <nvpair
                                id="alert-recipient-1-meta_attributes-attr2"
                                name="attr2"
                                value="val2"
                            />
                            <nvpair
                                id="alert-recipient-1-meta_attributes-attr3"
                                name="attr3"
                                value="new_val"
                            />
                        </meta_attributes>
                        <instance_attributes
                            id="alert-recipient-1-instance_attributes"
                        >
                            <nvpair
                                id="alert-recipient-1-instance_attributes-attr1"
                                name="attr1"
                                value="value"
                            />
                        </instance_attributes>
                    </recipient>
                </alert>
                """,
            }
        )
        cmd_alert.update_recipient(
            self.env_assist.get_env(),
            "alert-recipient-1",
            {"attr1": "value"},
            {"attr1": "", "attr3": "new_val"},
            recipient_value="new_val",
            description="desc",
        )


class RemoveRecipientTest(TestCase):
    fixture_initial_alerts = """
        <alerts>
            <alert id="alert" path="path">
                <recipient id="alert-recip1" value="value1"/>
                <recipient id="alert-recip2" value="value2"/>
            </alert>
            <alert id="alert2" path="path">
                <recipient id="alert2-recip3" value="value3"/>
                <recipient id="alert2-recip4" value="value4"/>
            </alert>
        </alerts>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(
            optional_in_conf=self.fixture_initial_alerts
        )

    def test_recipient_not_found(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_alert.remove_recipient(
                self.env_assist.get_env(),
                ["recipient", "alert-recip1", "alert2-recip1"],
            )
        )
        self.env_assist.assert_reports(
            [
                (
                    Severities.ERROR,
                    report_codes.ID_NOT_FOUND,
                    {
                        "id": "recipient",
                        "expected_types": ["recipient"],
                        "context_type": "alerts",
                        "context_id": "",
                    },
                    None,
                ),
                (
                    Severities.ERROR,
                    report_codes.ID_NOT_FOUND,
                    {
                        "id": "alert2-recip1",
                        "expected_types": ["recipient"],
                        "context_type": "alerts",
                        "context_id": "",
                    },
                    None,
                ),
            ]
        )

    def test_one_recipient(self):
        self.config.env.push_cib(
            remove="./configuration/alerts/alert/recipient[@id='alert-recip1']"
        )
        cmd_alert.remove_recipient(self.env_assist.get_env(), ["alert-recip1"])

    def test_multiple_recipients(self):
        self.config.env.push_cib(
            remove=[
                "./configuration/alerts/alert/recipient[@id='alert-recip1']",
                "./configuration/alerts/alert/recipient[@id='alert-recip2']",
                "./configuration/alerts/alert/recipient[@id='alert2-recip4']",
            ]
        )
        cmd_alert.remove_recipient(
            self.env_assist.get_env(),
            ["alert-recip1", "alert-recip2", "alert2-recip4"],
        )

    def test_no_recipient(self):
        self.config.env.push_cib()
        cmd_alert.remove_recipient(self.env_assist.get_env(), [])


@mock.patch.object(LibraryEnvironment, "get_cib")
@mock.patch("pcs.lib.cib.alert.get_all_alerts")
class GetAllAlertsTest(TestCase):
    def setUp(self):
        self.mock_log = mock.MagicMock(spec_set=logging.Logger)
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_env = LibraryEnvironment(self.mock_log, self.mock_rep)

    def test_success(self, mock_alerts, mock_get_cib):
        mock_alerts.return_value = [{"id": "alert"}]
        mock_get_cib.return_value = "<cib/>"
        self.assertEqual(
            [{"id": "alert"}], cmd_alert.get_all_alerts(self.mock_env)
        )
        self.assertEqual(1, mock_alerts.call_count)
