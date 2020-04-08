import os.path

from pcs_test.tools.misc import get_test_resource as rc

from pcs import utils

__pcs_location = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pcs_for_tests"
)
_temp_cib = rc("temp-cib.xml")

# this can be changed from suite.py
test_installed = False


class PcsRunner:
    def __init__(
        self, cib_file=_temp_cib, corosync_conf_opt=None, mock_settings=None
    ):
        self.cib_file = cib_file
        self.corosync_conf_opt = corosync_conf_opt
        self.mock_settings = mock_settings

    def run(self, args):
        return pcs(
            self.cib_file,
            args,
            corosync_conf_opt=self.corosync_conf_opt,
            mock_settings=self.mock_settings,
        )


def pcs(cib_file, args, corosync_conf_opt=None, mock_settings=None):
    """
    Run pcs with -f on specified file
    Return tuple with:
        shell stdoutdata
        shell returncode
    """
    if mock_settings is None:
        mock_settings = {}
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

    env_mock_settings_prefix = "PCS.SETTINGS."
    env = {
        "{}{}".format(env_mock_settings_prefix, option): value
        for option, value in mock_settings.items()
    }
    if test_installed:
        env["PCS_TEST.TEST_INSTALLED"] = "1"

    cmd = [__pcs_location] + arg_split_temp
    if cib_file:
        cmd.extend(["-f", cib_file])
    if corosync_conf_opt:
        cmd.extend(["--corosync_conf", corosync_conf_opt])

    return utils.run(cmd, env_extend=env)
