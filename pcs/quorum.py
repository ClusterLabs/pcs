from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys

from pcs import (
    usage,
    utils,
)
from pcs.lib.errors import LibraryError
from pcs.lib.commands import quorum as lib_quorum

# TODO vvv move to better place and make it reusable vvv
class ErrorWithMessage(utils.CmdLineInputError):
    pass

class MissingOptionValue(ErrorWithMessage):
    def __init__(self, option_name):
        self.message = "missing value of '{0}' option".format(option_name)
        super(MissingOptionValue, self).__init__(self.message)

class OptionWithoutKey(ErrorWithMessage):
    def __init__(self, option):
        self.message = "missing key in '{0}' option".format(option)
        super(OptionWithoutKey, self).__init__(self.message)

class InvalidChoose(ErrorWithMessage):
    def __init__(self, name, allowed_values, given_value):
        self.message = (
            "invalid {0} value '{2}', allowed values are: {1}"
            .format(name, ", ".join(allowed_values), given_value)
        )
        super(InvalidChoose, self).__init__(self.message)

def prepare_options(cmdline_args):
    options = {}
    for arg in cmdline_args:
        if "=" not in arg:
            raise MissingOptionValue(arg)
        if arg.startswith("="):
            raise OptionWithoutKey(arg)

        name, value = arg.split("=", 1)
        options[name] = value
    return options
# TODO ^^^ move to better place and make it reusable ^^^


def quorum_cmd(argv):
    if len(argv) < 1:
        usage.quorum()
        sys.exit(1)

    sub_cmd = argv.pop(0)
    try:
        if sub_cmd == "help":
            usage.quorum(argv)
        elif sub_cmd == "update":
            quorum_update_cmd(argv)
        else:
            raise utils.CmdLineInputError()

    except LibraryError as e:
        utils.process_library_reports(e.args)
    except ErrorWithMessage as e:
        utils.err(e.message)
    except utils.CmdLineInputError:
        usage.quorum([sub_cmd] + argv)
        sys.exit(1)

def quorum_update_cmd(argv):
    options = prepare_options(argv)
    if not options:
        raise utils.CmdLineInputError()

    lib_env = utils.get_lib_env()
    lib_quorum.set_options(lib_env, options)
    if "--corosync_conf" in utils.pcs_options:
        utils.setCorosyncConf(
            lib_env.get_corosync_conf(),
            utils.pcs_options["--corosync_conf"]
        )

