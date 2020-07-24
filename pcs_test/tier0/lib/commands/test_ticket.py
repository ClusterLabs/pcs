from unittest import mock, TestCase

from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import create_patcher

from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.commands.constraint import ticket as ticket_command

patch_commands = create_patcher("pcs.lib.commands.constraint.ticket")


class CreateTest(TestCase):
    def test_sucess_create(self):
        env_assist, config = get_env_tools(test_case=self)
        (
            config.runner.cib.load(
                resources="""
                    <resources>
                        <primitive id="resourceA" class="service" type="exim"/>
                    </resources>
                """
            ).env.push_cib(
                optional_in_conf="""
                    <constraints>
                        <rsc_ticket
                            id="ticket-ticketA-resourceA-Main"
                            rsc="resourceA"
                            rsc-role="Main"
                            ticket="ticketA"
                            loss-policy="fence"
                        />
                    </constraints>
                """
            )
        )

        ticket_command.create(
            env_assist.get_env(),
            "ticketA",
            "resourceA",
            {"loss-policy": "fence", "rsc-role": "main"},
        )

    def test_refuse_for_nonexisting_resource(self):
        env_assist, config = get_env_tools(test_case=self)
        config.runner.cib.load()
        env_assist.assert_raise_library_error(
            lambda: ticket_command.create(
                env_assist.get_env(),
                "ticketA",
                "resourceA",
                "main",
                {"loss-policy": "fence"},
            ),
            [
                (
                    severities.ERROR,
                    report_codes.ID_NOT_FOUND,
                    {
                        "context_type": "cib",
                        "context_id": "",
                        "id": "resourceA",
                        "expected_types": [
                            "bundle",
                            "clone",
                            "group",
                            "main",
                            "primitive",
                        ],
                    },
                    None,
                ),
            ],
            expected_in_processor=False,
        )


@patch_commands("get_constraints", mock.Mock)
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
