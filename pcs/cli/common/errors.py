from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

class CmdLineInputError(Exception):
    pass

class ErrorWithMessage(CmdLineInputError):
    def __init__(self, *args, **kwargs):
        super(ErrorWithMessage, self).__init__(
            self.build_message(*args, **kwargs)
        )

    def build_message(self, *args, **kwargs):
        return args[0] if args else ""
