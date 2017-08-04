from __future__ import (
    absolute_import,
    division,
    print_function,
)

from functools import partial
import logging

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as Severities
from pcs.lib.env import LibraryEnvironment
from pcs.lib.external import CommandRunner
from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.fixture import (
    remove_element,
    replace_element,
    replace_optional_element,
)
from pcs.test.tools.pcs_unittest import mock, TestCase

import pcs.lib.commands.alert as cmd_alert


get_env_tools = partial(
    get_env_tools,
    base_cib_filename="cib-empty-2.5.xml"
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
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    {"option_names": ["path"]},
                    None
                ),
            ],
            expected_in_processor=False
        )

    def test_create_no_upgrade(self):
        (self.config
            .runner.cib.load()
            .env.push_cib(
                modifiers=[
                    replace_optional_element(
                        "./configuration",
                        "alerts",
                        self.fixture_final_alerts
                    )
                ]
            )
        )
        cmd_alert.create_alert(
            self.env_assist.get_env(),
            "my-alert",
            "/my/path",
            {
                "instance": "value",
                "another": "val"
            },
            {"meta1": "val1"},
            "my description"
        )

    def test_create_upgrade(self):
        (self.config
            .runner.cib.load(
                filename="cib-empty.xml",
                name="load_cib_old_version"
            )
            .runner.cib.upgrade()
            .runner.cib.load()
            .env.push_cib(
                modifiers=[
                    replace_optional_element(
                        "./configuration",
                        "alerts",
                        self.fixture_final_alerts
                    )
                ]
            )
        )
        cmd_alert.create_alert(
            self.env_assist.get_env(),
            "my-alert",
            "/my/path",
            {
                "instance": "value",
                "another": "val"
            },
            {"meta1": "val1"},
            "my description"
        )
        self.env_assist.assert_reports([
            (
                Severities.INFO,
                report_codes.CIB_UPGRADE_SUCCESSFUL,
                {},
                None
            ),
        ])


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
        (self.config
            .runner.cib.load(
                modifiers=[
                    replace_optional_element(
                        "./configuration",
                        "alerts",
                        self.fixture_initial_alerts
                    )
                ]
            )
            .env.push_cib(
                modifiers=[
                    replace_element(
                        "./configuration/alerts",
                        fixture_final_alerts
                    )
                ]
            )
        )
        cmd_alert.update_alert(
            self.env_assist.get_env(),
            "my-alert",
            "/another/one",
            {
                "instance": "",
                "my-attr": "its_val"
            },
            {"meta1": "val2"},
            ""
        )

    def test_update_instance_attribute(self):
        (self.config
            .runner.cib.load(
                modifiers=[
                    replace_optional_element(
                        "./configuration",
                        "alerts",
                        self.fixture_initial_alerts
                    )
                ]
            )
            .env.push_cib(
                modifiers=[
                    replace_element(
                        (
                            './configuration/alerts/alert[@id="my-alert"]/'
                            +
                            'instance_attributes/nvpair[@name="instance"]'
                        ),
                        """
                            <nvpair
                                id="my-alert-instance_attributes-instance"
                                name="instance"
                                value="new_val"
                            />
                        """
                    )
                ]
            )
        )
        cmd_alert.update_alert(
            self.env_assist.get_env(),
            "my-alert",
            None,
            {"instance": "new_val"},
            {},
            None
        )

    def test_alert_doesnt_exist(self):
        (self.config
            .runner.cib.load(
                modifiers=[
                    replace_optional_element(
                        "./configuration",
                        "alerts",
                        """
                            <alerts>
                                <alert id="alert" path="path"/>
                            </alerts>
                        """
                    )
                ]
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
                        "id_description": "alert",
                    },
                    None
                ),
            ],
            expected_in_processor=False
        )


