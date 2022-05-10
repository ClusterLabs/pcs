from typing import Optional

ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE = (
    "Cannot specify both --all and a list of nodes."
)
SEE_MAN_CHANGES = "See 'man pcs' -> Changes in pcs-0.10."
HINT_SYNTAX_CHANGE = (
    "Syntax has changed from previous version. " + SEE_MAN_CHANGES
)


def msg_command_replaced(*new_commands):
    new = "', '".join(new_commands)
    return f"This command has been replaced with '{new}'. {SEE_MAN_CHANGES}"


def raise_command_replaced(*new_commands):
    raise CmdLineInputError(message=msg_command_replaced(*new_commands))


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
