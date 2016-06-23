from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

from lxml import etree

from pcs.common import report_codes
from pcs.lib.cib import alert
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import(
    assert_raise_library_error,
    assert_xml_equal,
)
from pcs.test.tools.pcs_mock import mock


@mock.patch("pcs.lib.cib.alert.update_nvset")
class UpdateInstanceAttributesTest(TestCase):
    def test_success(self, mock_update_nvset):
        ret_val = etree.Element("nvset")
        tree = etree.Element("tree")
        element = etree.Element("element")
        attributes = {"a": 1}
        mock_update_nvset.return_value = ret_val
        self.assertEqual(
            alert.update_instance_attributes(tree, element, attributes),
            ret_val
        )
        mock_update_nvset.assert_called_once_with(
            "instance_attributes", tree, element, attributes
        )


@mock.patch("pcs.lib.cib.alert.update_nvset")
class UpdateMetaAttributesTest(TestCase):
    def test_success(self, mock_update_nvset):
        ret_val = etree.Element("nvset")
        tree = etree.Element("tree")
        element = etree.Element("element")
        attributes = {"a": 1}
        mock_update_nvset.return_value = ret_val
        self.assertEqual(
            alert.update_meta_attributes(tree, element, attributes),
            ret_val
        )
        mock_update_nvset.assert_called_once_with(
            "meta_attributes", tree, element, attributes
        )


class UpdateOptionalAttributeTest(TestCase):
    def test_add(self):
        element = etree.Element("element")
        alert._update_optional_attribute(element, "attr", "value1")
        self.assertEqual(element.get("attr"), "value1")

    def test_update(self):
        element = etree.Element("element", attr="value")
        alert._update_optional_attribute(element, "attr", "value1")
        self.assertEqual(element.get("attr"), "value1")

    def test_remove(self):
        element = etree.Element("element", attr="value")
        alert._update_optional_attribute(element, "attr", "")
        self.assertTrue(element.get("attr") is None)


class GetAlertByIdTest(TestCase):
    def test_found(self):
        xml = """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert-1"/>
                        <alert id="alert-2"/>
                    </alerts>
                </configuration>
            </cib>
        """
        assert_xml_equal(
            '<alert id="alert-2"/>',
            etree.tostring(
                alert.get_alert_by_id(etree.XML(xml), "alert-2")
            ).decode()
        )

    def test_different_place(self):
        xml = """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert-1"/>
                    </alerts>
                    <alert id="alert-2"/>
                </configuration>
            </cib>
        """
        assert_raise_library_error(
            lambda: alert.get_alert_by_id(etree.XML(xml), "alert-2"),
            (
                severities.ERROR,
                report_codes.CIB_ALERT_NOT_FOUND,
                {"alert": "alert-2"}
            )
        )

    def test_not_exist(self):
        xml = """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert-1"/>
                    </alerts>
                </configuration>
            </cib>
        """
        assert_raise_library_error(
            lambda: alert.get_alert_by_id(etree.XML(xml), "alert-2"),
            (
                severities.ERROR,
                report_codes.CIB_ALERT_NOT_FOUND,
                {"alert": "alert-2"}
            )
        )


class GetRecipientTest(TestCase):
    def setUp(self):
        self.xml = etree.XML(
            """
                <alert id="alert-1">
                    <recipient id="rec-1" value="value1"/>
                    <recipient id="rec-2" value="value2"/>
                    <not_recipient value="value3"/>
                    <recipients>
                        <recipient id="rec-4" value="value4"/>
                    </recipients>
                </alert>
            """
        )

    def test_exist(self):
        assert_xml_equal(
            '<recipient id="rec-2" value="value2"/>',
            etree.tostring(alert.get_recipient(self.xml, "value2")).decode()
        )

    def test_different_place(self):
        assert_raise_library_error(
            lambda: alert.get_recipient(self.xml, "value4"),
            (
                severities.ERROR,
                report_codes.CIB_ALERT_RECIPIENT_NOT_FOUND,
                {
                    "alert": "alert-1",
                    "recipient": "value4"
                }
            )
        )

    def test_not_recipient(self):
        assert_raise_library_error(
            lambda: alert.get_recipient(self.xml, "value3"),
            (
                severities.ERROR,
                report_codes.CIB_ALERT_RECIPIENT_NOT_FOUND,
                {
                    "alert": "alert-1",
                    "recipient": "value3"
                }
            )
        )


