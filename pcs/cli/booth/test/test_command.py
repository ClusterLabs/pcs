from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

from pcs.cli.booth import command
from pcs.test.tools.pcs_unittest import mock


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
            modifiers={
                "force": False,
            }
        )
        lib.booth.config_setup.assert_called_once_with(
            [
                {"key": "site", "value": "1.1.1.1", "details": []},
                {"key": "site", "value": "2.2.2.2", "details": []},
                {"key": "site", "value": "4.4.4.4", "details": []},
                {"key": "arbitrator", "value": "3.3.3.3", "details": []},
            ],
            False
        )

class ConfigTicketAddTest(TestCase):
    def test_call_lib_with_ticket_name(self):
        lib = mock.MagicMock()
        lib.booth = mock.MagicMock()
        lib.booth.config_ticket_add = mock.MagicMock()
        command.config_ticket_add(
            lib,
            arg_list=["TICKET_A", "timeout=10"],
            modifiers={"force": True}
        )
        lib.booth.config_ticket_add.assert_called_once_with(
            "TICKET_A",
            {"timeout": "10"},
            allow_unknown_options=True
        )
