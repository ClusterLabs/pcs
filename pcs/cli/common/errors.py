from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

class CmdLineInputError(Exception):
    """
    Exception express that user entered incorrect commad in command line.
    """
    def __init__(self, message=None):
        """
        string message explain what was wrong with entered command
        The routine which handles this exception behaves according to whether
        the message was specified (prints this message to user) or not (prints
        appropriate part of documentation)
        """
        super(CmdLineInputError, self).__init__(message)
        self.message = message
