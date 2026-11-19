from unittest import TestCase

from pcs.common import reports
from pcs.lib.errors import LibraryError

from pcs_test.tools import cli_test_framework as ctf

WAIT_CALL_CMD = "cluster.wait_for_pcmk_idle"
SUPPORTED_FLAGS = ["-f", "--wait", "--all"]
ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)
ERROR_TIMEOUT = """\
Error: waiting timeout

timeout
"""


# Command axis - which pcs command word is tested and which library family and
# "enable" value it maps to.


class StandbyCommandMixin:
    cmd = "node standby"
    lib_prefix = "node.standby_unstandby"
    enable = True


class UnstandbyCommandMixin:
    cmd = "node unstandby"
    lib_prefix = "node.standby_unstandby"
    enable = False


class MaintenanceCommandMixin:
    cmd = "node maintenance"
    lib_prefix = "node.maintenance_unmaintenance"
    enable = True


class UnmaintenanceCommandMixin:
    cmd = "node unmaintenance"
    lib_prefix = "node.maintenance_unmaintenance"
    enable = False


# Target axis - which set of nodes the command acts on. Each mixin maps to a
# single library command.


class LocalTargetMixin:
    target_argv = ""
    lib_suffix = "local"

    @property
    def lib_args(self):
        return (self.enable,)


class ListTargetMixin:
    target_argv = " node1 node2"
    lib_suffix = "list"

    @property
    def lib_args(self):
        return (self.enable, ["node1", "node2"])


class AllTargetMixin:
    target_argv = " --all"
    lib_suffix = "all"

    @property
    def lib_args(self):
        return (self.enable,)


class TargetTestsMixin:
    """
    Tests parametrized by a command word (command axis) and a single target
    library command (target axis).

    Expects from the mixed-in axes:
      * cmd - the pcs command, e.g. "node standby"
      * lib_prefix / lib_suffix - compose the expected library call name
      * lib_args - positional args of the expected library call
      * target_argv - command line fragment selecting the target
      * enable - the boolean the command passes to the library
    """

    @property
    def cli_cmd(self):
        return self.cmd + self.target_argv

    @property
    def lib_cmd(self):
        return f"{self.lib_prefix}_{self.lib_suffix}"

    def _lib_call(self, **kwargs):
        return ctf.LibCallSpec(self.lib_cmd, self.lib_args, **kwargs)

    def test_success(self):
        ctf.run(
            self.cli_cmd,
            self._lib_call(),
            supported_flags=SUPPORTED_FLAGS,
        )

    def test_success_with_wait(self):
        ctf.run(
            self.cli_cmd + " --wait",
            [
                self._lib_call(),
                ctf.LibCallSpec(WAIT_CALL_CMD, (0,)),
            ],
        )

    def test_success_with_wait_timeout(self):
        ctf.run(
            self.cli_cmd + " --wait=10",
            [
                self._lib_call(),
                ctf.LibCallSpec(WAIT_CALL_CMD, (10,)),
            ],
        )

    def test_error_does_not_continue_with_wait(self):
        ctf.run(
            self.cli_cmd + " --wait",
            self._lib_call(raises=LibraryError()),
            exit_code=1,
            stderr=ERRORS_HAVE_OCCURRED,
        )

    def test_waiting_timeout_in_reports(self):
        ctf.run(
            self.cli_cmd + " --wait",
            [
                self._lib_call(),
                ctf.LibCallSpec(
                    WAIT_CALL_CMD,
                    (0,),
                    raises=LibraryError(),
                    reports=[
                        reports.ReportItem.error(
                            reports.messages.WaitForIdleTimedOut("timeout")
                        )
                    ],
                ),
            ],
            exit_code=2,
            stderr=ERROR_TIMEOUT + ERRORS_HAVE_OCCURRED,
        )

    def test_waiting_timeout_in_exception(self):
        ctf.run(
            self.cli_cmd + " --wait",
            [
                self._lib_call(),
                ctf.LibCallSpec(
                    WAIT_CALL_CMD,
                    (0,),
                    raises=LibraryError(
                        reports.ReportItem.error(
                            reports.messages.WaitForIdleTimedOut("timeout")
                        )
                    ),
                ),
            ],
            exit_code=2,
            stderr=ERROR_TIMEOUT,
        )

    def test_waiting_error(self):
        ctf.run(
            self.cli_cmd + " --wait",
            [
                self._lib_call(),
                ctf.LibCallSpec(WAIT_CALL_CMD, (0,), raises=LibraryError()),
            ],
            exit_code=1,
            stderr=ERRORS_HAVE_OCCURRED,
        )


