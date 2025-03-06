from unittest import TestCase

from lxml import etree

from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.cib import alert
from pcs.lib.cib.tools import IdProvider

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
    assert_xml_equal,
)


class UpdateOptionalAttributeTest(TestCase):
    # pylint: disable=protected-access
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


class ValidateRecipientValueIsUniqueTest(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.alert = etree.Element("alert", id="alert-1")
        self.recipient = etree.SubElement(
            self.alert, "recipient", id="rec-1", value="value1"
        )

    def test_is_unique_no_duplicity_allowed(self):
        report_list = alert._validate_recipient_value_is_unique(
            self.alert, "value2"
        )
        assert_report_item_list_equal(report_list, [])

    def test_same_recipient_no_duplicity_allowed(self):
        report_list = alert._validate_recipient_value_is_unique(
            self.alert, "value1", recipient_id="rec-1"
        )
        assert_report_item_list_equal(report_list, [])

    def test_same_recipient_duplicity_allowed(self):
        report_list = alert._validate_recipient_value_is_unique(
            self.alert,
            "value1",
            recipient_id="rec-1",
            allow_duplicity=True,
        )
        assert_report_item_list_equal(report_list, [])

    def test_not_unique_no_duplicity_allowed(self):
        report_list = alert._validate_recipient_value_is_unique(
            self.alert, "value1"
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    report_codes.CIB_ALERT_RECIPIENT_ALREADY_EXISTS,
                    force_code=report_codes.FORCE,
                    alert="alert-1",
                    recipient="value1",
                )
            ],
        )

    def test_is_unique_duplicity_allowed(self):
        report_list = alert._validate_recipient_value_is_unique(
            self.alert, "value2", allow_duplicity=True
        )
        assert_report_item_list_equal(report_list, [])

    def test_not_unique_duplicity_allowed(self):
        report_list = alert._validate_recipient_value_is_unique(
            self.alert, "value1", allow_duplicity=True
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.warn(
                    report_codes.CIB_ALERT_RECIPIENT_ALREADY_EXISTS,
                    alert="alert-1",
                    recipient="value1",
                )
            ],
        )


class ValidateCreateAlert(TestCase):
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
        self.id_provider = IdProvider(self.tree)

    def test_empty_path(self):
        assert_report_item_list_equal(
            alert.validate_create_alert(self.id_provider, "", "alert2"),
            [
                fixture.error(
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    option_names=["path"],
                    option_type=None,
                )
            ],
        )

    def test_invalid_id(self):
        assert_report_item_list_equal(
            alert.validate_create_alert(self.id_provider, "/path", "1alert"),
            [
                fixture.error(
                    report_codes.INVALID_ID_BAD_CHAR,
                    id="1alert",
                    id_description="alert-id",
                    invalid_character="1",
                    is_first_char=True,
                )
            ],
        )

    def test_id_exists(self):
        assert_report_item_list_equal(
            alert.validate_create_alert(self.id_provider, "/path", "alert"),
            [
                fixture.error(
                    report_codes.ID_ALREADY_EXISTS,
                    id="alert",
                ),
            ],
        )


