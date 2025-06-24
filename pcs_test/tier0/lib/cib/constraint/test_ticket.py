from unittest import TestCase

from lxml import etree

from pcs.common import const, reports
from pcs.lib.cib.constraint import ticket
from pcs.lib.cib.tools import IdProvider, Version

from pcs_test.tier0.lib.cib.constraint.test_common import (
    DuplicatesCheckerTestBase,
)
from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
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


class ValidateCreateWithSet(TestCase):
    def setUp(self):
        cib = str_to_etree("""
            <resources>
                <primitive id="R1">
                    <meta_attributes id="R1-meta" />
                </primitive>
                <primitive id="R2">
                    <meta_attributes id="R2-meta" />
                </primitive>
                <primitive id="R3" />
                <primitive id="R4" />
                <clone id="C">
                    <primitive id="CR" />
                </clone>
            </resources>
        """)
        self.el_primitives = cib.xpath("./primitive")
        self.el_metas = cib.xpath(".//meta_attributes")
        self.el_clone = cib.xpath(".//*[@id='C']")[0]
        self.el_cloned_primitive = cib.xpath(".//*[@id='CR']")[0]
        self.id_provider = IdProvider(cib)

    @staticmethod
    def set(*args, **kwargs):
        if "require_all" in kwargs:
            kwargs["require-all"] = kwargs["require_all"]
            del kwargs["require_all"]
        return dict(constrained_elements=args, options=kwargs)

    def test_empty_rsc_set_list(self):
        assert_report_item_list_equal(
            ticket.validate_create_with_set(
                self.id_provider, [], {"ticket": "T"}, False
            ),
            [
                fixture.error(reports.codes.EMPTY_RESOURCE_SET_LIST),
            ],
        )

    def test_empty_rsc_set(self):
        assert_report_item_list_equal(
            ticket.validate_create_with_set(
                self.id_provider,
                [self.set(*self.el_primitives[:2]), self.set()],
                {"ticket": "T"},
                False,
            ),
            [
                fixture.error(reports.codes.EMPTY_RESOURCE_SET),
            ],
        )

    def test_resource_not_a_resource(self):
        assert_report_item_list_equal(
            ticket.validate_create_with_set(
                self.id_provider,
                [
                    self.set(self.el_primitives[0], self.el_metas[0]),
                    self.set(self.el_metas[1], self.el_primitives[1]),
                ],
                {"ticket": "T"},
                False,
            ),
            [
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="R1-meta",
                    expected_types=[
                        "bundle",
                        "clone",
                        "group",
                        "master",
                        "primitive",
                    ],
                    current_type="meta_attributes",
                ),
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="R2-meta",
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
            ticket.validate_create_with_set(
                self.id_provider,
                [self.set(self.el_cloned_primitive)],
                {"ticket": "T"},
                False,
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
            ticket.validate_create_with_set(
                self.id_provider,
                [self.set(self.el_cloned_primitive)],
                {"ticket": "T"},
                True,
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
            ticket.validate_create_with_set(
                self.id_provider,
                [self.set(self.el_clone)],
                {"ticket": "T"},
                False,
            ),
            [],
        )

    def test_ticket_missing(self):
        assert_report_item_list_equal(
            ticket.validate_create_with_set(
                self.id_provider,
                [self.set(self.el_primitives[0])],
                {},
                False,
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
            ticket.validate_create_with_set(
                self.id_provider,
                [self.set(self.el_primitives[0])],
                {"ticket": "my_ticket"},
                False,
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
            ticket.validate_create_with_set(
                self.id_provider,
                [self.set(self.el_primitives[0])],
                {"id": "123", "ticket": "ticket"},
                False,
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
            ticket.validate_create_with_set(
                self.id_provider,
                [self.set(self.el_primitives[0])],
                {"id": "R1", "ticket": "ticket"},
                False,
            ),
            [
                fixture.error(
                    reports.codes.ID_ALREADY_EXISTS,
                    id="R1",
                )
            ],
        )

    def test_loss_policy_not_valid(self):
        assert_report_item_list_equal(
            ticket.validate_create_with_set(
                self.id_provider,
                [self.set(self.el_primitives[0])],
                {"loss-policy": "bad", "ticket": "ticket"},
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
                )
            ],
        )

    def test_option_names(self):
        assert_report_item_list_equal(
            ticket.validate_create_with_set(
                self.id_provider,
                [self.set(self.el_primitives[0])],
                {"ticket": "ticket", "bad_option": "value"},
                False,
            ),
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["bad_option"],
                    allowed=["id", "loss-policy", "ticket"],
                    option_type=None,
                    allowed_patterns=[],
                )
            ],
        )

    def test_set_options(self):
        pcmk_bool = (
            "a pacemaker boolean value: '0', '1', 'false', 'n', 'no', 'off', "
            "'on', 'true', 'y', 'yes'"
        )
        assert_report_item_list_equal(
            ticket.validate_create_with_set(
                self.id_provider,
                [
                    self.set(
                        self.el_primitives[0],
                        action="bad-action",
                        require_all="bad-require",
                        role=const.PCMK_ROLE_PROMOTED_LEGACY,
                        sequential="bad-sequential",
                        bad_option="value",
                    )
                ],
                {"ticket": "ticket"},
                False,
            ),
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["bad_option"],
                    allowed=["action", "require-all", "role", "sequential"],
                    option_type="set",
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="action",
                    option_value="bad-action",
                    allowed_values=("start", "stop", "promote", "demote"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="require-all",
                    option_value="bad-require",
                    allowed_values=pcmk_bool,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="role",
                    option_value=const.PCMK_ROLE_PROMOTED_LEGACY,
                    allowed_values=(
                        "Stopped",
                        "Started",
                        "Promoted",
                        "Unpromoted",
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="sequential",
                    option_value="bad-sequential",
                    allowed_values=pcmk_bool,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )


class CreateWithSet:
    # pcs_test.tier0.lib.cib.constraint.test_common.CreateConstraintWithSetTest
    pass


class DuplicatesCheckerTicketPlain(DuplicatesCheckerTestBase):
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
            <rsc_ticket id="C8" ticket="T1">
                <resource_set id="C8_set">
                    <resource_ref id="R1" />
                </resource_set>
            </rsc_ticket>
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
        self.assert_success(self.cib, checker, duplicates)


class DuplicatesCheckerTicketWithSet(DuplicatesCheckerTestBase):
    cib = etree.fromstring(
        """
        <constraints>
            <rsc_ticket id="C1" ticket="T1">
                <resource_set id="C1_set">
                    <resource_ref id="R1" /> <resource_ref id="R2" />
                </resource_set>
                <resource_set id="C1_set-1">
                    <resource_ref id="R3" /> <resource_ref id="R4" />
                </resource_set>
            </rsc_ticket>
            <rsc_ticket id="C2" ticket="T1">
                <resource_set id="C2_set" role="Promoted">
                    <resource_ref id="R1" /> <resource_ref id="R2" />
                </resource_set>
                <resource_set id="C2_set-1" role="Unpromoted">
                    <resource_ref id="R3" /> <resource_ref id="R4" />
                </resource_set>
            </rsc_ticket>
            <rsc_ticket id="C3" ticket="T2">
                <resource_set id="C3_set">
                    <resource_ref id="R1" /> <resource_ref id="R2" />
                </resource_set>
                <resource_set id="C3_set-1">
                    <resource_ref id="R3" /> <resource_ref id="R4" />
                </resource_set>
            </rsc_ticket>
            <rsc_ticket id="C4" ticket="T1">
                <resource_set id="C4_set">
                    <resource_ref id="R1" /> <resource_ref id="R2" />
                </resource_set>
            </rsc_ticket>
        </constraints>
        """
    )

    def test_success(self):
        duplicates = {
            "C1": ["C2"],  # same constraints, options don't matter
            "C2": ["C1"],  # same constraints, options don't matter
            "C3": [],  # same resources, different ticket
            "C4": [],  # different resources, same ticket
        }
        checker = ticket.DuplicatesCheckerTicketWithSet()
        self.assert_success(self.cib, checker, duplicates)


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
