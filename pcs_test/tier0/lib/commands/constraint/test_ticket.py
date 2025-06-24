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