class CreateAlertTest(TestCase):
    def setUp(self):
        self.tree = etree.XML(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert"/>
                    </alerts>
                </configuration>
            </cib>
            """
        )

    def test_no_alerts(self):
        tree = etree.XML(
            """
            <cib>
                <configuration/>
            </cib>
            """
        )
        assert_xml_equal(
            '<alert id="my-alert" path="/test/path"/>',
            etree.tostring(
                alert.create_alert(tree, "my-alert", "/test/path")
            ).decode()
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="my-alert" path="/test/path"/>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(tree).decode()
        )

    def test_alerts_exists(self):
        assert_xml_equal(
            '<alert id="my-alert" path="/test/path"/>',
            etree.tostring(
                alert.create_alert(self.tree, "my-alert", "/test/path")
            ).decode()
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert"/>
                        <alert id="my-alert" path="/test/path"/>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode()
        )

    def test_alerts_exists_with_description(self):
        assert_xml_equal(
            '<alert id="my-alert" path="/test/path" description="nothing"/>',
            etree.tostring(alert.create_alert(
                self.tree, "my-alert", "/test/path", "nothing"
            )).decode()
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert"/>
                        <alert
                            id="my-alert"
                            path="/test/path"
                            description="nothing"
                        />
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode()
        )

    def test_invalid_id(self):
        assert_raise_library_error(
            lambda: alert.create_alert(self.tree, "1alert", "/path"),
            (
                severities.ERROR,
                report_codes.INVALID_ID,
                {
                    "id": "1alert",
                    "id_description": "alert-id",
                    "invalid_character": "1",
                    "reason": "invalid first character"
                }
            )
        )

    def test_id_exists(self):
        assert_raise_library_error(
            lambda: alert.create_alert(self.tree, "alert", "/path"),
            (
                severities.ERROR,
                report_codes.ID_ALREADY_EXISTS,
                {"id": "alert"}
            )
        )

    def test_no_id(self):
        assert_xml_equal(
            '<alert id="alert-1" path="/test/path"/>',
            etree.tostring(
                alert.create_alert(self.tree, None, "/test/path")
            ).decode()
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert"/>
                        <alert id="alert-1" path="/test/path"/>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode()
        )


class UpdateAlertTest(TestCase):
    def setUp(self):
        self.tree = etree.XML(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path"/>
                        <alert id="alert1" path="/path1" description="nothing"/>
                    </alerts>
                </configuration>
            </cib>
            """
        )

    def test_update_path(self):
        assert_xml_equal(
            '<alert id="alert" path="/test/path"/>',
            etree.tostring(
                alert.update_alert(self.tree, "alert", "/test/path")
            ).decode()
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/test/path"/>
                        <alert id="alert1" path="/path1" description="nothing"/>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode()
        )

    def test_remove_path(self):
        assert_xml_equal(
            '<alert id="alert" path="/path"/>',
            etree.tostring(alert.update_alert(self.tree, "alert", "")).decode()
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path"/>
                        <alert id="alert1" path="/path1" description="nothing"/>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode()
        )

    def test_update_description(self):
        assert_xml_equal(
            '<alert id="alert" path="/path" description="desc"/>',
            etree.tostring(
                alert.update_alert(self.tree, "alert", None, "desc")
            ).decode()
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path" description="desc"/>
                        <alert id="alert1" path="/path1" description="nothing"/>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode()
        )

    def test_remove_description(self):
        assert_xml_equal(
            '<alert id="alert1" path="/path1"/>',
            etree.tostring(
                alert.update_alert(self.tree, "alert1", None, "")
            ).decode()
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path"/>
                        <alert id="alert1" path="/path1"/>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode()
        )

    def test_id_not_exists(self):
        assert_raise_library_error(
            lambda: alert.update_alert(self.tree, "alert0", "/test"),
            (
                severities.ERROR,
                report_codes.CIB_ALERT_NOT_FOUND,
                {"alert": "alert0"}
            )
        )


