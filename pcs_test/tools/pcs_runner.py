import os.path

from pcs import utils

__pcs_location = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pcs_for_tests"
)
# this can be changed from suite.py
test_installed = False


class PcsRunner:
    def __init__(self, cib_file, corosync_conf_opt=None, mock_settings=None):
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

    env_mock_settings_prefix = "PCS.SETTINGS."
    env = {
        "{}{}".format(env_mock_settings_prefix, option): value
        for option, value in mock_settings.items()
    }
    if test_installed:
        env["PCS_TEST.TEST_INSTALLED"] = "1"

    cmd = [__pcs_location]
    if cib_file:
        cmd.extend(["-f", cib_file])
    if corosync_conf_opt:
        cmd.extend(["--corosync_conf", corosync_conf_opt])
    cmd += args

    return utils.run(cmd, env_extend=env)
