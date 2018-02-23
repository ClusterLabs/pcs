from pcs.test.tools.pcs_unittest import TestCase
from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.misc import create_patcher

from pcs.common import report_codes
from pcs.lib.commands.constraint import ticket as ticket_command
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.lib.test.misc import get_mocked_env
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.xml import get_xml_manipulation_creator_from_file

patch_commands = create_patcher("pcs.lib.commands.constraint.ticket")

class CreateTest(TestCase):
    def setUp(self):
        self.create_cib = get_xml_manipulation_creator_from_file(
            rc("cib-empty.xml")
        )

    def test_sucess_create(self):
        env_assist, config = get_env_tools(test_case=self)
        (config
            .runner.cib.load(
                resources="""
                    <resources>
                        <primitive id="resourceA" class="service" type="exim"/>
                    </resources>
                """
            )
            .env.push_cib(
                optional_in_conf="""
                    <constraints>
                        <rsc_ticket
                            id="ticket-ticketA-resourceA-Master"
                            rsc="resourceA"
                            rsc-role="Master"
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
            {
                "loss-policy": "fence",
                "rsc-role": "master"
            }
        )

    def test_refuse_for_nonexisting_resource(self):
        env = get_mocked_env(cib_data=str(self.create_cib()))
        assert_raise_library_error(
            lambda: ticket_command.create(
                env, "ticketA", "resourceA", "master", {"loss-policy": "fence"}
            ),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "context_type": "cib",
                    "context_id": "",
                    "id": "resourceA",
                    "expected_types": [
                        "bundle", "clone", "group", "master", "primitive"
                    ],
                },
                None
            ),
        )

@patch_commands("get_constraints", mock.Mock)
class RemoveTest(TestCase):
    @patch_commands("ticket.remove_plain", mock.Mock(return_value=1))
    @patch_commands("ticket.remove_with_resource_set",mock.Mock(return_value=0))
    def test_successfully_remove_plain(self):
        self.assertTrue(ticket_command.remove(mock.MagicMock(), "T", "R"))

    @patch_commands("ticket.remove_plain", mock.Mock(return_value=0))
    @patch_commands("ticket.remove_with_resource_set",mock.Mock(return_value=1))
    def test_successfully_remove_with_resource_set(self):
        self.assertTrue(ticket_command.remove(mock.MagicMock(), "T", "R"))

    @patch_commands("ticket.remove_plain", mock.Mock(return_value=0))
    @patch_commands("ticket.remove_with_resource_set",mock.Mock(return_value=0))
    def test_raises_library_error_when_no_matching_constraint_found(self):
        self.assertFalse(ticket_command.remove(mock.MagicMock(), "T", "R"))