class RemoveAlertTest(TestCase):
    def setUp(self):
        self.tree = etree.XML(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path"/>
                        <alert id="alert-1" path="/next"/>
                    </alerts>
                </configuration>
            </cib>
            """
        )

    def test_success(self):
        alert.remove_alert(self.tree, "alert")
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert-1" path="/next"/>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode()
        )

    def test_not_existing_id(self):
        assert_raise_library_error(
            lambda: alert.remove_alert(self.tree, "not-existing-id"),
            (
                severities.ERROR,
                report_codes.CIB_ALERT_NOT_FOUND,
                {"alert": "not-existing-id"}
            )
        )


class AddRecipientTest(TestCase):
    def setUp(self):
        self.tree = etree.XML(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path">
                            <recipient id="alert-recipient" value="test_val"/>
                        </alert>
                    </alerts>
                </configuration>
            </cib>
            """
        )

    def test_success(self):
        assert_xml_equal(
            '<recipient id="alert-recipient-1" value="value1"/>',
            etree.tostring(
                alert.add_recipient(self.tree, "alert", "value1")
            ).decode()
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path">
                            <recipient id="alert-recipient" value="test_val"/>
                            <recipient id="alert-recipient-1" value="value1"/>
                        </alert>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode()
        )

    def test_recipient_exist(self):
        assert_raise_library_error(
            lambda: alert.add_recipient(self.tree, "alert", "test_val"),
            (
                severities.ERROR,
                report_codes.CIB_ALERT_RECIPIENT_ALREADY_EXISTS,
                {
                    "recipient": "test_val",
                    "alert": "alert"
                }
            )
        )

    def test_alert_not_exist(self):
        assert_raise_library_error(
            lambda: alert.add_recipient(self.tree, "alert1", "test_val"),
            (
                severities.ERROR,
                report_codes.CIB_ALERT_NOT_FOUND,
                {"alert": "alert1"}
            )
        )

    def test_with_description(self):
        assert_xml_equal(
            """
            <recipient
                id="alert-recipient-1"
                value="value1"
                description="desc"
            />
            """,
            etree.tostring(alert.add_recipient(
                self.tree, "alert", "value1", "desc"
            )).decode()
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path">
                            <recipient id="alert-recipient" value="test_val"/>
                            <recipient
                                id="alert-recipient-1"
                                value="value1"
                                description="desc"
                            />
                        </alert>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode()
        )


class UpdateRecipientTest(TestCase):
    def setUp(self):
        self.tree = etree.XML(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path">
                            <recipient id="alert-recipient" value="test_val"/>
                            <recipient
                                id="alert-recipient-1"
                                value="value1"
                                description="desc"
                            />
                        </alert>
                    </alerts>
                </configuration>
            </cib>
            """
        )

    def test_add_description(self):
        assert_xml_equal(
            """
            <recipient
                id="alert-recipient" value="test_val" description="description"
            />
            """,
            etree.tostring(alert.update_recipient(
                self.tree, "alert", "test_val", "description"
            )).decode()
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path">
                            <recipient
                                id="alert-recipient"
                                value="test_val"
                                description="description"
                            />
                            <recipient
                                id="alert-recipient-1"
                                value="value1"
                                description="desc"
                            />
                        </alert>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode()
        )

    def test_update_description(self):
        assert_xml_equal(
            """
            <recipient
                id="alert-recipient-1" value="value1" description="description"
            />
            """,
            etree.tostring(alert.update_recipient(
                self.tree, "alert", "value1", "description"
            )).decode()
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path">
                            <recipient id="alert-recipient" value="test_val"/>
                            <recipient
                                id="alert-recipient-1"
                                value="value1"
                                description="description"
                            />
                        </alert>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode()
        )

    def test_remove_description(self):
        assert_xml_equal(
            """
                <recipient id="alert-recipient-1" value="value1"/>
            """,
            etree.tostring(
               alert.update_recipient(self.tree, "alert", "value1", "")
            ).decode()
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path">
                            <recipient id="alert-recipient" value="test_val"/>
                            <recipient id="alert-recipient-1" value="value1"/>
                        </alert>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode()
        )

    def test_alert_not_exists(self):
        assert_raise_library_error(
            lambda: alert.update_recipient(self.tree, "alert1", "test_val", ""),
            (
                severities.ERROR,
                report_codes.CIB_ALERT_NOT_FOUND,
                {"alert": "alert1"}
            )
        )

    def test_recipient_not_exists(self):
        assert_raise_library_error(
            lambda: alert.update_recipient(self.tree, "alert", "unknown", ""),
            (
                severities.ERROR,
                report_codes.CIB_ALERT_RECIPIENT_NOT_FOUND,
                {
                    "alert": "alert",
                    "recipient": "unknown"
                }
            )
        )


class RemoveRecipientTest(TestCase):
    def setUp(self):
        self.tree = etree.XML(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path">
                            <recipient id="alert-recipient" value="test_val"/>
                            <recipient id="alert-recipient-2" value="val"/>
                        </alert>
                    </alerts>
                </configuration>
            </cib>
            """
        )

    def test_success(self):
        alert.remove_recipient(self.tree, "alert", "val")
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path">
                            <recipient id="alert-recipient" value="test_val"/>
                        </alert>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode()
        )

    def test_alert_not_exists(self):
        assert_raise_library_error(
            lambda: alert.remove_recipient(self.tree, "alert1", "test_val"),
            (
                severities.ERROR,
                report_codes.CIB_ALERT_NOT_FOUND,
                {"alert": "alert1"}
            )
        )

    def test_recipient_not_exists(self):
        assert_raise_library_error(
            lambda: alert.remove_recipient(self.tree, "alert", "unknown"),
            (
                severities.ERROR,
                report_codes.CIB_ALERT_RECIPIENT_NOT_FOUND,
                {
                    "alert": "alert",
                    "recipient": "unknown"
                }
            )
        )


