from unittest import TestCase, mock

from pcs.common import const, reports
from pcs.lib.commands.constraint import ticket as ticket_command

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import create_patcher

patch_commands = create_patcher("pcs.lib.commands.constraint.ticket")


class CreateTest(TestCase):
    def test_success_create_minimal(self):
        env_assist, config = get_env_tools(test_case=self)
        config.runner.cib.load(
            filename="cib-empty-3.7.xml",
            resources="""
                <resources>
                    <primitive id="resourceA" class="service" type="exim"/>
                </resources>
            """,
        )
        config.env.push_cib(
            optional_in_conf="""
                <constraints>
                    <rsc_ticket id="ticket-ticketA-resourceA"
                        rsc="resourceA" ticket="ticketA"
                    />
                </constraints>
            """
        )

        ticket_command.create(env_assist.get_env(), "ticketA", "resourceA", {})

    def test_success_create_full(self):
        env_assist, config = get_env_tools(test_case=self)
        config.runner.cib.load(
            filename="cib-empty-3.7.xml",
            resources="""
                <resources>
                    <primitive id="resourceA" class="service" type="exim"/>
                </resources>
            """,
        )
        config.env.push_cib(
            optional_in_conf="""
                <constraints>
                    <rsc_ticket id="my-id" rsc="resourceA" rsc-role="{role}"
                        ticket="ticketA" loss-policy="fence"
                    />
                </constraints>
            """.format(role=const.PCMK_ROLE_PROMOTED)
        )

        ticket_command.create(
            env_assist.get_env(),
            "ticketA",
            "resourceA",
            {
                "loss-policy": "Fence",
                "rsc-role": str(const.PCMK_ROLE_PROMOTED).lower(),
                "id": "my-id",
            },
        )

    def test_refuse_legacy_role(self):
        env_assist, config = get_env_tools(test_case=self)
        config.runner.cib.load(
            filename="cib-empty-3.7.xml",
            resources="""
                    <resources>
                        <primitive id="resourceA" class="service" type="exim"/>
                    </resources>
                """,
        )

        role = str(const.PCMK_ROLE_UNPROMOTED_LEGACY).lower()
        env_assist.assert_raise_library_error(
            lambda: ticket_command.create(
                env_assist.get_env(),
                "ticketA",
                "resourceA",
                {"rsc-role": role},
            ),
        )
        env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="role",
                    option_value=role,
                    allowed_values=const.PCMK_ROLES,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_refuse_for_nonexisting_resource(self):
        env_assist, config = get_env_tools(test_case=self)
        config.runner.cib.load()
        env_assist.assert_raise_library_error(
            lambda: ticket_command.create(
                env_assist.get_env(),
                "ticketA",
                "resourceA",
                {},
            ),
        )
        env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_NOT_FOUND,
                    id="resourceA",
                    expected_types=[],
                    context_type="",
                    context_id="",
                )
            ]
        )

    def test_validation(self):
        env_assist, config = get_env_tools(test_case=self)
        config.runner.cib.load(
            filename="cib-empty-3.7.xml",
            resources="""
                <resources>
                    <primitive id="R" class="service" type="exim">
                        <meta_attributes id="R-meta"/>
                    </primitive>
                </resources>
            """,
        )
        env_assist.assert_raise_library_error(
            lambda: ticket_command.create(
                env_assist.get_env(),
                "T_1",
                "R-meta",
                {
                    "loss-policy": "lossX",
                    "rsc-role": "roleX",
                    "id": "R",
                    "bad": "option",
                },
            )
        )
        env_assist.assert_reports(
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
                fixture.error(
                    reports.codes.BOOTH_TICKET_NAME_INVALID,
                    ticket_name="T_1",
                ),
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["bad"],
                    allowed=["id", "loss-policy", "rsc-role"],
                    option_type=None,
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.ID_ALREADY_EXISTS,
                    id="R",
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="role",
                    option_value="roleX",
                    allowed_values=(
                        const.PCMK_ROLE_STOPPED,
                        const.PCMK_ROLE_STARTED,
                        const.PCMK_ROLE_PROMOTED,
                        const.PCMK_ROLE_UNPROMOTED,
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="loss-policy",
                    option_value="lossX",
                    allowed_values=("fence", "stop", "freeze", "demote"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_duplicate_constraint(self):
        env_assist, config = get_env_tools(test_case=self)
        config.runner.cib.load(
            filename="cib-empty-3.7.xml",
            resources="""
                <resources>
                    <primitive id="R" class="service" type="exim"/>
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_ticket id="ticket-T-R" rsc="R" ticket="T" />
                </constraints>
            """,
        )

        env_assist.assert_raise_library_error(
            lambda: ticket_command.create(env_assist.get_env(), "T", "R", {})
        )
        env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.DUPLICATE_CONSTRAINTS_EXIST,
                    force_code=reports.codes.FORCE,
                    constraint_ids=["ticket-T-R"],
                )
            ]
        )

    def test_duplicate_constraint_forced(self):
        env_assist, config = get_env_tools(test_case=self)
        config.runner.cib.load(
            filename="cib-empty-3.7.xml",
            resources="""
                <resources>
                    <primitive id="R" class="service" type="exim" />
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_ticket id="ticket-T-R" rsc="R" ticket="T" />
                </constraints>
            """,
        )
        config.env.push_cib(
            optional_in_conf="""
                <constraints>
                    <rsc_ticket id="ticket-T-R" rsc="R" ticket="T" />
                    <rsc_ticket id="ticket-T-R-1" rsc="R" ticket="T" />
                </constraints>
            """
        )

        ticket_command.create(
            env_assist.get_env(), "T", "R", {}, duplication_alowed=True
        )
        env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.DUPLICATE_CONSTRAINTS_EXIST,
                    constraint_ids=["ticket-T-R"],
                )
            ]
        )

    def test_resource_in_clone(self):
        env_assist, config = get_env_tools(test_case=self)
        config.runner.cib.load(
            filename="cib-empty-3.7.xml",
            resources="""
                <resources>
                    <clone id="C">
                        <primitive id="R" class="service" type="exim" />
                    </clone>
                </resources>
            """,
        )

        env_assist.assert_raise_library_error(
            lambda: ticket_command.create(env_assist.get_env(), "T", "R", {})
        )

        env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
                    force_code=reports.codes.FORCE,
                    resource_id="R",
                    parent_type="clone",
                    parent_id="C",
                )
            ]
        )

    def test_resource_in_clone_forced(self):
        env_assist, config = get_env_tools(test_case=self)
        config.runner.cib.load(
            filename="cib-empty-3.7.xml",
            resources="""
                <resources>
                    <clone id="C">
                        <primitive id="R" class="service" type="exim" />
                    </clone>
                </resources>
            """,
        )
        config.env.push_cib(
            optional_in_conf="""
                <constraints>
                    <rsc_ticket id="ticket-T-R" rsc="R" ticket="T" />
                </constraints>
            """
        )

        ticket_command.create(
            env_assist.get_env(), "T", "R", {}, resource_in_clone_alowed=True
        )

        env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
                    resource_id="R",
                    parent_type="clone",
                    parent_id="C",
                )
            ]
        )


