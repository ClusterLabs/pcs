from pcs import utils
from pcs.cli.common.errors import CmdLineInputError

def create_router(cmd_map, usage_sub_cmd, default_cmd=None):
    def _router(lib, argv, modifiers):
        if argv:
            sub_cmd, *argv_next = argv
        else:
            if default_cmd is None:
                raise CmdLineInputError()
            sub_cmd, argv_next = default_cmd, []

        try:
            if sub_cmd not in cmd_map:
                sub_cmd = ""
                raise CmdLineInputError()
            return cmd_map[sub_cmd](lib, argv_next, modifiers)
        except CmdLineInputError as e:
            if not usage_sub_cmd:
                raise
            utils.exit_on_cmdline_input_errror(
                e,
                usage_sub_cmd[0],
                (usage_sub_cmd[1:] + [sub_cmd])
            )

    return _router
