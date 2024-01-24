from unittest import (
    TestCase,
    mock,
)

from pcs.common import const
from pcs.common.reports import codes as report_codes
from pcs.lib.commands.constraint import ticket as ticket_command

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import create_patcher

patch_commands = create_patcher("pcs.lib.commands.constraint.ticket")


class CreateTest(TestCase):
    def test_success_create(self):
        env_assist, config = get_env_tools(test_case=self)
        (
            config.runner.cib.load(
                filename="cib-empty-3.7.xml",
                resources="""
                    <resources>
                        <primitive id="resourceA" class="service" type="exim"/>
                    </resources>
                """,
            ).env.push_cib(
                optional_in_conf="""
                    <constraints>
                        <rsc_ticket
                            id="ticket-ticketA-resourceA-{role}"
                            rsc="resourceA"
                            rsc-role="{role}"
                            ticket="ticketA"
                            loss-policy="fence"
                        />
                    </constraints>
                """.format(
                    role=const.PCMK_ROLE_PROMOTED_PRIMARY
                )
            )
        )
        role = str(const.PCMK_ROLE_PROMOTED_LEGACY).lower()

        ticket_command.create(
            env_assist.get_env(),
            "ticketA",
            "resourceA",
            {
                "loss-policy": "fence",
                "rsc-role": role,
            },
        )
        env_assist.assert_reports(
            [
                fixture.deprecation(
                    report_codes.DEPRECATED_OPTION_VALUE,
                    option_name="role",
                    deprecated_value=role,
                    replaced_by=const.PCMK_ROLE_PROMOTED,
                )
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
                str(const.PCMK_ROLE_UNPROMOTED_LEGACY).lower(),
                {"loss-policy": "fence"},
            ),
        )
        env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.ID_NOT_FOUND,
                    id="resourceA",
                    expected_types=[],
                    context_type="",
                    context_id="",
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
