from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

from pcs.cli.booth import command
from pcs.test.tools.pcs_mock import mock


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
            {
                "sites": ["1.1.1.1", "2.2.2.2", "4.4.4.4"],
                "arbitrators": ["3.3.3.3"],
            },
            False
        )
