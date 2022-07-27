import os.path
import signal
import subprocess

from pcs_test import TEST_ROOT

__pcs_location = os.path.join(TEST_ROOT, "pcs_for_tests")
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


class PcsRunnerOld(PcsRunner):
    # TODO remove this class
    def run(self, args, ignore_stderr=False):
        stdout, stderr, retval = super().run(args)
        if ignore_stderr:
            stderr = None
        return "".join(filter(None, [stderr, stdout])), retval


def pcs(cib_file, args, corosync_conf_opt=None, mock_settings=None):
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

    return _run(cmd, env_extend=env)


def pcs_old(
    cib_file,
    args,
    corosync_conf_opt=None,
    mock_settings=None,
    ignore_stderr=False,
):
    # TODO remove this function
    stdout, stderr, retval = pcs(
        cib_file,
        args,
        corosync_conf_opt=corosync_conf_opt,
        mock_settings=mock_settings,
    )
    if ignore_stderr:
        stderr = None
    return "".join(filter(None, [stderr, stdout])), retval


def _run(args, env_extend=None):
    env_vars = {"LC_ALL": "C"}
    env_vars.update(dict(env_extend) if env_extend else {})

    # pylint: disable=subprocess-popen-preexec-fn
    with subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=(lambda: signal.signal(signal.SIGPIPE, signal.SIG_DFL)),
        close_fds=True,
        shell=False,
        env=env_vars,
        # decodes newlines and in python3 also converts bytes to str
        universal_newlines=True,
    ) as process:
        stdout, stderr = process.communicate()
        retval = process.returncode

    return stdout, stderr, retval
