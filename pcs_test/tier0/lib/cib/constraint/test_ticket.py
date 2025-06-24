from unittest import TestCase, mock

from lxml import etree

from pcs.common import const, reports
from pcs.lib.cib.constraint import ticket
from pcs.lib.cib.tools import IdProvider, Version

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs_test.tools.xml import etree_to_str, str_to_etree


class IsTicketConstraint(TestCase):
    def test_ticket_constraint_true(self):
        self.assertTrue(
            ticket.is_ticket_constraint(etree.Element("rsc_ticket"))
        )

    def test_ticket_constraint_false(self):
        self.assertFalse(ticket.is_ticket_constraint(etree.Element("ticket")))


class ValidateCreatePlain(TestCase):
    def setUp(self):
        cib = str_to_etree("""
            <resources>
                <primitive id="R">
                    <meta_attributes id="R-meta" />
                </primitive>
                <clone id="C">
                    <primitive id="CR" />
                </clone>
            </resources>
        """)
        self.el_primitive = cib.xpath(".//*[@id='R']")[0]
        self.el_meta = cib.xpath(".//*[@id='R-meta']")[0]
        self.el_clone = cib.xpath(".//*[@id='C']")[0]
        self.el_cloned_primitive = cib.xpath(".//*[@id='CR']")[0]
        self.id_provider = IdProvider(cib)

    def test_resource_not_a_resource(self):
        assert_report_item_list_equal(
            ticket.validate_create_plain(
                self.id_provider, "T", self.el_meta, {}, False
            ),
            [
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="R-meta",
                    expected_types=[
                        "bundle",
                        "clone",
                        "group",
                        "master",
                        "primitive",
                    ],
                    current_type="meta_attributes",
                ),
            ],
        )

    def test_resource_in_a_clone(self):
        assert_report_item_list_equal(
            ticket.validate_create_plain(
                self.id_provider, "T", self.el_cloned_primitive, {}, False
            ),
            [
                fixture.error(
                    reports.codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
                    force_code=reports.codes.FORCE,
                    resource_id="CR",
                    parent_type="clone",
                    parent_id="C",
                ),
            ],
        )

    def test_resource_in_a_clone_forced(self):
        assert_report_item_list_equal(
            ticket.validate_create_plain(
                self.id_provider, "T", self.el_cloned_primitive, {}, True
            ),
            [
                fixture.warn(
                    reports.codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
                    resource_id="CR",
                    parent_type="clone",
                    parent_id="C",
                ),
            ],
        )

    def test_clone(self):
        assert_report_item_list_equal(
            ticket.validate_create_plain(
                self.id_provider, "T", self.el_clone, {}, False
            ),
            [],
        )

    def test_ticket_missing(self):
        assert_report_item_list_equal(
            ticket.validate_create_plain(
                self.id_provider, "", self.el_primitive, {}, False
            ),
            [
                fixture.error(
                    reports.codes.REQUIRED_OPTIONS_ARE_MISSING,
                    option_names=["ticket"],
                    option_type=None,
                )
            ],
        )

    def test_ticket_not_valid(self):
        assert_report_item_list_equal(
            ticket.validate_create_plain(
                self.id_provider, "my_ticket", self.el_primitive, {}, False
            ),
            [
                fixture.error(
                    reports.codes.BOOTH_TICKET_NAME_INVALID,
                    ticket_name="my_ticket",
                )
            ],
        )

    def test_id_not_valid(self):
        assert_report_item_list_equal(
            ticket.validate_create_plain(
                self.id_provider, "T", self.el_primitive, {"id": "123"}, False
            ),
            [
                fixture.error(
                    reports.codes.INVALID_ID_BAD_CHAR,
                    id="123",
                    id_description="constraint id",
                    invalid_character="1",
                    is_first_char=True,
                )
            ],
        )

    def test_id_already_used(self):
        assert_report_item_list_equal(
            ticket.validate_create_plain(
                self.id_provider, "T", self.el_primitive, {"id": "R"}, False
            ),
            [
                fixture.error(
                    reports.codes.ID_ALREADY_EXISTS,
                    id="R",
                )
            ],
        )

    def test_role_not_valid(self):
        assert_report_item_list_equal(
            ticket.validate_create_plain(
                self.id_provider,
                "T",
                self.el_primitive,
                {"rsc-role": "bad"},
                False,
            ),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="role",
                    option_value="bad",
                    allowed_values=(
                        const.PCMK_ROLE_STOPPED,
                        const.PCMK_ROLE_STARTED,
                        const.PCMK_ROLE_PROMOTED,
                        const.PCMK_ROLE_UNPROMOTED,
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_role_legacy(self):
        assert_report_item_list_equal(
            ticket.validate_create_plain(
                self.id_provider,
                "T",
                self.el_primitive,
                {"rsc-role": const.PCMK_ROLE_PROMOTED_LEGACY},
                False,
            ),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="role",
                    option_value=const.PCMK_ROLE_PROMOTED_LEGACY,
                    allowed_values=(
                        const.PCMK_ROLE_STOPPED,
                        const.PCMK_ROLE_STARTED,
                        const.PCMK_ROLE_PROMOTED,
                        const.PCMK_ROLE_UNPROMOTED,
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_loss_policy_not_valid(self):
        assert_report_item_list_equal(
            ticket.validate_create_plain(
                self.id_provider,
                "T",
                self.el_primitive,
                {"loss-policy": "bad"},
                False,
            ),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="loss-policy",
                    option_value="bad",
                    allowed_values=("fence", "stop", "freeze", "demote"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_option_names(self):
        assert_report_item_list_equal(
            ticket.validate_create_plain(
                self.id_provider,
                "T",
                self.el_primitive,
                {
                    "id": "const",
                    "loss-policy": "stop",
                    "rsc-role": const.PCMK_ROLE_PROMOTED,
                    "unknown": "option",
                },
                False,
            ),
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["unknown"],
                    allowed=["id", "loss-policy", "rsc-role"],
                    option_type=None,
                    allowed_patterns=[],
                ),
            ],
        )


class CreatePlain(TestCase):
    def setUp(self):
        cib = str_to_etree(
            """
            <cib>
                <resources>
                    <primitive id="resource1" />
                </resources>
                <constraints />
            </cib>
            """
        )
        self.el_constraints = cib.find("constraints")
        self.id_provider = IdProvider(cib)

    def test_minimal_options(self):
        ticket.create_plain(
            self.el_constraints,
            self.id_provider,
            Version(3, 8, 0),
            "ticket1",
            "resource1",
            {},
        )
        assert_xml_equal(
            """
            <constraints>
                <rsc_ticket id="ticket-ticket1-resource1" ticket="ticket1"
                    rsc="resource1"
                />
            </constraints>
            """,
            etree_to_str(self.el_constraints),
        )

    def test_all_options(self):
        ticket.create_plain(
            self.el_constraints,
            self.id_provider,
            Version(3, 8, 0),
            "ticket1",
            "resource1",
            {
                "id": "my-id",
                "loss-policy": "freeze",
                "rsc-role": const.PCMK_ROLE_UNPROMOTED,
            },
        )
        assert_xml_equal(
            """
            <constraints>
                <rsc_ticket id="my-id" loss-policy="freeze" rsc="resource1"
                    rsc-role="Unpromoted" ticket="ticket1"
                />
            </constraints>
            """,
            etree_to_str(self.el_constraints),
        )

    def test_build_id_with_role(self):
        ticket.create_plain(
            self.el_constraints,
            self.id_provider,
            Version(3, 8, 0),
            "ticket1",
            "resource1",
            {"rsc-role": const.PCMK_ROLE_PROMOTED},
        )
        assert_xml_equal(
            """
            <constraints>
                <rsc_ticket id="ticket-ticket1-resource1-{role}"
                    ticket="ticket1" rsc="resource1" rsc-role="{role}"
                />
            </constraints>
            """.format(role=const.PCMK_ROLE_PROMOTED),
            etree_to_str(self.el_constraints),
        )

    def test_build_id_with_role_legacy(self):
        ticket.create_plain(
            self.el_constraints,
            self.id_provider,
            Version(3, 6, 0),
            "ticket1",
            "resource1",
            {"rsc-role": const.PCMK_ROLE_PROMOTED},
        )
        assert_xml_equal(
            """
            <constraints>
                <rsc_ticket id="ticket-ticket1-resource1-{role}"
                    ticket="ticket1" rsc="resource1" rsc-role="{role}"
                />
            </constraints>
            """.format(role=const.PCMK_ROLE_PROMOTED_LEGACY),
            etree_to_str(self.el_constraints),
        )


# Patch check_new_id_applicable is always desired when working with
# prepare_options_with_set. Patched function raises when id not applicable
# and do nothing when applicable - in this case tests do no actions with it
@mock.patch("pcs.lib.cib.constraint.ticket.check_new_id_applicable")
class PrepareOptionsWithSetTest(TestCase):
    def setUp(self):
        self.cib = "cib"
        self.resource_set_list = "resource_set_list"
        self.prepare = lambda options: ticket.prepare_options_with_set(
            self.cib,
            options,
            self.resource_set_list,
        )

    @mock.patch("pcs.lib.cib.constraint.ticket.create_id")
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
            self.cib, "constraint id", invalid_id
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
            fixture.error(
                reports.codes.INVALID_OPTION_VALUE,
                allowed_values=("fence", "stop", "freeze", "demote"),
                option_value="unknown",
                option_name="loss-policy",
                cannot_be_empty=False,
                forbidden_characters=None,
            ),
        )

    def test_refuse_missing_ticket(self, _):
        assert_raise_library_error(
            lambda: self.prepare({"loss-policy": "stop", "id": "id"}),
            fixture.error(
                reports.codes.REQUIRED_OPTIONS_ARE_MISSING,
                option_names=["ticket"],
                option_type=None,
            ),
        )

    def test_refuse_empty_ticket(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {"loss-policy": "stop", "id": "id", "ticket": " "}
            ),
            fixture.error(
                reports.codes.REQUIRED_OPTIONS_ARE_MISSING,
                option_names=["ticket"],
                option_type=None,
            ),
        )

    def test_refuse_bad_ticket(self, _):
        assert_raise_library_error(
            lambda: self.prepare({"id": "id", "ticket": "bad_ticket"}),
            fixture.error(
                reports.codes.BOOTH_TICKET_NAME_INVALID,
                ticket_name="bad_ticket",
            ),
        )


class DuplicatesCheckerTicketPlain(TestCase):
    cib = etree.fromstring(
        """
        <constraints>
            <rsc_ticket id="C1" ticket="T1" rsc="R1" />
            <rsc_ticket id="C2" ticket="T1" rsc="R1" />
            <rsc_ticket id="C3" ticket="T1" rsc="R1" rsc-role="Master" />
            <rsc_ticket id="C4" ticket="T1" rsc="R1" rsc-role="Promoted" />
            <rsc_ticket id="C5" ticket="T1" rsc="R1" rsc-role="Unpromoted" />
            <rsc_ticket id="C6" ticket="T2" rsc="R1" />
            <rsc_ticket id="C7" ticket="T1" rsc="R2" />
        </constraints>
        """
    )

    def test_success(self):
        duplicates = {
            "C1": ["C2"],  # literally same constraints
            "C2": ["C1"],  # literally same constraints
            "C3": ["C4"],  # same constraints, legacy role vs the same new role
            "C4": ["C3"],  # same constraints, legacy role vs the same new role
            "C5": [],  # role doesn't match
            "C6": [],  # ticket doesn't match
            "C7": [],  # resource doesn't match
        }
        checker = ticket.DuplicatesCheckerTicketPlain()
        for id_to_check, id_results in duplicates.items():
            for forced in (False, True):
                with self.subTest(id_to_check=id_to_check, forced=forced):
                    real_reports = checker.check(
                        self.cib,
                        self.cib.xpath(".//*[@id=$id]", id=f"{id_to_check}")[0],
                        force_flags=([reports.codes.FORCE] if forced else []),
                    )
                    expected_reports = []
                    if id_results:
                        if forced:
                            expected_reports = [
                                fixture.warn(
                                    reports.codes.DUPLICATE_CONSTRAINTS_EXIST,
                                    constraint_ids=id_results,
                                )
                            ]
                        else:
                            expected_reports = [
                                fixture.error(
                                    reports.codes.DUPLICATE_CONSTRAINTS_EXIST,
                                    force_code=reports.codes.FORCE,
                                    constraint_ids=id_results,
                                )
                            ]
                    assert_report_item_list_equal(
                        real_reports, expected_reports
                    )


class Element:
    def __init__(self, attrib):
        self.attrib = attrib

    def update(self, attrib):
        self.attrib.update(attrib)
        return self


@mock.patch("pcs.lib.cib.constraint.ticket.have_duplicate_resource_sets")
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