class CommandTestsMixin:
    """
    Command-line parsing tests that do not depend on the target. These fail
    before any library call is made, so they run once per command word.

    Expects 'cmd' from the command axis.
    """

    def test_node_list_and_all_mutually_exclusive(self):
        ctf.run(
            self.cmd + " node1 --all",
            exit_code=1,
            stderr="Error: Cannot specify both --all and a list of nodes.\n",
        )

    def test_f_and_wait_mutually_exclusive(self):
        ctf.run(
            self.cmd + " --wait -f foo",
            exit_code=1,
            stderr="Error: Only one of '--wait', '-f' can be used\n",
        )

    def test_invalid_wait_value(self):
        ctf.run(
            self.cmd + " --wait=abc",
            exit_code=1,
            stderr="Error: 'abc' is not a valid interval value\n",
        )

    def test_unsupported_option(self):
        ctf.run(
            self.cmd + " --force",
            exit_code=1,
            stderr=(
                "Error: Specified option '--force' is not supported in this "
                "command\n"
            ),
        )


# Target leaf classes - one per (command word, target) combination.


class StandbyLocal(
    StandbyCommandMixin, LocalTargetMixin, TargetTestsMixin, TestCase
):
    pass


class StandbyList(
    StandbyCommandMixin, ListTargetMixin, TargetTestsMixin, TestCase
):
    pass


class StandbyAll(
    StandbyCommandMixin, AllTargetMixin, TargetTestsMixin, TestCase
):
    pass


class UnstandbyLocal(
    UnstandbyCommandMixin, LocalTargetMixin, TargetTestsMixin, TestCase
):
    pass


class UnstandbyList(
    UnstandbyCommandMixin, ListTargetMixin, TargetTestsMixin, TestCase
):
    pass


class UnstandbyAll(
    UnstandbyCommandMixin, AllTargetMixin, TargetTestsMixin, TestCase
):
    pass


class MaintenanceLocal(
    MaintenanceCommandMixin, LocalTargetMixin, TargetTestsMixin, TestCase
):
    pass


class MaintenanceList(
    MaintenanceCommandMixin, ListTargetMixin, TargetTestsMixin, TestCase
):
    pass


class MaintenanceAll(
    MaintenanceCommandMixin, AllTargetMixin, TargetTestsMixin, TestCase
):
    pass


class UnmaintenanceLocal(
    UnmaintenanceCommandMixin, LocalTargetMixin, TargetTestsMixin, TestCase
):
    pass


class UnmaintenanceList(
    UnmaintenanceCommandMixin, ListTargetMixin, TargetTestsMixin, TestCase
):
    pass


class UnmaintenanceAll(
    UnmaintenanceCommandMixin, AllTargetMixin, TargetTestsMixin, TestCase
):
    pass


# Command-level parsing leaf classes - one per command word.


class StandbyCommand(StandbyCommandMixin, CommandTestsMixin, TestCase):
    pass


class UnstandbyCommand(UnstandbyCommandMixin, CommandTestsMixin, TestCase):
    pass


class MaintenanceCommand(MaintenanceCommandMixin, CommandTestsMixin, TestCase):
    pass


class UnmaintenanceCommand(
    UnmaintenanceCommandMixin, CommandTestsMixin, TestCase
):
    pass
