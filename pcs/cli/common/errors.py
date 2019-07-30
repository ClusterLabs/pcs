from __future__ import (
    absolute_import,
    division,
    print_function,
)


ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE = (
    "Cannot specify both --all and a list of nodes."
)


class CmdLineInputError(Exception):
    """
    Exception express that user entered incorrect commad in command line.
    """
    def __init__(
        self, message=None, hint=None, show_both_usage_and_message=False
    ):
        """
        string message -- explains what was wrong with the entered command
        string hint -- provides an additional hint how to proceed
        bool show_both_usage_and_message -- show both the message and usage

        The routine which handles this exception behaves according to whether
        the message was specified (prints this message to user) or not (prints
        appropriate part of documentation). If show_both_usage_and_message is
        True, documentation will be printed first and the message will be
        printed after that. Hint is printed every time as the last item.
        """
        super(CmdLineInputError, self).__init__(message)
        self.message = message
        self.hint = hint
        self.show_both_usage_and_message = show_both_usage_and_message
