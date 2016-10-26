from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging
from lxml import etree

from pcs.test.tools.pcs_unittest import TestCase

from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_xml_equal,
    assert_report_item_list_equal,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as Severities
from pcs.lib.env import LibraryEnvironment
from pcs.lib.external import CommandRunner

import pcs.lib.commands.alert as cmd_alert


@mock.patch("pcs.lib.cib.tools.upgrade_cib")
class CreateAlertTest(TestCase):
    def setUp(self):
        self.mock_log = mock.MagicMock(spec_set=logging.Logger)
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_env = LibraryEnvironment(
            self.mock_log, self.mock_rep, cib_data="<cib/>"
        )

    def test_no_path(self, mock_upgrade_cib):
        assert_raise_library_error(
            lambda: cmd_alert.create_alert(
                self.mock_env, None, None, None, None
            ),
            (
                Severities.ERROR,
                report_codes.REQUIRED_OPTION_IS_MISSING,
                {"option_name": "path"}
            )
        )
        self.assertEqual(0, mock_upgrade_cib.call_count)

    def test_upgrade_needed(self, mock_upgrade_cib):
        self.mock_env._push_cib_xml(
            """
            <cib validate-with="pacemaker-2.4.1">
                <configuration>
                </configuration>
            </cib>
            """
        )
        mock_upgrade_cib.return_value = etree.XML(
            """
            <cib validate-with="pacemaker-2.5.0">
                <configuration>
                </configuration>
            </cib>
            """
        )
        cmd_alert.create_alert(
            self.mock_env,
            "my-alert",
            "/my/path",
            {
                "instance": "value",
                "another": "val"
            },
            {"meta1": "val1"},
            "my description"
        )
        assert_xml_equal(
            """
<cib validate-with="pacemaker-2.5.0">
    <configuration>
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
    </configuration>
</cib>
            """,
            self.mock_env._get_cib_xml()
        )
        self.assertEqual(1, mock_upgrade_cib.call_count)


class UpdateAlertTest(TestCase):
    def setUp(self):
        self.mock_log = mock.MagicMock(spec_set=logging.Logger)
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_env = LibraryEnvironment(
            self.mock_log, self.mock_rep, cib_data="<cib/>"
        )

    def test_update_all(self):
        self.mock_env._push_cib_xml(
            """
<cib validate-with="pacemaker-2.5">
    <configuration>
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
    </configuration>
</cib>
            """
        )
        cmd_alert.update_alert(
            self.mock_env,
            "my-alert",
            "/another/one",
            {
                "instance": "",
                "my-attr": "its_val"
            },
            {"meta1": "val2"},
            ""
        )
        assert_xml_equal(
            """
<cib validate-with="pacemaker-2.5">
    <configuration>
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
    </configuration>
</cib>
            """,
            self.mock_env._get_cib_xml()
        )

    def test_update_instance_attribute(self):
        self.mock_env._push_cib_xml(
            """
<cib validate-with="pacemaker-2.5">
    <configuration>
        <alerts>
            <alert id="my-alert" path="/my/path" description="my description">
                <instance_attributes id="my-alert-instance_attributes">
                    <nvpair
                        id="my-alert-instance_attributes-instance"
                        name="instance"
                        value="value"
                    />
                </instance_attributes>
            </alert>
        </alerts>
    </configuration>
</cib>
            """
        )
        cmd_alert.update_alert(
            self.mock_env,
            "my-alert",
            None,
            {"instance": "new_val"},
            {},
            None
        )
        assert_xml_equal(
            """
<cib validate-with="pacemaker-2.5">
    <configuration>
        <alerts>
            <alert id="my-alert" path="/my/path" description="my description">
                <instance_attributes id="my-alert-instance_attributes">
                    <nvpair
                        id="my-alert-instance_attributes-instance"
                        name="instance"
                        value="new_val"
                    />
                </instance_attributes>
            </alert>
        </alerts>
    </configuration>
</cib>
            """,
            self.mock_env._get_cib_xml()
        )

    def test_alert_doesnt_exist(self):
        self.mock_env._push_cib_xml(
            """
            <cib validate-with="pacemaker-2.5">
                <configuration>
                    <alerts>
                        <alert id="alert" path="path"/>
                    </alerts>
                </configuration>
            </cib>
            """
        )
        assert_raise_library_error(
            lambda: cmd_alert.update_alert(
                self.mock_env, "unknown", "test", {}, {}, None
            ),
            (
                Severities.ERROR,
                report_codes.CIB_ALERT_NOT_FOUND,
                {"alert": "unknown"}
            )
        )