class CreateAlert(TestCase):
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
        self.id_provider = IdProvider(self.tree)

    def test_no_alerts(self):
        # pylint: disable=no-self-use
        tree = etree.XML(
            """
            <cib>
                <configuration/>
            </cib>
            """
        )
        id_provider = IdProvider(tree)
        assert_xml_equal(
            '<alert id="my-alert" path="/test/path"/>',
            etree.tostring(
                alert.create_alert(tree, id_provider, "/test/path", "my-alert")
            ).decode(),
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
            etree.tostring(tree).decode(),
        )

    def test_alerts_exists(self):
        assert_xml_equal(
            '<alert id="my-alert" path="/test/path"/>',
            etree.tostring(
                alert.create_alert(
                    self.tree, self.id_provider, "/test/path", "my-alert"
                )
            ).decode(),
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
            etree.tostring(self.tree).decode(),
        )

    def test_alerts_exists_with_description(self):
        assert_xml_equal(
            '<alert id="my-alert" path="/test/path" description="nothing"/>',
            etree.tostring(
                alert.create_alert(
                    self.tree,
                    self.id_provider,
                    "/test/path",
                    "my-alert",
                    "nothing",
                )
            ).decode(),
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
            etree.tostring(self.tree).decode(),
        )

    def test_no_id(self):
        assert_xml_equal(
            '<alert id="alert-1" path="/test/path"/>',
            etree.tostring(
                alert.create_alert(self.tree, self.id_provider, "/test/path")
            ).decode(),
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
            etree.tostring(self.tree).decode(),
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
            ).decode(),
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
            etree.tostring(self.tree).decode(),
        )

    def test_remove_path(self):
        assert_xml_equal(
            '<alert id="alert" path="/path"/>',
            etree.tostring(alert.update_alert(self.tree, "alert", "")).decode(),
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
            etree.tostring(self.tree).decode(),
        )

    def test_update_description(self):
        assert_xml_equal(
            '<alert id="alert" path="/path" description="desc"/>',
            etree.tostring(
                alert.update_alert(self.tree, "alert", None, "desc")
            ).decode(),
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
            etree.tostring(self.tree).decode(),
        )

    def test_remove_description(self):
        assert_xml_equal(
            '<alert id="alert1" path="/path1"/>',
            etree.tostring(
                alert.update_alert(self.tree, "alert1", None, "")
            ).decode(),
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
            etree.tostring(self.tree).decode(),
        )

    def test_id_not_exists(self):
        assert_raise_library_error(
            lambda: alert.update_alert(self.tree, "alert0", "/test"),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "alert0",
                    "expected_types": ["alert"],
                    "context_type": "alerts",
                    "context_id": "",
                },
                None,
            ),
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
            etree.tostring(self.tree).decode(),
        )

    def test_not_existing_id(self):
        assert_raise_library_error(
            lambda: alert.remove_alert(self.tree, "not-existing-id"),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "not-existing-id",
                    "expected_types": ["alert"],
                    "context_type": "alerts",
                    "context_id": "",
                },
                None,
            ),
        )


