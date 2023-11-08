from functools import partial
from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs.common import const
from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.cib.constraint import ticket

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_xml_equal,
)
from pcs_test.tools.custom_mock import MockLibraryReportProcessor


class IsTicketConstraint(TestCase):
    def test_ticket_constraint_true(self):
        self.assertTrue(
            ticket.is_ticket_constraint(etree.Element("rsc_ticket"))
        )

    def test_ticket_constraint_false(self):
        self.assertFalse(ticket.is_ticket_constraint(etree.Element("ticket")))


@mock.patch(
    "pcs.lib.cib.constraint.ticket.tools.are_new_role_names_supported",
    lambda _: True,
)
@mock.patch("pcs.lib.cib.constraint.ticket.tools.check_new_id_applicable")
class PrepareOptionsPlainTest(TestCase):
    def setUp(self):
        self.cib = "cib"
        self.report_processor = MockLibraryReportProcessor(debug=False)
        self.prepare = partial(
            ticket.prepare_options_plain, self.cib, self.report_processor
        )

    @mock.patch("pcs.lib.cib.constraint.ticket._create_id")
    def test_prepare_correct_options(self, mock_create_id, _):
        mock_create_id.return_value = "generated_id"
        role = str(const.PCMK_ROLE_PROMOTED_LEGACY).lower()
        self.assertEqual(
            {
                "id": "generated_id",
                "loss-policy": "fence",
                "rsc": "resourceA",
                "rsc-role": const.PCMK_ROLE_PROMOTED_PRIMARY,
                "ticket": "ticket-key",
            },
            self.prepare(
                {"loss-policy": "fence", "rsc-role": role},
                "ticket-key",
                "resourceA",
            ),
        )
        self.report_processor.assert_reports(
            [
                fixture.deprecation(
                    report_codes.DEPRECATED_OPTION_VALUE,
                    option_name="role",
                    deprecated_value=role,
                    replaced_by=const.PCMK_ROLE_PROMOTED,
                )
            ]
        )

    @mock.patch("pcs.lib.cib.constraint.ticket._create_id")
    def test_does_not_include_role_if_not_presented(self, mock_create_id, _):
        mock_create_id.return_value = "generated_id"
        self.assertEqual(
            {
                "id": "generated_id",
                "loss-policy": "fence",
                "rsc": "resourceA",
                "ticket": "ticket-key",
            },
            self.prepare(
                {"loss-policy": "fence", "rsc-role": ""},
                "ticket-key",
                "resourceA",
            ),
        )
        self.report_processor.assert_reports([])

    def test_refuse_unknown_attributes(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {"unknown": "nonsense", "rsc-role": "promoted"},
                "ticket-key",
                "resourceA",
            )
        )
        self.report_processor.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["unknown"],
                    option_type=None,
                    allowed=[
                        "id",
                        "loss-policy",
                        "rsc-role",
                    ],
                    allowed_patterns=[],
                )
            ]
        )

    def test_refuse_bad_role(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {"id": "id", "rsc-role": "bad_role"}, "ticket-key", "resourceA"
            ),
        )
        self.report_processor.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    allowed_values=const.PCMK_ROLES,
                    option_value="bad_role",
                    option_name="role",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_refuse_missing_ticket(self, _):
        role = str(const.PCMK_ROLE_UNPROMOTED_LEGACY).lower()
        assert_raise_library_error(
            lambda: self.prepare(
                {"id": "id", "rsc-role": role}, "", "resourceA"
            ),
        )
        self.report_processor.assert_reports(
            [
                fixture.error(
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    option_names=["ticket"],
                    option_type=None,
                ),
                fixture.deprecation(
                    report_codes.DEPRECATED_OPTION_VALUE,
                    option_name="role",
                    deprecated_value=role,
                    replaced_by=const.PCMK_ROLE_UNPROMOTED,
                ),
            ]
        )

    def test_refuse_bad_ticket(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {
                    "id": "id",
                },
                "bad_ticket",
                "resourceA",
            ),
        )
        self.report_processor.assert_reports(
            [
                fixture.error(
                    report_codes.BOOTH_TICKET_NAME_INVALID,
                    ticket_name="bad_ticket",
                ),
            ]
        )

    def test_refuse_missing_resource_id(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {"id": "id", "rsc-role": const.PCMK_ROLE_PROMOTED},
                "ticket-key",
                "",
            ),
        )
        self.report_processor.assert_reports(
            [
                fixture.error(
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    option_names=["rsc"],
                    option_type=None,
                ),
            ]
        )

    def test_refuse_unknown_lost_policy(self, mock_check_new_id_applicable):
        del mock_check_new_id_applicable
        assert_raise_library_error(
            lambda: self.prepare(
                {"loss-policy": "unknown", "id": "id"},
                "ticket-key",
                "resourceA",
            ),
        )
        self.report_processor.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    allowed_values=("fence", "stop", "freeze", "demote"),
                    option_value="unknown",
                    option_name="loss-policy",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    @mock.patch("pcs.lib.cib.constraint.ticket._create_id")
    def test_complete_id(self, mock_create_id, _):
        mock_create_id.return_value = "generated_id"
        options = {
            "loss-policy": "freeze",
            "rsc-role": const.PCMK_ROLE_PROMOTED,
        }
        ticket_key = "ticket-key"
        resource_id = "resourceA"
        expected_options = options.copy()
        expected_options.update(
            {
                "id": "generated_id",
                "rsc": resource_id,
                "rsc-role": const.PCMK_ROLE_PROMOTED_PRIMARY,
                "ticket": ticket_key,
            }
        )
        self.assertEqual(
            expected_options,
            self.prepare(
                options,
                ticket_key,
                resource_id,
            ),
        )
        mock_create_id.assert_called_once_with(
            self.cib,
            ticket_key,
            resource_id,
            const.PCMK_ROLE_PROMOTED_PRIMARY,
        )


