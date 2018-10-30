from pcs import utils
from pcs.cli.common.errors import CmdLineInputError
from pcs.lib.errors import LibraryError

def create_router(cmd_map, usage_sub_cmd, default_cmd=None):
    def _router(lib, argv, modifiers):
        if len(argv) < 1:
            if default_cmd is None:
                raise CmdLineInputError()
            sub_cmd, argv_next = default_cmd, []
        else:
            sub_cmd, *argv_next = argv

        try:
            if sub_cmd not in cmd_map:
                sub_cmd = ""
                raise CmdLineInputError()
            return cmd_map[sub_cmd](lib, argv_next, modifiers)
        except LibraryError as e:
            utils.process_library_reports(e.args)
        except CmdLineInputError as e:
            utils.exit_on_cmdline_input_errror(
                e,
                usage_sub_cmd[0],
                " ".join(usage_sub_cmd[1:] + [sub_cmd])
            )
    return _router
