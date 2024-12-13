from pcs_test.tools.command_env.config_runner_booth import BoothShortcuts
from pcs_test.tools.command_env.config_runner_cib import CibShortcuts
from pcs_test.tools.command_env.config_runner_corosync import CorosyncShortcuts
from pcs_test.tools.command_env.config_runner_pcmk import PcmkShortcuts
from pcs_test.tools.command_env.config_runner_sbd import SbdShortcuts
from pcs_test.tools.command_env.config_runner_scsi import ScsiShortcuts
from pcs_test.tools.command_env.mock_runner import Call as RunnerCall


class RunnerConfig:
    def __init__(self, call_collection, wrap_helper):
        self.__calls = call_collection

        self.booth = wrap_helper(BoothShortcuts(self.__calls))
        self.cib = wrap_helper(CibShortcuts(self.__calls))
        self.corosync = wrap_helper(CorosyncShortcuts(self.__calls))
        self.pcmk = wrap_helper(PcmkShortcuts(self.__calls))
        self.sbd = wrap_helper(SbdShortcuts(self.__calls))
        self.scsi = wrap_helper(ScsiShortcuts(self.__calls))

    def place(  # noqa: PLR0913
        self,
        command,
        *,
        name="",
        stdout="",
        stderr="",
        returncode=0,
        check_stdin=None,
        before=None,
        instead=None,
        env=None,
    ):
        # pylint: disable=too-many-arguments
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
        dict env -- CommandRunner environment variables
        """
        call = RunnerCall(
            command, stdout, stderr, returncode, check_stdin, env=env
        )
        self.__calls.place(name, call, before, instead)
        return self