# Patch check_new_id_applicable is always desired when working with
# prepare_options_with_set. Patched function raises when id not applicable
# and do nothing when applicable - in this case tests do no actions with it
@mock.patch("pcs.lib.cib.constraint.ticket.tools.check_new_id_applicable")
class PrepareOptionsWithSetTest(TestCase):
    def setUp(self):
        self.cib = "cib"
        self.resource_set_list = "resource_set_list"
        self.prepare = lambda options: ticket.prepare_options_with_set(
            self.cib,
            options,
            self.resource_set_list,
        )

    @mock.patch("pcs.lib.cib.constraint.ticket.constraint.create_id")
    def test_complete_id(self, mock_create_id, _):
        mock_create_id.return_value = "generated_id"
        options = {"loss-policy": "freeze", "ticket": "T"}
        expected_options = options.copy()
        expected_options.update({"id": "generated_id"})
        self.assertEqual(expected_options, self.prepare(options))
        mock_create_id.assert_called_once_with(
            self.cib, "ticket", self.resource_set_list
        )

    def test_refuse_invalid_id(self, mock_check_new_id_applicable):
        class SomeException(Exception):
            pass

        mock_check_new_id_applicable.side_effect = SomeException()
        invalid_id = "invalid_id"
        self.assertRaises(
            SomeException,
            lambda: self.prepare(
                {
                    "loss-policy": "freeze",
                    "ticket": "T",
                    "id": invalid_id,
                }
            ),
        )
        mock_check_new_id_applicable.assert_called_once_with(
            self.cib, ticket.DESCRIPTION, invalid_id
        )

    def test_refuse_unknown_lost_policy(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {
                    "loss-policy": "unknown",
                    "ticket": "T",
                    "id": "id",
                }
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "allowed_values": ("fence", "stop", "freeze", "demote"),
                    "option_value": "unknown",
                    "option_name": "loss-policy",
                    "cannot_be_empty": False,
                    "forbidden_characters": None,
                },
            ),
        )

    def test_refuse_missing_ticket(self, _):
        assert_raise_library_error(
            lambda: self.prepare({"loss-policy": "stop", "id": "id"}),
            (
                severities.ERROR,
                report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                {"option_names": ["ticket"], "option_type": None},
            ),
        )

    def test_refuse_empty_ticket(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {"loss-policy": "stop", "id": "id", "ticket": " "}
            ),
            (
                severities.ERROR,
                report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                {"option_names": ["ticket"], "option_type": None},
            ),
        )

    def test_refuse_bad_ticket(self, _):
        assert_raise_library_error(
            lambda: self.prepare({"id": "id", "ticket": "bad_ticket"}),
            (
                severities.ERROR,
                report_codes.BOOTH_TICKET_NAME_INVALID,
                {"ticket_name": "bad_ticket"},
            ),
        )