class RemoveAlertTest(TestCase):
    def setUp(self):
        self.mock_log = mock.MagicMock(spec_set=logging.Logger)
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_rep = MockLibraryReportProcessor()
        cib = """
            <cib validate-with="pacemaker-2.5">
                <configuration>
                    <alerts>
                        <alert id="alert1" path="path"/>
                        <alert id="alert2" path="/path"/>
                        <alert id="alert3" path="/path"/>
                        <alert id="alert4" path="/path"/>
                    </alerts>
                </configuration>
            </cib>
        """
        self.mock_env = LibraryEnvironment(
            self.mock_log, self.mock_rep, cib_data=cib
        )

    def test_one_alert(self):
        cmd_alert.remove_alert(self.mock_env, ["alert2"])
        assert_xml_equal(
            """
                <cib validate-with="pacemaker-2.5">
                    <configuration>
                        <alerts>
                            <alert id="alert1" path="path"/>
                            <alert id="alert3" path="/path"/>
                            <alert id="alert4" path="/path"/>
                        </alerts>
                    </configuration>
                </cib>
            """,
            self.mock_env._get_cib_xml()
        )
        self.assertEqual([], self.mock_rep.report_item_list)

    def test_multiple_alerts(self):
        cmd_alert.remove_alert(self.mock_env, ["alert1", "alert3", "alert4"])
        assert_xml_equal(
            """
                <cib validate-with="pacemaker-2.5">
                    <configuration>
                        <alerts>
                            <alert id="alert2" path="/path"/>
                        </alerts>
                    </configuration>
                </cib>
            """,
            self.mock_env._get_cib_xml()
        )
        self.assertEqual([], self.mock_rep.report_item_list)

    def test_no_alert(self):
        cmd_alert.remove_alert(self.mock_env, [])
        assert_xml_equal(
            """
                <cib validate-with="pacemaker-2.5">
                    <configuration>
                        <alerts>
                            <alert id="alert1" path="path"/>
                            <alert id="alert2" path="/path"/>
                            <alert id="alert3" path="/path"/>
                            <alert id="alert4" path="/path"/>
                        </alerts>
                    </configuration>
                </cib>
            """,
            self.mock_env._get_cib_xml()
        )
        self.assertEqual([], self.mock_rep.report_item_list)

    def test_failure(self):
        report_list = [
            (
                Severities.ERROR,
                report_codes.CIB_ALERT_NOT_FOUND,
                {"alert": "unknown"}
            ),
            (
                Severities.ERROR,
                report_codes.CIB_ALERT_NOT_FOUND,
                {"alert": "unknown2"}
            )
        ]
        assert_raise_library_error(
            lambda: cmd_alert.remove_alert(
                self.mock_env, ["unknown", "alert1", "unknown2", "alert2"]
            ),
            *report_list
        )
        assert_report_item_list_equal(
            self.mock_rep.report_item_list, report_list
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

    def test_alert_not_found(self):
        assert_raise_library_error(
            lambda: cmd_alert.add_recipient(
                self.mock_env, "unknown", "recipient", {}, {}
            ),
            (
                Severities.ERROR,
                report_codes.CIB_ALERT_NOT_FOUND,
                {"alert": "unknown"}
            )
        )

    def test_value_not_defined(self):
        assert_raise_library_error(
            lambda: cmd_alert.add_recipient(
                self.mock_env, "unknown", "", {}, {}
            ),
            (
                Severities.ERROR,
                report_codes.REQUIRED_OPTION_IS_MISSING,
                {"option_name": "value"}
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
                    "id_description": "Recipient"
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