class RemoveAlertTest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(
            modifiers=[
                replace_optional_element(
                    "./configuration",
                    "alerts",
                    """
                        <alerts>
                            <alert id="alert1" path="path"/>
                            <alert id="alert2" path="/path"/>
                            <alert id="alert3" path="/path"/>
                            <alert id="alert4" path="/path"/>
                        </alerts>
                    """
                )
            ]
        )

    def test_one_alert(self):
        self.config.env.push_cib(
            modifiers=[
                remove_element("./configuration/alerts/alert[@id='alert2']")
            ]
        )
        cmd_alert.remove_alert(
            self.env_assist.get_env(),
            ["alert2"]
        )

    def test_multiple_alerts(self):
        self.config.env.push_cib(
            modifiers=[
                remove_element("./configuration/alerts/alert[@id='alert1']"),
                remove_element("./configuration/alerts/alert[@id='alert3']"),
                remove_element("./configuration/alerts/alert[@id='alert4']"),
            ]
        )
        cmd_alert.remove_alert(
            self.env_assist.get_env(),
            ["alert1", "alert3", "alert4"]
        )

    def test_no_alert(self):
        self.config.env.push_cib()
        cmd_alert.remove_alert(
            self.env_assist.get_env(),
            []
        )

    def test_alerts_dont_exist(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_alert.remove_alert(
                self.env_assist.get_env(),
                ["unknown1", "alert1", "unknown2", "alert2"]
            ),
            [
                (
                    Severities.ERROR,
                    report_codes.ID_NOT_FOUND,
                    {
                        "context_type": "alerts",
                        "context_id": "",
                        "id": "unknown1",
                        "id_description": "alert",
                    },
                    None
                ),
                (
                    Severities.ERROR,
                    report_codes.ID_NOT_FOUND,
                    {
                        "context_type": "alerts",
                        "context_id": "",
                        "id": "unknown2",
                        "id_description": "alert",
                    },
                    None
                ),
            ],
            expected_in_processor=True
        )


class AddRecipientTest(TestCase):
    def setUp(self):
        self.mock_log = mock.MagicMock(spec_set=logging.Logger)
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_rep = MockLibraryReportProcessor()
        cib = """
            <cib validate-with="pacemaker-2.5">
                <configuration>
                    <alerts>
                        <alert id="alert" path="path">
                            <recipient id="alert-recipient" value="value1"/>
                        </alert>
                    </alerts>
                </configuration>
            </cib>
        """
        self.mock_env = LibraryEnvironment(
            self.mock_log, self.mock_rep, cib_data=cib
        )

    def test_value_not_defined(self):
        assert_raise_library_error(
            lambda: cmd_alert.add_recipient(
                self.mock_env, "unknown", "", {}, {}
            ),
            (
                Severities.ERROR,
                report_codes.REQUIRED_OPTION_IS_MISSING,
                {"option_names": ["value"]}
            )
        )

    def test_recipient_already_exists(self):
        assert_raise_library_error(
            lambda: cmd_alert.add_recipient(
                self.mock_env, "alert", "value1", {}, {},
                recipient_id="alert-recipient"
            ),
            (
                Severities.ERROR,
                report_codes.ID_ALREADY_EXISTS,
                {"id": "alert-recipient"}
            )
        )

    def test_without_id(self):
        cmd_alert.add_recipient(
            self.mock_env,
            "alert",
            "value",
            {"attr1": "val1"},
            {
                "attr2": "val2",
                "attr1": "val1"
            }
        )
        assert_xml_equal(
            """
<cib validate-with="pacemaker-2.5">
    <configuration>
        <alerts>
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
        </alerts>
    </configuration>
</cib>
            """,
            self.mock_env._get_cib_xml()
        )

    def test_with_id(self):
        cmd_alert.add_recipient(
            self.mock_env,
            "alert",
            "value",
            {"attr1": "val1"},
            {
                "attr2": "val2",
                "attr1": "val1"
            },
            recipient_id="my-recipient"
        )
        assert_xml_equal(
            """
<cib validate-with="pacemaker-2.5">
    <configuration>
        <alerts>
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
        </alerts>
    </configuration>
</cib>
            """,
            self.mock_env._get_cib_xml()
        )


class UpdateRecipientTest(TestCase):
    def setUp(self):
        self.mock_log = mock.MagicMock(spec_set=logging.Logger)
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_rep = MockLibraryReportProcessor()
        cib = """
<cib validate-with="pacemaker-2.5">
    <configuration>
        <alerts>
            <alert id="alert" path="path">
                <recipient id="alert-recipient" value="value1"/>
                <recipient id="alert-recipient-1" value="value" description="d">
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
    </configuration>
</cib>
        """
        self.mock_env = LibraryEnvironment(
            self.mock_log, self.mock_rep, cib_data=cib
        )

    def test_empty_value(self):
        assert_raise_library_error(
            lambda: cmd_alert.update_recipient(
                self.mock_env, "alert-recipient-1", {}, {}, recipient_value=""
            ),
            (
                Severities.ERROR,
                report_codes.CIB_ALERT_RECIPIENT_VALUE_INVALID,
                {"recipient": ""}
            )
        )

    def test_recipient_not_found(self):
        assert_raise_library_error(
            lambda: cmd_alert.update_recipient(
                self.mock_env, "recipient", {}, {}
            ),
            (
                Severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "recipient",
                    "id_description": "recipient"
                }
            )
        )

    def test_update_all(self):
        cmd_alert.update_recipient(
            self.mock_env,
            "alert-recipient-1",
            {"attr1": "value"},
            {
                "attr1": "",
                "attr3": "new_val"
            },
            recipient_value="new_val",
            description="desc"
        )
        assert_xml_equal(
            """
<cib validate-with="pacemaker-2.5">
    <configuration>
        <alerts>
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
        </alerts>
    </configuration>
</cib>
            """,
            self.mock_env._get_cib_xml()
        )


