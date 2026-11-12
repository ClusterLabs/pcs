from unittest import TestCase

from pcs.common import reports
from pcs.lib.errors import LibraryError

from pcs_test.tools import cli_test_framework as ctf
from pcs_test.tools.fixture_cli import FIXTURE_FUTURE_OPTION_DEPRECATION_WARNING

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
SYNTAX_CHANGED_HINT = (
    "Hint: Syntax has changed from previous version. "
    "See 'man pcs' -> Changes in pcs-1.0.\n"
)
CREATE_SETTINGS = dict(
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    ensure_disabled=False,
    use_default_operations=True,
    allow_not_suitable_command=False,
    enable_agent_self_validation=False,
)


class ResourceCreateWaitMixin:
    create_call_kwargs = dict(**CREATE_SETTINGS)
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
    cli_cmd = "resource create R dummy group G"
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


class ResourceCreateArgsValidation(TestCase):
    def test_too_few_args(self):
        ctf.run(
            "resource create R",
            exit_code=1,
            stderr=ctf.prepare_stderr_usage("resource", "create"),
        )

    def test_group_option_rejected(self):
        ctf.run(
            "resource create R ocf:pacemaker:Dummy --group G",
            exit_code=1,
            stderr=(
                "Error: Specified option '--group' is not supported in this "
                "command\n" + SYNTAX_CHANGED_HINT
            ),
        )

    def test_all_group_options_rejected(self):
        ctf.run(
            "resource create R ocf:pacemaker:Dummy "
            "--group G --before R1 --after R2",
            exit_code=1,
            stderr=(
                "Error: Specified options '--after', '--before', '--group' are "
                "not supported in this command\n" + SYNTAX_CHANGED_HINT
            ),
        )


class ResourceCreateInGroup(TestCase):
    create_call_cmd = "resource.create_in_group"

    @staticmethod
    def _create_call_kwargs(adjacent_resource_id, put_after_adjacent):
        return dict(
            **CREATE_SETTINGS,
            adjacent_resource_id=adjacent_resource_id,
            put_after_adjacent=put_after_adjacent,
        )

    def test_group_keyword(self):
        ctf.run(
            "resource create R ocf:pacemaker:Dummy group G",
            ctf.LibCallSpec(
                self.create_call_cmd,
                ("R", "ocf:pacemaker:Dummy", "G", [], {}, {}),
                self._create_call_kwargs(None, False),
            ),
        )

    def test_group_with_before_keyword(self):
        ctf.run(
            "resource create R ocf:pacemaker:Dummy group G before R1",
            ctf.LibCallSpec(
                self.create_call_cmd,
                ("R", "ocf:pacemaker:Dummy", "G", [], {}, {}),
                self._create_call_kwargs("R1", False),
            ),
        )

    def test_group_with_after_keyword(self):
        ctf.run(
            "resource create R ocf:pacemaker:Dummy group G after R1",
            ctf.LibCallSpec(
                self.create_call_cmd,
                ("R", "ocf:pacemaker:Dummy", "G", [], {}, {}),
                self._create_call_kwargs("R1", True),
            ),
        )

    def test_group_with_before_and_after_keywords(self):
        ctf.run(
            "resource create R ocf:pacemaker:Dummy group G before R1 after R2",
            exit_code=1,
            stderr="Error: you cannot specify both 'before' and 'after'\n",
        )

    def test_future_is_noop_and_warns(self):
        ctf.run(
            "resource create R ocf:pacemaker:Dummy group G --future",
            ctf.LibCallSpec(
                self.create_call_cmd,
                ("R", "ocf:pacemaker:Dummy", "G", [], {}, {}),
                self._create_call_kwargs(None, False),
            ),
            stderr=(
                "Deprecation Warning: "
                + FIXTURE_FUTURE_OPTION_DEPRECATION_WARNING
                + "\n"
            ),
        )
