from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.command_env.config_runner_cib import CibShortcuts
from pcs.test.tools.command_env.config_runner_pcmk import PcmkShortcuts
from pcs.test.tools.command_env.config_runner_corosync import CorosyncShortcuts
from pcs.test.tools.command_env.config_runner_sbd import SbdShortcuts
from pcs.test.tools.command_env.config_runner_systemctl import SystemctlShortcuts
from pcs.test.tools.command_env.mock_runner import Call as RunnerCall


class RunnerConfig(object):
    def __init__(self, call_collection, wrap_helper):
        self.__calls = call_collection

        self.cib = wrap_helper(CibShortcuts(self.__calls))
        self.pcmk = wrap_helper(PcmkShortcuts(self.__calls))
        self.corosync = wrap_helper(CorosyncShortcuts(self.__calls))
        self.sbd = wrap_helper(SbdShortcuts(self.__calls))
        self.systemctl = wrap_helper(SystemctlShortcuts(self.__calls))

    def place(
        self, command,
        name="", stdout="", stderr="", returncode=0, check_stdin=None,
        before=None, instead=None
    ):
        """
        Place new call to a config.

        string command -- cmdline call (e.g. "crm_mon --one-shot --as-xml")
        string name -- name of the call; it is possible to get it by the method
            "get"
        string stdout -- stdout of the call
        string stderr -- stderr of the call
        int returncode -- returncode of the call
        callable check_stdin -- callable that can check if stdin is as expected
        string before -- name of another call to insert this call before it
        string instead -- name of another call to replace it by this call
        """
        call = RunnerCall(command, stdout, stderr, returncode, check_stdin)
        self.__calls.place(name, call, before, instead)
        return self
