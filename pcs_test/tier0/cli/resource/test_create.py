from unittest import TestCase

from pcs.common import reports
from pcs.lib.errors import LibraryError

from pcs_test.tools import cli_test_framework as ctf

ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)
DEPRECATED_WAIT = (
    "Deprecation Warning: Ability of this command to accept 'wait' argument is "
    "deprecated and will be removed in a future release.\n"
)
ERROR_TIMEOUT = """\
Error: waiting timeout

timeout
"""


class ResourceCreateWaitMixin:
    create_call_kwargs = dict(
        allow_absent_agent=False,
        allow_invalid_operation=False,
        allow_invalid_instance_attributes=False,
        ensure_disabled=False,
        use_default_operations=True,
        allow_not_suitable_command=False,
        enable_agent_self_validation=False,
    )
    wait_call_cmd = "cluster.wait_for_pcmk_idle"

    def test_success_no_wait(self):
        ctf.run(
            self.cli_cmd,
            ctf.LibCallSpec(
                self.create_call_cmd,
                self.create_call_args,
                self.create_call_kwargs,
            ),
        )

    def test_success_with_wait(self):
        ctf.run(
            self.cli_cmd + " --wait",
            [
                ctf.LibCallSpec(
                    self.create_call_cmd,
                    self.create_call_args,
                    self.create_call_kwargs,
                ),
                ctf.LibCallSpec(self.wait_call_cmd, (0,)),
            ],
            stderr=DEPRECATED_WAIT,
        )

    def test_error_does_not_continue_with_wait(self):
        ctf.run(
            self.cli_cmd + " --wait",
            ctf.LibCallSpec(
                self.create_call_cmd,
                self.create_call_args,
                self.create_call_kwargs,
                raises=LibraryError(),
            ),
            exit_code=1,
            stderr=DEPRECATED_WAIT + ERRORS_HAVE_OCCURRED,
        )

    def test_waiting_timeout_in_reports(self):
        ctf.run(
            self.cli_cmd + " --wait",
            [
                ctf.LibCallSpec(
                    self.create_call_cmd,
                    self.create_call_args,
                    self.create_call_kwargs,
                ),
                ctf.LibCallSpec(
                    self.wait_call_cmd,
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
                ctf.LibCallSpec(
                    self.create_call_cmd,
                    self.create_call_args,
                    self.create_call_kwargs,
                ),
                ctf.LibCallSpec(
                    self.wait_call_cmd,
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
                ctf.LibCallSpec(
                    self.create_call_cmd,
                    self.create_call_args,
                    self.create_call_kwargs,
                ),
                ctf.LibCallSpec(
                    self.wait_call_cmd, (0,), raises=LibraryError()
                ),
            ],
            exit_code=1,
            stderr=DEPRECATED_WAIT + ERRORS_HAVE_OCCURRED,
        )


class ResourceCreateWaitPrimitive(ResourceCreateWaitMixin, TestCase):
    cli_cmd = "resource create R dummy"
    create_call_cmd = "resource.create"
    create_call_args = ("R", "dummy", [], {}, {})


class ResourceCreateWaitClone(ResourceCreateWaitMixin, TestCase):
    cli_cmd = "resource create R dummy clone"
    create_call_cmd = "resource.create_as_clone"
    create_call_args = ("R", "dummy", [], {}, {}, {})
    create_call_kwargs = dict(
        **ResourceCreateWaitMixin.create_call_kwargs,
        clone_id=None,
        allow_incompatible_clone_meta_attributes=False,
    )


class ResourceCreateWaitPromotable(ResourceCreateWaitClone):
    cli_cmd = "resource create R dummy promotable"
    create_call_args = ("R", "dummy", [], {}, {}, dict(promotable="true"))


class ResourceCreateWaitGroup(ResourceCreateWaitMixin, TestCase):
    cli_cmd = "--future resource create R dummy group G"
    create_call_cmd = "resource.create_in_group"
    create_call_args = ("R", "dummy", "G", [], {}, {})
    create_call_kwargs = dict(
        **ResourceCreateWaitMixin.create_call_kwargs,
        adjacent_resource_id=None,
        put_after_adjacent=False,
    )


class ResourceCreateWaitIntoBundle(ResourceCreateWaitMixin, TestCase):
    cli_cmd = "resource create R dummy bundle B"
    create_call_cmd = "resource.create_into_bundle"
    create_call_args = ("R", "dummy", [], {}, {}, "B")
    create_call_kwargs = dict(
        **ResourceCreateWaitMixin.create_call_kwargs,
        allow_not_accessible_resource=False,
    )