class RemoveRecipientTest(TestCase):
    def setUp(self):
        self.mock_log = mock.MagicMock(spec_set=logging.Logger)
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_rep = MockLibraryReportProcessor()
        cib = """
            <cib validate-with="pacemaker-2.5">
                <configuration>
                    <alerts>
                        <alert id="alert" path="path">
                            <recipient id="alert-recipient1" value="value1"/>
                            <recipient id="alert-recipient2" value="value2"/>
                        </alert>
                        <alert id="alert2" path="path">
                            <recipient id="alert2-recipient3" value="value3"/>
                            <recipient id="alert2-recipient4" value="value4"/>
                        </alert>
                    </alerts>
                </configuration>
            </cib>
        """
        self.mock_env = LibraryEnvironment(
            self.mock_log, self.mock_rep, cib_data=cib
        )

    def test_recipient_not_found(self):
        report_list = [
            (
                Severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {"id": "recipient"}
            ),
            (
                Severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {"id": "alert2-recipient1"}
            )
        ]
        assert_raise_library_error(
            lambda: cmd_alert.remove_recipient(
                self.mock_env,
                ["recipient", "alert-recipient1", "alert2-recipient1"]
            ),
            *report_list
        )
        assert_report_item_list_equal(
            self.mock_rep.report_item_list, report_list
        )

    def test_one_recipient(self):
        cmd_alert.remove_recipient(self.mock_env, ["alert-recipient1"])
        assert_xml_equal(
            """
            <cib validate-with="pacemaker-2.5">
                <configuration>
                    <alerts>
                        <alert id="alert" path="path">
                            <recipient id="alert-recipient2" value="value2"/>
                        </alert>
                        <alert id="alert2" path="path">
                            <recipient id="alert2-recipient3" value="value3"/>
                            <recipient id="alert2-recipient4" value="value4"/>
                        </alert>
                    </alerts>
                </configuration>
            </cib>
            """,
            self.mock_env._get_cib_xml()
        )
        self.assertEqual([], self.mock_rep.report_item_list)

    def test_multiple_recipients(self):
        cmd_alert.remove_recipient(
            self.mock_env,
            ["alert-recipient1", "alert-recipient2", "alert2-recipient4"]
        )
        assert_xml_equal(
            """
            <cib validate-with="pacemaker-2.5">
                <configuration>
                    <alerts>
                        <alert id="alert" path="path"/>
                        <alert id="alert2" path="path">
                            <recipient id="alert2-recipient3" value="value3"/>
                        </alert>
                    </alerts>
                </configuration>
            </cib>
            """,
            self.mock_env._get_cib_xml()
        )
        self.assertEqual([], self.mock_rep.report_item_list)

    def test_no_recipient(self):
        cmd_alert.remove_recipient(self.mock_env, [])
        assert_xml_equal(
            """
            <cib validate-with="pacemaker-2.5">
                <configuration>
                    <alerts>
                        <alert id="alert" path="path">
                            <recipient id="alert-recipient1" value="value1"/>
                            <recipient id="alert-recipient2" value="value2"/>
                        </alert>
                        <alert id="alert2" path="path">
                            <recipient id="alert2-recipient3" value="value3"/>
                            <recipient id="alert2-recipient4" value="value4"/>
                        </alert>
                    </alerts>
                </configuration>
            </cib>
            """,
            self.mock_env._get_cib_xml()
        )
        self.assertEqual([], self.mock_rep.report_item_list)


@mock.patch("pcs.lib.cib.alert.get_all_alerts")
class GetAllAlertsTest(TestCase):
    def setUp(self):
        self.mock_log = mock.MagicMock(spec_set=logging.Logger)
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_env = LibraryEnvironment(
            self.mock_log, self.mock_rep, cib_data='<cib/>'
        )

    def test_success(self, mock_alerts):
        mock_alerts.return_value = [{"id": "alert"}]
        self.assertEqual(
            [{"id": "alert"}],
            cmd_alert.get_all_alerts(self.mock_env)
        )
        self.assertEqual(1, mock_alerts.call_count)
