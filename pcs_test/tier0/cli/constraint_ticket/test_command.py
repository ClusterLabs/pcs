from unittest import (
    TestCase,
    mock,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import InputModifiers
from pcs.cli.constraint_ticket import command


def _modifiers(force=True):
    options = {}
    if force:
        options["--force"] = ""
    return InputModifiers(options)


class AddTest(TestCase):
    def setUp(self):
        self.lib = mock.MagicMock()
        self.lib.constraint_ticket = mock.MagicMock()
        self.lib.constraint_ticket.create = mock.MagicMock()

    @mock.patch("pcs.cli.constraint_ticket.command.parse_args.parse_add")
    def test_call_library_with_correct_attrs(self, mock_parse_add):
        mock_parse_add.return_value = (
            "ticket",
            "resource_id",
            "",
            {"loss-policy": "fence"},
        )

        command.add(self.lib, ["argv"], _modifiers())

        mock_parse_add.assert_called_once_with(["argv"])
        self.lib.constraint_ticket.create.assert_called_once_with(
            "ticket",
            "resource_id",
            {"loss-policy": "fence"},
            resource_in_clone_alowed=True,
            duplication_alowed=True,
        )

    @mock.patch("pcs.cli.constraint_ticket.command.parse_args.parse_add")
    def test_refuse_resource_role_in_options(self, mock_parse_add):
        mock_parse_add.return_value = (
            "ticket",
            "resource_id",
            "resource_role",
            {"rsc-role": "master"},
        )
        self.assertRaises(
            CmdLineInputError,
            lambda: command.add(self.lib, ["argv"], _modifiers()),
        )

    @mock.patch("pcs.cli.constraint_ticket.command.parse_args.parse_add")
    def test_put_resource_role_to_options_for_library(self, mock_parse_add):
        mock_parse_add.return_value = (
            "ticket",
            "resource_id",
            "resource_role",
            {"loss-policy": "fence"},
        )

        command.add(self.lib, ["argv"], _modifiers())

        mock_parse_add.assert_called_once_with(["argv"])
        self.lib.constraint_ticket.create.assert_called_once_with(
            "ticket",
            "resource_id",
            {"loss-policy": "fence", "rsc-role": "resource_role"},
            resource_in_clone_alowed=True,
            duplication_alowed=True,
        )


class RemoveTest(TestCase):
    def test_refuse_args_count(self):
        self.assertRaises(
            CmdLineInputError,
            lambda: command.remove(
                mock.MagicMock(),
                ["TICKET"],
                _modifiers(False),
            ),
        )
        self.assertRaises(
            CmdLineInputError,
            lambda: command.remove(
                mock.MagicMock(),
                ["TICKET", "RESOURCE", "SOMETHING_ELSE"],
                _modifiers(False),
            ),
        )

    def test_call_library_remove_with_correct_attrs(self):
        # pylint: disable=no-self-use
        lib = mock.MagicMock(
            constraint_ticket=mock.MagicMock(remove=mock.Mock())
        )
        command.remove(lib, ["TICKET", "RESOURCE"], _modifiers(False))
        lib.constraint_ticket.remove.assert_called_once_with(
            "TICKET",
            "RESOURCE",
        )
