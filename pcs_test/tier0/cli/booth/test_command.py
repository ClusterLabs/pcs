# pylint: disable=no-self-use

from unittest import mock, TestCase

from pcs.cli.booth import command
from pcs.cli.common.parse_args import InputModifiers


class ConfigSetupTest(TestCase):
    def test_call_lib_with_correct_args(self):
        lib = mock.MagicMock()
        lib.booth = mock.MagicMock()
        lib.booth.config_setup = mock.MagicMock()

        command.config_setup(
            lib,
            arg_list=[
                "sites", "1.1.1.1", "2.2.2.2", "4.4.4.4",
                "arbitrators", "3.3.3.3"
            ],
            modifiers=InputModifiers({}),
        )
        lib.booth.config_setup.assert_called_once_with(
            [
                {"key": "site", "value": "1.1.1.1", "details": []},
                {"key": "site", "value": "2.2.2.2", "details": []},
                {"key": "site", "value": "4.4.4.4", "details": []},
                {"key": "arbitrator", "value": "3.3.3.3", "details": []},
            ],
            overwrite_existing=False
        )

class ConfigTicketAddTest(TestCase):
    def test_call_lib_with_ticket_name(self):
        lib = mock.MagicMock()
        lib.booth = mock.MagicMock()
        lib.booth.config_ticket_add = mock.MagicMock()
        command.config_ticket_add(
            lib,
            arg_list=["TICKET_A", "timeout=10"],
            modifiers=InputModifiers({"--force": ""})
        )
        lib.booth.config_ticket_add.assert_called_once_with(
            "TICKET_A",
            {"timeout": "10"},
            allow_unknown_options=True
        )