class GetAllRecipientsTest(TestCase):
    def test_success(self):
        alert_obj = etree.XML(
            """
            <alert id="alert" path="/path">
                <recipient id="alert-recipient" value="test_val">
                    <instance_attributes>
                        <nvpair
                            id="nvset-name1-value1" name="name1" value="value1"
                        />
                        <nvpair
                            id="nvset-name2-value2" name="name2" value="value2"
                        />
                    </instance_attributes>
                    <meta_attributes>
                        <nvpair id="nvset-name3" name="name3"/>
                    </meta_attributes>
                </recipient>
                <recipient
                    id="alert-recipient-1" value="value1" description="desc"
                />
            </alert>
            """
        )
        self.assertEqual(
            [
                {
                    "id": "alert-recipient",
                    "value": "test_val",
                    "description": "",
                    "instance_attributes": [
                        {
                            "id": "nvset-name1-value1",
                            "name": "name1",
                            "value": "value1"
                        },
                        {
                            "id": "nvset-name2-value2",
                            "name": "name2",
                            "value": "value2"
                        }
                    ],
                    "meta_attributes": [
                        {
                            "id": "nvset-name3",
                            "name": "name3",
                            "value": ""
                        }
                    ]
                },
                {
                    "id": "alert-recipient-1",
                    "value": "value1",
                    "description": "desc",
                    "instance_attributes": [],
                    "meta_attributes": []
                }
            ],
            alert.get_all_recipients(alert_obj)
        )


class GetAllAlertsTest(TestCase):
    def test_success(self):
        alerts = etree.XML(
            """
<cib>
    <configuration>
        <alerts>
            <alert id="alert" path="/path">
                <recipient id="alert-recipient" value="test_val">
                    <instance_attributes>
                        <nvpair
                            id="instance_attributes-name1-value1"
                            name="name1"
                            value="value1"
                        />
                        <nvpair
                            id="instance_attributes-name2-value2"
                            name="name2"
                            value="value2"
                        />
                    </instance_attributes>
                    <meta_attributes>
                        <nvpair id="meta_attributes-name3" name="name3"/>
                    </meta_attributes>
                </recipient>
                <recipient
                    id="alert-recipient-1" value="value1" description="desc"
                />
            </alert>
            <alert id="alert1" path="/test/path" description="desc">
                <instance_attributes>
                    <nvpair
                        id="alert1-name1-value1" name="name1" value="value1"
                    />
                    <nvpair
                        id="alert1-name2-value2" name="name2" value="value2"
                    />
                </instance_attributes>
                <meta_attributes>
                    <nvpair id="alert1-name3" name="name3"/>
                </meta_attributes>
            </alert>
        </alerts>
    </configuration>
</cib>
            """
        )
        self.assertEqual(
            [
                {
                    "id": "alert",
                    "path": "/path",
                    "description": "",
                    "instance_attributes": [],
                    "meta_attributes": [],
                    "recipient_list": [
                        {
                            "id": "alert-recipient",
                            "value": "test_val",
                            "description": "",
                            "instance_attributes": [
                                {
                                    "id": "instance_attributes-name1-value1",
                                    "name": "name1",
                                    "value": "value1"
                                },
                                {
                                    "id": "instance_attributes-name2-value2",
                                    "name": "name2",
                                    "value": "value2"
                                }
                            ],
                            "meta_attributes": [
                                {
                                    "id": "meta_attributes-name3",
                                    "name": "name3",
                                    "value": ""
                                }
                            ]
                        },
                        {
                            "id": "alert-recipient-1",
                            "value": "value1",
                            "description": "desc",
                            "instance_attributes": [],
                            "meta_attributes": []
                        }
                    ]
                },
                {
                    "id": "alert1",
                    "path": "/test/path",
                    "description": "desc",
                    "instance_attributes": [
                        {
                            "id": "alert1-name1-value1",
                            "name": "name1",
                            "value": "value1"
                        },
                        {
                            "id": "alert1-name2-value2",
                            "name": "name2",
                            "value": "value2"
                        }
                    ],
                    "meta_attributes": [
                        {
                            "id": "alert1-name3",
                            "name": "name3",
                            "value": ""
                        }
                    ],
                    "recipient_list": []
                }
            ],
            alert.get_all_alerts(alerts)
        )
