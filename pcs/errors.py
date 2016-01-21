import sys

import usage
import error_codes

class CmdLineInputError(Exception):
    show_usage = False
    message_list = []

    def __init__(self, show_usage=False):
        self.show_usage = show_usage

class ErrorMessage(object):
    type = None
    info = {}

    def __init__(self, type):
        self.type = type

    def set_info(self, info):
        self.info = info
        return self

def exit_on_cmd_line_input_errror(error, usage_name):
    if error.message_list:
        print('\n'.join(error.message_list))
    if error.show_usage:
        usage.acl([usage_name])
    sys.exit(1)
