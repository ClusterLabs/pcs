from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase
from pcs.test.tools.pcs_mock import mock
from pcs.lib.commands import booth as commands

class ConfigSetupTest(TestCase):
    @mock.patch("pcs.lib.booth.configuration.build")
    @mock.patch("pcs.lib.booth.configuration.validate_participants")
    def test_successfuly_build_and_write_to_std_path(
        self, mock_validate_participants, mock_build
    ):
        mock_build.return_value = "config content"
        env = mock.MagicMock()
        commands.config_setup(
            env,
            booth_configuration={
                "sites": ["1.1.1.1"],
                "arbitrators": ["2.2.2.2"],
            },
        )
        env.booth.create_config.assert_called_once_with(
            "config content",
            False
        )
        mock_validate_participants.assert_called_once_with(
            ["1.1.1.1"], ["2.2.2.2"]
        )
