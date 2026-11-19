from unittest import TestCase

from pcs.common import reports
from pcs.lib.errors import LibraryError

from pcs_test.tools import cli_test_framework as ctf

WAIT_CALL_CMD = "cluster.wait_for_pcmk_idle"
ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)
DEPRECATED_WAIT = (
    "Deprecation Warning: Using '--wait' is deprecated. Instead, use the "
    "'pcs status wait' command to wait for the cluster to settle into stable "
    "state. Use the 'pcs status query resource' commands to verify that the "
    "resource is in the expected state after the wait.\n"
)
ERROR_TIMEOUT = """\
Error: waiting timeout

timeout
"""


class WaitMixin:
    """
    Expects:
      * cli_cmd - full pcs command without --wait
      * lib_cmd - the library command the pcs command calls
      * lib_args, lib_kwargs - expected arguments of the library call
    """

    def _lib_call(self, **kwargs):
        return ctf.LibCallSpec(
            self.lib_cmd, self.lib_args, self.lib_kwargs, **kwargs
        )

    def test_success_no_wait(self):
        ctf.run(self.cli_cmd, self._lib_call())

    def test_success_with_wait(self):
        ctf.run(
            self.cli_cmd + " --wait",
            [self._lib_call(), ctf.LibCallSpec(WAIT_CALL_CMD, (0,))],
            stderr=DEPRECATED_WAIT,
        )

    def test_success_with_wait_timeout(self):
        ctf.run(
            self.cli_cmd + " --wait=10",
            [self._lib_call(), ctf.LibCallSpec(WAIT_CALL_CMD, (10,))],
            stderr=DEPRECATED_WAIT,
        )

    def test_error_does_not_continue_with_wait(self):
        ctf.run(
            self.cli_cmd + " --wait",
            self._lib_call(raises=LibraryError()),
            exit_code=1,
            stderr=DEPRECATED_WAIT + ERRORS_HAVE_OCCURRED,
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
            stderr=DEPRECATED_WAIT + ERROR_TIMEOUT + ERRORS_HAVE_OCCURRED,
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
            stderr=DEPRECATED_WAIT + ERROR_TIMEOUT,
        )

    def test_waiting_error(self):
        ctf.run(
            self.cli_cmd + " --wait",
            [
                self._lib_call(),
                ctf.LibCallSpec(WAIT_CALL_CMD, (0,), raises=LibraryError()),
            ],
            exit_code=1,
            stderr=DEPRECATED_WAIT + ERRORS_HAVE_OCCURRED,
        )

    def test_f_and_wait_mutually_exclusive(self):
        ctf.run(
            self.cli_cmd + " --wait -f foo",
            exit_code=1,
            stderr="Error: Only one of '--wait', '-f' can be used\n",
        )

    def test_invalid_wait_value(self):
        ctf.run(
            self.cli_cmd + " --wait=abc",
            exit_code=1,
            stderr="Error: 'abc' is not a valid interval value\n",
        )


class ResourceMoveWithConstraintWait(WaitMixin, TestCase):
    cli_cmd = "resource move-with-constraint R node1"
    lib_cmd = "resource.move"
    lib_args = ("R",)
    lib_kwargs = dict(node="node1", master=False, lifetime=None)


class ResourceBanWait(WaitMixin, TestCase):
    cli_cmd = "resource ban R node1"
    lib_cmd = "resource.ban"
    lib_args = ("R",)
    lib_kwargs = dict(node="node1", master=False, lifetime=None)


class ResourceClearWait(WaitMixin, TestCase):
    cli_cmd = "resource clear R node1"
    lib_cmd = "resource.unmove_unban"
    lib_args = ("R",)
    lib_kwargs = dict(node="node1", master=False, expired=False)


class MoveBanArgsMixin:
    """
    Expects:
      * cmd - pcs command, e.g. "resource ban"
      * lib_cmd - the library command the pcs command calls
      * no_args_error - error printed when no resource is specified
    """

    @property
    def usage(self):
        return ctf.prepare_stderr_usage(*self.cmd.split())

    def _lib_call(self, node=None, master=False, lifetime=None):
        return ctf.LibCallSpec(
            self.lib_cmd,
            ("R",),
            dict(node=node, master=master, lifetime=lifetime),
        )

    def test_no_args(self):
        ctf.run(
            self.cmd,
            exit_code=1,
            stderr=f"Error: {self.no_args_error}\n",
        )

    def test_too_many_args(self):
        ctf.run(f"{self.cmd} R arg1 arg2 arg3", exit_code=1, stderr=self.usage)

    def test_node_twice(self):
        ctf.run(f"{self.cmd} R node1 node2", exit_code=1, stderr=self.usage)

    def test_lifetime_twice(self):
        ctf.run(
            f"{self.cmd} R lifetime=1h lifetime=2h",
            exit_code=1,
            stderr=self.usage,
        )

    def test_success(self):
        ctf.run(
            f"{self.cmd} R",
            self._lib_call(),
            supported_flags=["-f", "--promoted", "--wait"],
        )

    def test_success_node(self):
        ctf.run(f"{self.cmd} R node1", self._lib_call(node="node1"))

    def test_success_lifetime(self):
        ctf.run(f"{self.cmd} R lifetime=1h", self._lib_call(lifetime="P1h"))

    def test_success_lifetime_unchanged(self):
        ctf.run(f"{self.cmd} R lifetime=T1h", self._lib_call(lifetime="T1h"))

    def test_success_node_lifetime(self):
        ctf.run(
            f"{self.cmd} R node1 lifetime=1h",
            self._lib_call(node="node1", lifetime="P1h"),
        )

    def test_success_lifetime_node(self):
        ctf.run(
            f"{self.cmd} R lifetime=1h node1",
            self._lib_call(node="node1", lifetime="P1h"),
        )

    def test_success_all_options(self):
        ctf.run(
            f"{self.cmd} R lifetime=1h node1 --promoted",
            self._lib_call(node="node1", master=True, lifetime="P1h"),
        )


class ResourceMoveWithConstraintArgs(MoveBanArgsMixin, TestCase):
    cmd = "resource move-with-constraint"
    lib_cmd = "resource.move"
    no_args_error = "must specify a resource to move"


class ResourceBanArgs(MoveBanArgsMixin, TestCase):
    cmd = "resource ban"
    lib_cmd = "resource.ban"
    no_args_error = "must specify a resource to ban"


class ResourceClearArgs(TestCase):
    lib_cmd = "resource.unmove_unban"

    def _lib_call(self, node=None, master=False, expired=False):
        return ctf.LibCallSpec(
            self.lib_cmd,
            ("R",),
            dict(node=node, master=master, expired=expired),
        )

    def test_no_args(self):
        ctf.run(
            "resource clear",
            exit_code=1,
            stderr="Error: must specify a resource to clear\n",
        )

    def test_too_many_args(self):
        ctf.run(
            "resource clear R arg1 arg2",
            exit_code=1,
            stderr=ctf.prepare_stderr_usage("resource", "clear"),
        )

    def test_success(self):
        ctf.run(
            "resource clear R",
            self._lib_call(),
            supported_flags=["-f", "--expired", "--promoted", "--wait"],
        )

    def test_success_node(self):
        ctf.run("resource clear R node1", self._lib_call(node="node1"))

    def test_success_all_options(self):
        ctf.run(
            "resource clear R node1 --promoted --expired",
            self._lib_call(node="node1", master=True, expired=True),
        )
