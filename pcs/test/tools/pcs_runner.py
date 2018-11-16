from __future__ import (
    absolute_import,
    division,
    print_function,
)

import os.path

from pcs.test.tools.misc import get_test_resource as rc

from pcs import utils

__pcs_location = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "pcs_for_tests"
)
_temp_cib = rc("temp-cib.xml")


class PcsRunner(object):
    def __init__(
        self, cib_file=_temp_cib, corosync_conf_file=None,
        cluster_conf_file=None, mock_settings=None,
    ):
        self.cib_file = cib_file
        self.corosync_conf_file = (
            rc("corosync.conf") if corosync_conf_file is None
            else corosync_conf_file
        )
        self.cluster_conf_file = (
            rc("cluster.conf") if cluster_conf_file is None
            else cluster_conf_file
        )
        self.mock_settings = mock_settings

    def run(self, args):
        args_with_files = (
            "--corosync_conf={0} ".format(self.corosync_conf_file)
            + "--cluster_conf={0} ".format(self.cluster_conf_file)
            + args
        )
        return pcs(
            self.cib_file, args_with_files, mock_settings=self.mock_settings
        )


def pcs(testfile, args="", mock_settings=None):
    """
    Run pcs with -f on specified file
    Return tuple with:
        shell stdoutdata
        shell returncode
    """
    if mock_settings is None:
        mock_settings = {}
    if args == "":
        args = testfile
        testfile = _temp_cib
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

    conf_opts = []
    if "--corosync_conf" not in args:
        corosync_conf = rc("corosync.conf")
        conf_opts.append("--corosync_conf=" + corosync_conf)
    if "--cluster_conf" not in args:
        cluster_conf = rc("cluster.conf")
        conf_opts.append("--cluster_conf=" + cluster_conf)
    env_mock_settings_prefix = "PCS.SETTINGS."
    return utils.run(
        [__pcs_location, "-f", testfile] + conf_opts + arg_split_temp,
        env_extend={
            "{}{}".format(env_mock_settings_prefix, option): value
            for option, value in mock_settings.items()
        },
    )
