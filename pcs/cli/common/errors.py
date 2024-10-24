from typing import Optional

from pcs.common.str_tools import (
    format_list_base,
    quote_items,
)
from pcs.common.types import StringSequence

ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE = (
    "Cannot specify both --all and a list of nodes."
)

SEE_MAN_CHANGES = "See 'man pcs' -> Changes in pcs-{}."


class CmdLineInputError(Exception):
    """
    an incorrect command has been entered in the command line
    """

    def __init__(
        self,
        message: Optional[str] = None,
        hint: Optional[str] = None,
        show_both_usage_and_message: bool = False,
    ) -> None:
        """
        message -- explains what was wrong with the entered command
        hint -- provides an additional hint how to proceed
        show_both_usage_and_message -- show both the message and usage

        The routine which handles this exception behaves according to whether
        the message was specified (prints this message to user) or not (prints
        appropriate part of documentation). If show_both_usage_and_message is
        True, documentation will be printed first and the message will be
        printed after that. Hint is printed every time as the last item.
        """
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.show_both_usage_and_message = show_both_usage_and_message


def _msg_command_replaced(
    new_commands: StringSequence, pcs_version: str
) -> str:
    commands = format_list_base(quote_items(new_commands))
    changes = SEE_MAN_CHANGES.format(pcs_version)
    return f"This command has been replaced with {commands}. {changes}"


def _msg_command_removed(pcs_version: str) -> str:
    changes = SEE_MAN_CHANGES.format(pcs_version)
    return f"This command has been removed. {changes}"


def command_replaced(
    new_commands: StringSequence, pcs_version: str
) -> CmdLineInputError:
    return CmdLineInputError(
        message=_msg_command_replaced(new_commands, pcs_version=pcs_version)
    )


def command_removed(pcs_version: str) -> CmdLineInputError:
    return CmdLineInputError(
        message=_msg_command_removed(pcs_version=pcs_version)
    )


def raise_command_replaced(
    new_commands: StringSequence, pcs_version: str
) -> None:
    raise command_replaced(new_commands, pcs_version)


def raise_command_removed(pcs_version: str) -> None:
    raise command_removed(pcs_version)