class Element:
    def __init__(self, attrib):
        self.attrib = attrib

    def update(self, attrib):
        self.attrib.update(attrib)
        return self


class AreDuplicatePlain(TestCase):
    def setUp(self):
        self.first = Element(
            {
                "ticket": "ticket-key",
                "rsc": "resourceA",
                "rsc-role": const.PCMK_ROLE_PROMOTED_LEGACY,
            }
        )
        self.second = Element(
            {
                "ticket": "ticket-key",
                "rsc": "resourceA",
                "rsc-role": const.PCMK_ROLE_PROMOTED_LEGACY,
            }
        )

    def test_returns_true_for_duplicate_elements(self):
        self.assertTrue(
            ticket.get_duplicit_checker_callback(False)(self.first, self.second)
        )

    def test_returns_false_for_different_ticket(self):
        self.assertFalse(
            ticket.get_duplicit_checker_callback(False)(
                self.first, self.second.update({"ticket": "X"})
            )
        )

    def test_returns_false_for_different_resource(self):
        self.assertFalse(
            ticket.get_duplicit_checker_callback(False)(
                self.first, self.second.update({"rsc": "Y"})
            )
        )

    def test_returns_false_for_different_role(self):
        self.assertFalse(
            ticket.get_duplicit_checker_callback(False)(
                self.first, self.second.update({"rsc-role": "Z"})
            )
        )

    def test_returns_false_for_different_elements(self):
        self.second.update({"ticket": "X", "rsc": "Y", "rsc-role": "Z"})
        self.assertFalse(
            ticket.get_duplicit_checker_callback(False)(self.first, self.second)
        )

    def test_returns_true_for_equivalent_new_role(self):
        self.assertTrue(
            ticket.get_duplicit_checker_callback(False)(
                self.first,
                self.second.update({"rsc-role": const.PCMK_ROLE_PROMOTED}),
            )
        )

    def test_returns_true_for_equivalent_new_role_new_roles_supported(self):
        self.assertTrue(
            ticket.get_duplicit_checker_callback(True)(
                self.first,
                self.second.update({"rsc-role": const.PCMK_ROLE_PROMOTED}),
            )
        )


@mock.patch(
    "pcs.lib.cib.constraint.ticket.constraint.have_duplicate_resource_sets"
)
class AreDuplicateWithResourceSet(TestCase):
    def test_returns_true_for_duplicate_elements(
        self, mock_have_duplicate_resource_sets
    ):
        mock_have_duplicate_resource_sets.return_value = True
        self.assertTrue(
            ticket.are_duplicate_with_resource_set(
                Element({"ticket": "ticket-key"}),
                Element({"ticket": "ticket-key"}),
            )
        )

    def test_returns_false_for_different_elements(
        self, mock_have_duplicate_resource_sets
    ):
        mock_have_duplicate_resource_sets.return_value = True
        self.assertFalse(
            ticket.are_duplicate_with_resource_set(
                Element({"ticket": "ticket-key"}),
                Element({"ticket": "X"}),
            )
        )