class ValidateAddRecipientTest(TestCase):
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
        self.id_provider = IdProvider(self.tree)
        self.alert_el = self.tree.xpath(".//alert[@id='alert']")[0]

    def test_id_exists(self):
        report_list = alert.validate_add_recipient(
            self.id_provider,
            self.alert_el,
            "value1",
            "alert-recipient",
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    report_codes.ID_ALREADY_EXISTS,
                    id="alert-recipient",
                ),
            ],
        )

    def test_duplicity_of_value_not_allowed(self):
        report_list = alert.validate_add_recipient(
            self.id_provider,
            self.alert_el,
            "test_val",
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    report_codes.CIB_ALERT_RECIPIENT_ALREADY_EXISTS,
                    force_code=report_codes.FORCE,
                    alert="alert",
                    recipient="test_val",
                )
            ],
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
        self.id_provider = IdProvider(self.tree)
        self.alert_el = self.tree.xpath(".//alert[@id='alert']")[0]

    def test_with_id(self):
        assert_xml_equal(
            '<recipient id="my-recipient" value="value1"/>',
            etree.tostring(
                alert.add_recipient(
                    self.id_provider,
                    self.alert_el,
                    "value1",
                    "my-recipient",
                )
            ).decode(),
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path">
                            <recipient id="alert-recipient" value="test_val"/>
                            <recipient id="my-recipient" value="value1"/>
                        </alert>
                    </alerts>
                </configuration>
            </cib>
            """,
            etree.tostring(self.tree).decode(),
        )

    def test_without_id(self):
        assert_xml_equal(
            '<recipient id="alert-recipient-1" value="value1"/>',
            etree.tostring(
                alert.add_recipient(
                    self.id_provider,
                    self.alert_el,
                    "value1",
                )
            ).decode(),
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
            etree.tostring(self.tree).decode(),
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
            etree.tostring(
                alert.add_recipient(
                    self.id_provider,
                    self.alert_el,
                    "value1",
                    description="desc",
                )
            ).decode(),
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
            etree.tostring(self.tree).decode(),
        )


class ValideteUpdateRecipientTest(TestCase):
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
        self.recipient_el = self.tree.xpath(
            ".//recipient[@id='alert-recipient']"
        )[0]

    def test_update_same_value_no_duplicity_allowed(self):
        report_list = alert.validate_update_recipient(
            self.recipient_el,
            recipient_value="test_val",
        )
        assert_report_item_list_equal(report_list, [])

    def test_duplicity_of_value_not_allowed(self):
        report_list = alert.validate_update_recipient(
            self.recipient_el,
            "value1",
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    report_codes.CIB_ALERT_RECIPIENT_ALREADY_EXISTS,
                    force_code=report_codes.FORCE,
                    alert="alert",
                    recipient="value1",
                )
            ],
        )

    def test_duplicity_of_value_allowed(self):
        report_list = alert.validate_update_recipient(
            self.recipient_el,
            "value1",
            allow_same_value=True,
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.warn(
                    report_codes.CIB_ALERT_RECIPIENT_ALREADY_EXISTS,
                    alert="alert",
                    recipient="value1",
                )
            ],
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
        self.recipient_el = self.tree.xpath(
            ".//recipient[@id='alert-recipient']"
        )[0]
        self.recipient1_el = self.tree.xpath(
            ".//recipient[@id='alert-recipient-1']"
        )[0]

    def test_update_value(self):
        assert_xml_equal(
            """
            <recipient id="alert-recipient" value="new_val"/>
            """,
            etree.tostring(
                alert.update_recipient(
                    self.recipient_el,
                    recipient_value="new_val",
                )
            ).decode(),
        )
        assert_xml_equal(
            """
            <cib>
                <configuration>
                    <alerts>
                        <alert id="alert" path="/path">
                            <recipient id="alert-recipient" value="new_val"/>
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
            etree.tostring(self.tree).decode(),
        )

    def test_add_description(self):
        assert_xml_equal(
            """
            <recipient
                id="alert-recipient" value="test_val" description="description"
            />
            """,
            etree.tostring(
                alert.update_recipient(
                    self.recipient_el,
                    description="description",
                )
            ).decode(),
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
            etree.tostring(self.tree).decode(),
        )

    def test_update_description(self):
        assert_xml_equal(
            """
            <recipient
                id="alert-recipient-1" value="value1" description="description"
            />
            """,
            etree.tostring(
                alert.update_recipient(
                    self.recipient1_el,
                    description="description",
                )
            ).decode(),
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
            etree.tostring(self.tree).decode(),
        )

    def test_remove_description(self):
        assert_xml_equal(
            """
                <recipient id="alert-recipient-1" value="value1"/>
            """,
            etree.tostring(
                alert.update_recipient(
                    self.recipient1_el,
                    description="",
                )
            ).decode(),
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
            etree.tostring(self.tree).decode(),
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
        alert.remove_recipient(self.tree, "alert-recipient-2")
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
            etree.tostring(self.tree).decode(),
        )

    def test_recipient_not_exists(self):
        assert_raise_library_error(
            lambda: alert.remove_recipient(self.tree, "recipient"),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "recipient",
                    "expected_types": ["recipient"],
                    "context_type": "alerts",
                    "context_id": "",
                },
                None,
            ),
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
                            "value": "value1",
                        },
                        {
                            "id": "nvset-name2-value2",
                            "name": "name2",
                            "value": "value2",
                        },
                    ],
                    "meta_attributes": [
                        {"id": "nvset-name3", "name": "name3", "value": None}
                    ],
                },
                {
                    "id": "alert-recipient-1",
                    "value": "value1",
                    "description": "desc",
                    "instance_attributes": [],
                    "meta_attributes": [],
                },
            ],
            alert.get_all_recipients(alert_obj),
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
                                    "value": "value1",
                                },
                                {
                                    "id": "instance_attributes-name2-value2",
                                    "name": "name2",
                                    "value": "value2",
                                },
                            ],
                            "meta_attributes": [
                                {
                                    "id": "meta_attributes-name3",
                                    "name": "name3",
                                    "value": None,
                                }
                            ],
                        },
                        {
                            "id": "alert-recipient-1",
                            "value": "value1",
                            "description": "desc",
                            "instance_attributes": [],
                            "meta_attributes": [],
                        },
                    ],
                },
                {
                    "id": "alert1",
                    "path": "/test/path",
                    "description": "desc",
                    "instance_attributes": [
                        {
                            "id": "alert1-name1-value1",
                            "name": "name1",
                            "value": "value1",
                        },
                        {
                            "id": "alert1-name2-value2",
                            "name": "name2",
                            "value": "value2",
                        },
                    ],
                    "meta_attributes": [
                        {"id": "alert1-name3", "name": "name3", "value": None}
                    ],
                    "recipient_list": [],
                },
            ],
            alert.get_all_alerts(alerts),
        )