class CreateWithSet(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.cib_resources = """
            <resources>
                <primitive id="resource1">
                    <meta_attributes id="resource1-meta"/>
                </primitive>
                <primitive id="resource2">
                    <meta_attributes id="resource2-meta"/>
                </primitive>
                <primitive id="resource3" />
                <primitive id="resource4" />
                <clone id="C">
                    <primitive id="resource-in-clone" />
                </clone>
                <bundle id="B">
                    <primitive id="resource-in-bundle" />
                </bundle>
            </resources>
        """

    @staticmethod
    def set(*args, **kwargs):
        if "require_all" in kwargs:
            kwargs["require-all"] = kwargs["require_all"]
            del kwargs["require_all"]
        return dict(ids=args, options=kwargs)

    def test_success_create_minimal(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.7.xml", resources=self.cib_resources
        )
        self.config.env.push_cib(
            optional_in_conf="""
                <constraints>
                    <rsc_ticket id="ticket_set_r1" ticket="ticket1">
                        <resource_set id="ticket_set_r1_set">
                            <resource_ref id="resource1" />
                        </resource_set>
                    </rsc_ticket>
                </constraints>
            """
        )
        ticket_command.create_with_set(
            self.env_assist.get_env(),
            [self.set("resource1")],
            {"ticket": "ticket1"},
        )

    def test_success_create_full(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.7.xml", resources=self.cib_resources
        )
        self.config.env.push_cib(
            optional_in_conf="""
                <constraints>
                    <rsc_ticket id="constr1" loss-policy="freeze"
                        ticket="ticket1"
                    >
                        <resource_set id="constr1_set" action="promote"
                            require-all="true"
                        >
                            <resource_ref id="resource1" />
                            <resource_ref id="resource2" />
                        </resource_set>
                        <resource_set id="constr1_set-1" role="{role}"
                            sequential="true"
                        >
                            <resource_ref id="resource3" />
                            <resource_ref id="resource4" />
                        </resource_set>
                    </rsc_ticket>
                </constraints>
            """.format(role=const.PCMK_ROLE_PROMOTED)
        )
        ticket_command.create_with_set(
            self.env_assist.get_env(),
            [
                self.set(
                    "resource1",
                    "resource2",
                    action="promote",
                    require_all="true",
                ),
                self.set(
                    "resource3",
                    "resource4",
                    role=const.PCMK_ROLE_PROMOTED,
                    sequential="true",
                ),
            ],
            {"ticket": "ticket1", "loss-policy": "FReeZE", "id": "constr1"},
        )

    def test_refuse_legacy_role(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.7.xml", resources=self.cib_resources
        )
        role = str(const.PCMK_ROLE_UNPROMOTED_LEGACY).lower()
        self.env_assist.assert_raise_library_error(
            lambda: ticket_command.create_with_set(
                self.env_assist.get_env(),
                [self.set("resource1", role=role)],
                {"ticket": "ticket1"},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="role",
                    option_value=role,
                    allowed_values=const.PCMK_ROLES,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_refuse_for_nonexisting_resource(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.7.xml", resources=self.cib_resources
        )
        self.env_assist.assert_raise_library_error(
            lambda: ticket_command.create_with_set(
                self.env_assist.get_env(),
                [self.set("resource1", "resX"), self.set("resY", "resource2")],
                {"ticket": "ticket1"},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_NOT_FOUND,
                    id=res_id,
                    expected_types=[],
                    context_type="",
                    context_id="",
                )
                for res_id in ("resX", "resY")
            ]
        )

    def test_validation(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.7.xml", resources=self.cib_resources
        )
        self.env_assist.assert_raise_library_error(
            lambda: ticket_command.create_with_set(
                self.env_assist.get_env(),
                [
                    self.set(
                        "resource1",
                        "resource1-meta",
                        action="bad_action",
                        sequential="bad_sequential",
                        set_option="value",
                    ),
                    self.set(
                        "resource2-meta",
                        "resource4",
                        role="bad_role",
                        require_all="bad_require_all",
                    ),
                    self.set(),
                ],
                {
                    "ticket": "ticket_1",
                    "id": "resource3",
                    "loss-policy": "bad_policy",
                    "top-option": "value",
                },
            )
        )
        pcmk_bool = (
            "a pacemaker boolean value: '0', '1', 'false', 'n', 'no', 'off', "
            "'on', 'true', 'y', 'yes'"
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="resource1-meta",
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
                    reports.codes.INVALID_OPTIONS,
                    option_names=["set_option"],
                    allowed=["action", "require-all", "role", "sequential"],
                    option_type="set",
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="action",
                    option_value="bad_action",
                    allowed_values=("start", "stop", "promote", "demote"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="sequential",
                    option_value="bad_sequential",
                    allowed_values=pcmk_bool,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="resource2-meta",
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
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="require-all",
                    option_value="bad_require_all",
                    allowed_values=pcmk_bool,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="role",
                    option_value="bad_role",
                    allowed_values=(
                        "Stopped",
                        "Started",
                        "Promoted",
                        "Unpromoted",
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(reports.codes.EMPTY_RESOURCE_SET),
                fixture.error(
                    reports.codes.BOOTH_TICKET_NAME_INVALID,
                    ticket_name="ticket_1",
                ),
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["top-option"],
                    allowed=["id", "loss-policy", "ticket"],
                    option_type=None,
                    allowed_patterns=[],
                ),
                fixture.error(reports.codes.ID_ALREADY_EXISTS, id="resource3"),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="loss-policy",
                    option_value="bad_policy",
                    allowed_values=("fence", "stop", "freeze", "demote"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_duplicate_constraint(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.7.xml",
            resources=self.cib_resources,
            constraints="""
                <constraints>
                    <rsc_ticket id="ticket_set_r1r2r3" ticket="ticket1">
                        <resource_set id="ticket_set_r1r2r3_set">
                            <resource_ref id="resource1" />
                            <resource_ref id="resource2" />
                        </resource_set>
                        <resource_set id="ticket_set_r1r2r3_set-1">
                            <resource_ref id="resource3" />
                            <resource_ref id="resource4" />
                        </resource_set>
                    </rsc_ticket>
                </constraints>
            """,
        )
        self.env_assist.assert_raise_library_error(
            lambda: ticket_command.create_with_set(
                self.env_assist.get_env(),
                [
                    self.set("resource1", "resource2"),
                    self.set("resource3", "resource4"),
                ],
                {"ticket": "ticket1"},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.DUPLICATE_CONSTRAINTS_EXIST,
                    force_code=reports.codes.FORCE,
                    constraint_ids=["ticket_set_r1r2r3"],
                )
            ]
        )

    def test_duplicate_constraint_forced(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.7.xml",
            resources=self.cib_resources,
            constraints="""
                <constraints>
                    <rsc_ticket id="ticket_set_r1r2r3" ticket="ticket1">
                        <resource_set id="ticket_set_r1r2r3_set">
                            <resource_ref id="resource1" />
                            <resource_ref id="resource2" />
                        </resource_set>
                        <resource_set id="ticket_set_r1r2r3_set-1">
                            <resource_ref id="resource3" />
                            <resource_ref id="resource4" />
                        </resource_set>
                    </rsc_ticket>
                </constraints>
            """,
        )
        self.config.env.push_cib(
            optional_in_conf="""
                <constraints>
                    <rsc_ticket id="ticket_set_r1r2r3" ticket="ticket1">
                        <resource_set id="ticket_set_r1r2r3_set">
                            <resource_ref id="resource1" />
                            <resource_ref id="resource2" />
                        </resource_set>
                        <resource_set id="ticket_set_r1r2r3_set-1">
                            <resource_ref id="resource3" />
                            <resource_ref id="resource4" />
                        </resource_set>
                    </rsc_ticket>
                    <rsc_ticket id="ticket_set_r1r2r3-1" ticket="ticket1">
                        <resource_set id="ticket_set_r1r2r3-1_set">
                            <resource_ref id="resource1" />
                            <resource_ref id="resource2" />
                        </resource_set>
                        <resource_set id="ticket_set_r1r2r3-1_set-1">
                            <resource_ref id="resource3" />
                            <resource_ref id="resource4" />
                        </resource_set>
                    </rsc_ticket>
                </constraints>
            """
        )
        ticket_command.create_with_set(
            self.env_assist.get_env(),
            [
                self.set("resource1", "resource2"),
                self.set("resource3", "resource4"),
            ],
            {"ticket": "ticket1"},
            duplication_alowed=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.DUPLICATE_CONSTRAINTS_EXIST,
                    constraint_ids=["ticket_set_r1r2r3"],
                )
            ]
        )

    def test_resource_in_clone(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.7.xml", resources=self.cib_resources
        )
        self.env_assist.assert_raise_library_error(
            lambda: ticket_command.create_with_set(
                self.env_assist.get_env(),
                [
                    self.set("resource1", "resource-in-clone"),
                    self.set("resource-in-bundle", "resource2"),
                ],
                {"ticket": "ticket1"},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
                    force_code=reports.codes.FORCE,
                    resource_id="resource-in-clone",
                    parent_type="clone",
                    parent_id="C",
                ),
                fixture.error(
                    reports.codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
                    force_code=reports.codes.FORCE,
                    resource_id="resource-in-bundle",
                    parent_type="bundle",
                    parent_id="B",
                ),
            ]
        )

    def test_resource_in_clone_forced(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.7.xml", resources=self.cib_resources
        )
        self.config.env.push_cib(
            optional_in_conf="""
                <constraints>
                    <rsc_ticket id="ticket_set_r1rere" ticket="ticket1">
                        <resource_set id="ticket_set_r1rere_set">
                            <resource_ref id="resource1" />
                            <resource_ref id="resource-in-clone" />
                        </resource_set>
                        <resource_set id="ticket_set_r1rere_set-1">
                            <resource_ref id="resource-in-bundle" />
                            <resource_ref id="resource2" />
                        </resource_set>
                    </rsc_ticket>
                </constraints>
            """
        )
        ticket_command.create_with_set(
            self.env_assist.get_env(),
            [
                self.set("resource1", "resource-in-clone"),
                self.set("resource-in-bundle", "resource2"),
            ],
            {"ticket": "ticket1"},
            resource_in_clone_alowed=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
                    resource_id="resource-in-clone",
                    parent_type="clone",
                    parent_id="C",
                ),
                fixture.warn(
                    reports.codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
                    resource_id="resource-in-bundle",
                    parent_type="bundle",
                    parent_id="B",
                ),
            ]
        )


@patch_commands("get_constraints", mock.Mock())
class RemoveTest(TestCase):
    @patch_commands("ticket.remove_plain", mock.Mock(return_value=1))
    @patch_commands(
        "ticket.remove_with_resource_set", mock.Mock(return_value=0)
    )
    def test_successfully_remove_plain(self):
        self.assertTrue(ticket_command.remove(mock.MagicMock(), "T", "R"))

    @patch_commands("ticket.remove_plain", mock.Mock(return_value=0))
    @patch_commands(
        "ticket.remove_with_resource_set", mock.Mock(return_value=1)
    )
    def test_successfully_remove_with_resource_set(self):
        self.assertTrue(ticket_command.remove(mock.MagicMock(), "T", "R"))

    @patch_commands("ticket.remove_plain", mock.Mock(return_value=0))
    @patch_commands(
        "ticket.remove_with_resource_set", mock.Mock(return_value=0)
    )
    def test_raises_library_error_when_no_matching_constraint_found(self):
        self.assertFalse(ticket_command.remove(mock.MagicMock(), "T", "R"))