class RemovePlainTest(TestCase):
    def test_remove_tickets_constraints_for_resource(self):
        constraint_section = etree.fromstring(
            """
            <constraints>
                <rsc_ticket id="t1" ticket="tA" rsc="rA"/>
                <rsc_ticket id="t2" ticket="tA" rsc="rB"/>
                <rsc_ticket id="t3" ticket="tA" rsc="rA"/>
                <rsc_ticket id="t4" ticket="tB" rsc="rA"/>
                <rsc_ticket id="t5" ticket="tB" rsc="rB"/>
            </constraints>
        """
        )

        self.assertTrue(
            ticket.remove_plain(
                constraint_section,
                ticket_key="tA",
                resource_id="rA",
            )
        )

        assert_xml_equal(
            etree.tostring(constraint_section).decode(),
            """
            <constraints>
                <rsc_ticket id="t2" ticket="tA" rsc="rB"/>
                <rsc_ticket id="t4" ticket="tB" rsc="rA"/>
                <rsc_ticket id="t5" ticket="tB" rsc="rB"/>
            </constraints>
        """,
        )

    def test_remove_nothing_when_no_matching_found(self):
        constraint_section = etree.fromstring(
            """
            <constraints>
                <rsc_ticket id="t2" ticket="tA" rsc="rB"/>
                <rsc_ticket id="t4" ticket="tB" rsc="rA"/>
                <rsc_ticket id="t5" ticket="tB" rsc="rB"/>
            </constraints>
        """
        )

        self.assertFalse(
            ticket.remove_plain(
                constraint_section,
                ticket_key="tA",
                resource_id="rA",
            )
        )

        assert_xml_equal(
            etree.tostring(constraint_section).decode(),
            """
            <constraints>
                <rsc_ticket id="t2" ticket="tA" rsc="rB"/>
                <rsc_ticket id="t4" ticket="tB" rsc="rA"/>
                <rsc_ticket id="t5" ticket="tB" rsc="rB"/>
            </constraints>
        """,
        )


class RemoveWithSetTest(TestCase):
    def test_remove_resource_references_and_empty_remaining_parents(self):
        constraint_section = etree.fromstring(
            """
            <constraints>
                <rsc_ticket id="t1" ticket="tA">
                    <resource_set id="rs1">
                        <resource_ref id="rA"/>
                    </resource_set>
                    <resource_set id="rs2">
                        <resource_ref id="rA"/>
                    </resource_set>
                </rsc_ticket>

                <rsc_ticket id="t2" ticket="tA">
                    <resource_set id="rs3">
                        <resource_ref id="rA"/>
                        <resource_ref id="rB"/>
                    </resource_set>
                    <resource_set id="rs4">
                        <resource_ref id="rA"/>
                    </resource_set>
                </rsc_ticket>

                <rsc_ticket id="t3" ticket="tB">
                    <resource_set id="rs5">
                        <resource_ref id="rA"/>
                    </resource_set>
                </rsc_ticket>
            </constraints>
        """
        )

        self.assertTrue(
            ticket.remove_with_resource_set(
                constraint_section, ticket_key="tA", resource_id="rA"
            )
        )

        assert_xml_equal(
            """
                <constraints>
                    <rsc_ticket id="t2" ticket="tA">
                        <resource_set id="rs3">
                            <resource_ref id="rB"/>
                        </resource_set>
                    </rsc_ticket>

                    <rsc_ticket id="t3" ticket="tB">
                        <resource_set id="rs5">
                            <resource_ref id="rA"/>
                        </resource_set>
                    </rsc_ticket>
                </constraints>
            """,
            etree.tostring(constraint_section).decode(),
        )

    def test_remove_nothing_when_no_matching_found(self):
        constraint_section = etree.fromstring(
            """
                <constraints>
                    <rsc_ticket id="t2" ticket="tA">
                        <resource_set id="rs3">
                            <resource_ref id="rB"/>
                        </resource_set>
                    </rsc_ticket>

                    <rsc_ticket id="t3" ticket="tB">
                        <resource_set id="rs5">
                            <resource_ref id="rA"/>
                        </resource_set>
                    </rsc_ticket>
                </constraints>
        """
        )
        self.assertFalse(
            ticket.remove_with_resource_set(
                constraint_section, ticket_key="tA", resource_id="rA"
            )
        )
