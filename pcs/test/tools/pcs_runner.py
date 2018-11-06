import os.path

from pcs.test.tools.misc import get_test_resource as rc

from pcs import utils

__pcs_location = os.path.join(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ),
    "pcs_for_tests"
)
_temp_cib = rc("temp-cib.xml")


class PcsRunner:
    def __init__(
        self, cib_file=_temp_cib, corosync_conf_file=None,
        corosync_conf_opt=None
    ):
        self.cib_file = cib_file
        self.corosync_conf_file = corosync_conf_file
        self.corosync_conf_opt = corosync_conf_opt

    def run(self, args):
        return pcs(
            self.cib_file, args, corosync_conf_file=self.corosync_conf_file,
            corosync_conf_opt=self.corosync_conf_opt
        )


def pcs(
    cib_file, args, corosync_conf_file=None, uid_gid_dir=None,
    corosync_conf_opt=None
):
    """
    Run pcs with -f on specified file
    Return tuple with:
        shell stdoutdata
        shell returncode
    """
    arg_split = args.split()
    arg_split_temp = []
    in_quote = False
    for arg in arg_split:
        if in_quote:
            arg_split_temp[-1] = arg_split_temp[-1] + " " + arg.replace("'", "")
            if arg.find("'") != -1:
                in_quote = False
        else:
            arg_split_temp.append(arg.replace("'", ""))
            if arg.find("'") != -1 and not (arg[0] == "'" and arg[-1] == "'"):
                in_quote = True

    env = {}
    env_pcs_settings_prefix = "PCS.SETTINGS."
    if corosync_conf_file:
        env[f"{env_pcs_settings_prefix}corosync_conf_file"] = corosync_conf_file
    if uid_gid_dir:
        env[f"{env_pcs_settings_prefix}corosync_uidgid_dir"] = uid_gid_dir
    cmd = [__pcs_location] + arg_split_temp
    if cib_file:
        cmd.extend(["-f", cib_file])
    if corosync_conf_opt:
        cmd.extend(["--corosync_conf", corosync_conf_opt])
    return utils.run(cmd, env_extend=env)
