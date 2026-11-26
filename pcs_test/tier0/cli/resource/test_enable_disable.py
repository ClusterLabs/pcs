from dataclasses import replace
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
SAFE_DISABLE_FORCE_WARNING = (
    "Warning: option '--force' is specified therefore checks for disabling "
    "resource safely will be skipped\n"
)


def _call_is_any_stonith(resource_ids, output=False):
    return ctf.LibCallSpec(
        "resource.is_any_stonith", (resource_ids,), output=output
    )


def _fixture_simulate_output(resources=("Rx", "Ry")):
    return dict(
        plaintext_simulated_status="simulate output",
        other_affected_resource_list=list(resources),
    )


class WaitMixin:
    """
    Expects:
      * cli_cmd - full pcs command without --wait
      * type_check_call - expected lib call checking types of the resources
      * lib_call - expected lib call doing the actual change
      * type_check_before_wait_parsing - True if the command checks resource
        types before it parses the --wait value
      * cmd_stderr - output the command prints before processing --wait
    """

    cmd_stderr = ""

    def _lib_calls(self, raises=None):
        return [self.type_check_call, replace(self.lib_call, raises=raises)]

    def test_success_no_wait(self):
        ctf.run(self.cli_cmd, self._lib_calls(), stderr=self.cmd_stderr)

    def test_success_with_wait(self):
        ctf.run(
            self.cli_cmd + " --wait",
            self._lib_calls() + [ctf.LibCallSpec(WAIT_CALL_CMD, (0,))],
            stderr=self.cmd_stderr + DEPRECATED_WAIT,
        )

    def test_success_with_wait_timeout(self):
        ctf.run(
            self.cli_cmd + " --wait=10",
            self._lib_calls() + [ctf.LibCallSpec(WAIT_CALL_CMD, (10,))],
            stderr=self.cmd_stderr + DEPRECATED_WAIT,
        )

    def test_error_does_not_continue_with_wait(self):
        ctf.run(
            self.cli_cmd + " --wait",
            self._lib_calls(raises=LibraryError()),
            exit_code=1,
            stderr=self.cmd_stderr + DEPRECATED_WAIT + ERRORS_HAVE_OCCURRED,
        )

    def test_waiting_timeout_in_reports(self):
        ctf.run(
            self.cli_cmd + " --wait",
            self._lib_calls()
            + [
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
            stderr=(
                self.cmd_stderr
                + DEPRECATED_WAIT
                + ERROR_TIMEOUT
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_waiting_timeout_in_exception(self):
        ctf.run(
            self.cli_cmd + " --wait",
            self._lib_calls()
            + [
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
            stderr=self.cmd_stderr + DEPRECATED_WAIT + ERROR_TIMEOUT,
        )

    def test_waiting_error(self):
        ctf.run(
            self.cli_cmd + " --wait",
            self._lib_calls()
            + [ctf.LibCallSpec(WAIT_CALL_CMD, (0,), raises=LibraryError())],
            exit_code=1,
            stderr=self.cmd_stderr + DEPRECATED_WAIT + ERRORS_HAVE_OCCURRED,
        )

    def test_invalid_wait_value(self):
        ctf.run(
            self.cli_cmd + " --wait=abc",
            (
                [self.type_check_call]
                if self.type_check_before_wait_parsing
                else []
            ),
            exit_code=1,
            stderr=(
                self.cmd_stderr + "Error: 'abc' is not a valid interval value\n"
            ),
        )


class ResourceEnableWait(WaitMixin, TestCase):
    cli_cmd = "resource enable R1 R2"
    type_check_call = _call_is_any_stonith(["R1", "R2"])
    lib_call = ctf.LibCallSpec("resource.enable", (["R1", "R2"],))
    type_check_before_wait_parsing = False


class ResourceDisableWait(WaitMixin, TestCase):
    cli_cmd = "resource disable R1 R2"
    type_check_call = _call_is_any_stonith(["R1", "R2"])
    lib_call = ctf.LibCallSpec("resource.disable", (["R1", "R2"], set()))
    type_check_before_wait_parsing = True


class ResourceDisableSafeWait(WaitMixin, TestCase):
    cli_cmd = "resource disable R1 R2 --safe"
    type_check_call = _call_is_any_stonith(["R1", "R2"])
    lib_call = ctf.LibCallSpec("resource.disable_safe", (["R1", "R2"], True))
    type_check_before_wait_parsing = True


class ResourceDisableNoStrictWait(WaitMixin, TestCase):
    cli_cmd = "resource disable R1 R2 --no-strict"
    type_check_call = _call_is_any_stonith(["R1", "R2"])
    lib_call = ctf.LibCallSpec("resource.disable_safe", (["R1", "R2"], False))
    type_check_before_wait_parsing = True


class ResourceSafeDisableWait(WaitMixin, TestCase):
    cli_cmd = "resource safe-disable R1 R2"
    type_check_call = _call_is_any_stonith(["R1", "R2"])
    lib_call = ctf.LibCallSpec("resource.disable_safe", (["R1", "R2"], True))
    type_check_before_wait_parsing = True


class ResourceSafeDisableNoStrictWait(WaitMixin, TestCase):
    cli_cmd = "resource safe-disable R1 R2 --no-strict"
    type_check_call = _call_is_any_stonith(["R1", "R2"])
    lib_call = ctf.LibCallSpec("resource.disable_safe", (["R1", "R2"], False))
    type_check_before_wait_parsing = True


class ResourceSafeDisableForceWait(WaitMixin, TestCase):
    cli_cmd = "resource safe-disable R1 R2 --force"
    type_check_call = _call_is_any_stonith(["R1", "R2"])
    # --force skips safety checks, it is not passed to the library command
    lib_call = ctf.LibCallSpec("resource.disable", (["R1", "R2"], set()))
    type_check_before_wait_parsing = True
    cmd_stderr = SAFE_DISABLE_FORCE_WARNING


class SafeBriefMixin:
    # This class is important because it verifies pcs exit code in --brief
    # mode. Exit code is based on reports, brief mode filters reports.
    """
    Expects:
      * cli_cmd - full pcs command without --brief and --wait
      * lib_call - expected lib call doing the actual change
    """

    def _lib_calls(self, wait_raises=None):
        return [
            _call_is_any_stonith(["R1", "R2"]),
            replace(
                self.lib_call,
                reports=[
                    reports.ReportItem.info(
                        reports.messages.PacemakerSimulationResult(
                            "simulate output"
                        )
                    )
                ],
            ),
            ctf.LibCallSpec(
                WAIT_CALL_CMD,
                (0,),
                raises=wait_raises,
                reports=[
                    reports.ReportItem.info(
                        reports.messages.WaitForIdleStarted(0)
                    )
                ],
            ),
        ]

    def test_success_brief_with_wait(self):
        ctf.run(
            self.cli_cmd + " --brief --wait",
            self._lib_calls(),
            # info reports, including the one about waiting, are suppressed in
            # brief mode
            stderr=DEPRECATED_WAIT,
        )

    def test_waiting_timeout_brief(self):
        ctf.run(
            self.cli_cmd + " --brief --wait",
            self._lib_calls(
                wait_raises=LibraryError(
                    reports.ReportItem.error(
                        reports.messages.WaitForIdleTimedOut("timeout")
                    )
                )
            ),
            exit_code=2,
            stderr=DEPRECATED_WAIT + ERROR_TIMEOUT,
        )


class ResourceDisableSafeBrief(SafeBriefMixin, TestCase):
    cli_cmd = "resource disable R1 R2 --safe"
    lib_call = ctf.LibCallSpec("resource.disable_safe", (["R1", "R2"], True))


class ResourceDisableNoStrictBrief(SafeBriefMixin, TestCase):
    cli_cmd = "resource disable R1 R2 --no-strict"
    lib_call = ctf.LibCallSpec("resource.disable_safe", (["R1", "R2"], False))


class ResourceSafeDisableBrief(SafeBriefMixin, TestCase):
    cli_cmd = "resource safe-disable R1 R2"
    lib_call = ctf.LibCallSpec("resource.disable_safe", (["R1", "R2"], True))


class ResourceSafeDisableNoStrictBrief(SafeBriefMixin, TestCase):
    cli_cmd = "resource safe-disable R1 R2 --no-strict"
    lib_call = ctf.LibCallSpec("resource.disable_safe", (["R1", "R2"], False))


class ResourceEnable(TestCase):
    def test_no_args(self):
        ctf.run(
            "resource enable",
            exit_code=1,
            stderr="Error: You must specify resource(s) to enable\n",
        )

    def test_one_resource(self):
        ctf.run(
            "resource enable R1",
            [
                _call_is_any_stonith(["R1"]),
                ctf.LibCallSpec("resource.enable", (["R1"],)),
            ],
            supported_flags=["--wait", "-f"],
        )

    def test_more_resources(self):
        ctf.run(
            "resource enable R1 R2",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec("resource.enable", (["R1", "R2"],)),
            ],
        )

    def test_stonith_resource(self):
        ctf.run(
            "resource enable R1 S1",
            _call_is_any_stonith(["R1", "S1"], output=True),
            exit_code=1,
            stderr=(
                "Error: This command does not accept stonith resources. "
                "Please use 'pcs stonith enable' instead.\n"
            ),
        )

    def test_f_and_wait_mutually_exclusive(self):
        ctf.run(
            "resource enable R1 --wait -f foo",
            exit_code=1,
            stderr="Error: Only one of '--wait', '-f' can be used\n",
        )


class ResourceDisable(TestCase):
    def test_no_args(self):
        ctf.run(
            "resource disable",
            exit_code=1,
            stderr="Error: You must specify resource(s) to disable\n",
        )

    def test_one_resource(self):
        ctf.run(
            "resource disable R1",
            [
                _call_is_any_stonith(["R1"]),
                ctf.LibCallSpec("resource.disable", (["R1"], set())),
            ],
            supported_flags=[
                "-f",
                "--force",
                "--brief",
                "--safe",
                "--simulate",
                "--no-strict",
                "--wait",
            ],
        )

    def test_more_resources(self):
        ctf.run(
            "resource disable R1 R2",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec("resource.disable", (["R1", "R2"], set())),
            ],
        )

    def test_force(self):
        ctf.run(
            "resource disable R1 --force",
            [
                _call_is_any_stonith(["R1"]),
                ctf.LibCallSpec(
                    "resource.disable", (["R1"], {reports.codes.FORCE})
                ),
            ],
        )

    def test_stonith_resource(self):
        ctf.run(
            "resource disable R1 S1",
            _call_is_any_stonith(["R1", "S1"], output=True),
            exit_code=1,
            stderr=(
                "Error: This command does not accept stonith resources. "
                "Please use 'pcs stonith disable' instead.\n"
            ),
        )

    def test_brief(self):
        ctf.run(
            "resource disable R1 R2 --brief",
            _call_is_any_stonith(["R1", "R2"]),
            exit_code=1,
            stderr=(
                "Error: '--brief' cannot be used without '--simulate' or "
                "'--safe'\n"
            ),
        )

    def test_safe(self):
        ctf.run(
            "resource disable R1 R2 --safe",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec("resource.disable_safe", (["R1", "R2"], True)),
            ],
        )

    def test_safe_affects_other_resources(self):
        lib_reports = [
            reports.ReportItem.error(
                reports.messages.ResourceDisableAffectsOtherResources(
                    ["R1", "R2"], ["Rx"]
                )
            ),
            reports.ReportItem.info(
                reports.messages.PacemakerSimulationResult("simulate output")
            ),
        ]
        ctf.run(
            "resource disable R1 R2 --safe",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec(
                    "resource.disable_safe",
                    (["R1", "R2"], True),
                    raises=LibraryError(),
                    reports=lib_reports,
                ),
            ],
            exit_code=1,
            stderr=ctf.prepare_stderr_reports(
                lib_reports, additional_error=True
            ),
        )

    def test_safe_brief_affects_other_resources(self):
        error_report = reports.ReportItem.error(
            reports.messages.ResourceDisableAffectsOtherResources(
                ["R1", "R2"], ["Rx"]
            )
        )
        ctf.run(
            "resource disable R1 R2 --safe --brief",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec(
                    "resource.disable_safe",
                    (["R1", "R2"], True),
                    raises=LibraryError(),
                    reports=[
                        error_report,
                        reports.ReportItem.info(
                            reports.messages.PacemakerSimulationResult(
                                "simulate output"
                            )
                        ),
                    ],
                ),
            ],
            exit_code=1,
            # info reports are suppressed in brief mode
            stderr=ctf.prepare_stderr_reports(
                [error_report], additional_error=True
            ),
        )

    def test_safe_no_strict(self):
        ctf.run(
            "resource disable R1 R2 --safe --no-strict",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec("resource.disable_safe", (["R1", "R2"], False)),
            ],
        )

    def test_no_strict(self):
        ctf.run(
            "resource disable R1 R2 --no-strict",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec("resource.disable_safe", (["R1", "R2"], False)),
            ],
        )

    def test_simulate(self):
        ctf.run(
            "resource disable R1 R2 --simulate",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec(
                    "resource.disable_simulate",
                    (["R1", "R2"], True),
                    output=_fixture_simulate_output(),
                ),
            ],
            stdout="simulate output\n",
        )

    def test_simulate_no_strict(self):
        ctf.run(
            "resource disable R1 R2 --simulate --no-strict",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec(
                    "resource.disable_simulate",
                    (["R1", "R2"], False),
                    output=_fixture_simulate_output(),
                ),
            ],
            stdout="simulate output\n",
        )

    def test_simulate_brief(self):
        ctf.run(
            "resource disable R1 R2 --simulate --brief",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec(
                    "resource.disable_simulate",
                    (["R1", "R2"], True),
                    output=_fixture_simulate_output(),
                ),
            ],
            stdout="Rx\nRy\n",
        )

    def test_simulate_brief_no_strict(self):
        ctf.run(
            "resource disable R1 R2 --simulate --brief --no-strict",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec(
                    "resource.disable_simulate",
                    (["R1", "R2"], False),
                    output=_fixture_simulate_output(),
                ),
            ],
            stdout="Rx\nRy\n",
        )

    def test_simulate_brief_nothing_affected(self):
        ctf.run(
            "resource disable R1 R2 --simulate --brief",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec(
                    "resource.disable_simulate",
                    (["R1", "R2"], True),
                    output=_fixture_simulate_output(resources=[]),
                ),
            ],
        )

    def test_simulate_wait(self):
        ctf.run(
            "resource disable R1 --simulate --wait",
            _call_is_any_stonith(["R1"]),
            exit_code=1,
            stderr="Error: Only one of '--simulate', '--wait' can be used\n",
        )

    def test_simulate_safe(self):
        ctf.run(
            "resource disable R1 --simulate --safe --no-strict",
            _call_is_any_stonith(["R1"]),
            exit_code=1,
            stderr="Error: '--simulate' cannot be used with '--safe'\n",
        )

    def test_f_and_wait_mutually_exclusive(self):
        ctf.run(
            "resource disable R1 --wait -f foo",
            _call_is_any_stonith(["R1"]),
            exit_code=1,
            stderr="Error: Only one of '--wait', '-f' can be used\n",
        )


class ResourceSafeDisable(TestCase):
    def test_no_args(self):
        ctf.run(
            "resource safe-disable",
            exit_code=1,
            stderr="Error: You must specify resource(s) to disable\n",
        )

    def test_one_resource(self):
        ctf.run(
            "resource safe-disable R1",
            [
                _call_is_any_stonith(["R1"]),
                ctf.LibCallSpec("resource.disable_safe", (["R1"], True)),
            ],
        )

    def test_more_resources(self):
        ctf.run(
            "resource safe-disable R1 R2",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec("resource.disable_safe", (["R1", "R2"], True)),
            ],
        )

    def test_stonith_resource(self):
        ctf.run(
            "resource safe-disable R1 S1",
            _call_is_any_stonith(["R1", "S1"], output=True),
            exit_code=1,
            stderr=(
                "Error: This command does not accept stonith resources. "
                "Please use 'pcs stonith disable' instead.\n"
            ),
        )

    def test_no_strict(self):
        ctf.run(
            "resource safe-disable R1 R2 --no-strict",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec("resource.disable_safe", (["R1", "R2"], False)),
            ],
        )

    def test_safe_affects_other_resources(self):
        lib_reports = [
            reports.ReportItem.error(
                reports.messages.ResourceDisableAffectsOtherResources(
                    ["R1", "R2"], ["Rx"]
                )
            ),
            reports.ReportItem.info(
                reports.messages.PacemakerSimulationResult("simulate output")
            ),
        ]
        ctf.run(
            "resource safe-disable R1 R2",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec(
                    "resource.disable_safe",
                    (["R1", "R2"], True),
                    raises=LibraryError(),
                    reports=lib_reports,
                ),
            ],
            exit_code=1,
            stderr=ctf.prepare_stderr_reports(
                lib_reports, additional_error=True
            ),
        )

    def test_brief_affects_other_resources(self):
        error_report = reports.ReportItem.error(
            reports.messages.ResourceDisableAffectsOtherResources(
                ["R1", "R2"], ["Rx"]
            )
        )
        ctf.run(
            "resource safe-disable R1 R2 --brief",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec(
                    "resource.disable_safe",
                    (["R1", "R2"], True),
                    raises=LibraryError(),
                    reports=[
                        error_report,
                        reports.ReportItem.info(
                            reports.messages.PacemakerSimulationResult(
                                "simulate output"
                            )
                        ),
                    ],
                ),
            ],
            exit_code=1,
            # info reports are suppressed in brief mode
            stderr=ctf.prepare_stderr_reports(
                [error_report], additional_error=True
            ),
        )

    def test_force(self):
        ctf.run(
            "resource safe-disable R1 R2 --force",
            [
                _call_is_any_stonith(["R1", "R2"]),
                # --force skips safety checks, it is not passed to the library
                ctf.LibCallSpec("resource.disable", (["R1", "R2"], set())),
            ],
            stderr=SAFE_DISABLE_FORCE_WARNING,
        )

    def test_simulate(self):
        ctf.run(
            "resource safe-disable R1 R2 --simulate",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec(
                    "resource.disable_simulate",
                    (["R1", "R2"], True),
                    output=_fixture_simulate_output(),
                ),
            ],
            stdout="simulate output\n",
        )

    def test_simulate_no_strict(self):
        ctf.run(
            "resource safe-disable R1 --simulate --no-strict",
            [
                _call_is_any_stonith(["R1"]),
                ctf.LibCallSpec(
                    "resource.disable_simulate",
                    (["R1"], False),
                    output=_fixture_simulate_output(),
                ),
            ],
            stdout="simulate output\n",
        )

    def test_simulate_brief(self):
        ctf.run(
            "resource safe-disable R1 R2 --simulate --brief",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec(
                    "resource.disable_simulate",
                    (["R1", "R2"], True),
                    output=_fixture_simulate_output(),
                ),
            ],
            stdout="Rx\nRy\n",
        )

    def test_simulate_brief_no_strict(self):
        ctf.run(
            "resource safe-disable R1 R2 --simulate --brief --no-strict",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec(
                    "resource.disable_simulate",
                    (["R1", "R2"], False),
                    output=_fixture_simulate_output(),
                ),
            ],
            stdout="Rx\nRy\n",
        )

    def test_simulate_brief_nothing_affected(self):
        ctf.run(
            "resource safe-disable R1 R2 --simulate --brief --no-strict",
            [
                _call_is_any_stonith(["R1", "R2"]),
                ctf.LibCallSpec(
                    "resource.disable_simulate",
                    (["R1", "R2"], False),
                    output=_fixture_simulate_output(resources=[]),
                ),
            ],
        )

    def test_simulate_wait(self):
        ctf.run(
            "resource safe-disable R1 --simulate --wait",
            _call_is_any_stonith(["R1"]),
            exit_code=1,
            stderr="Error: Only one of '--simulate', '--wait' can be used\n",
        )

    def test_simulate_force(self):
        ctf.run(
            "resource safe-disable R1 --simulate --force",
            exit_code=1,
            stderr="Error: '--force' cannot be used with '--simulate'\n",
        )

    def test_simulate_no_strict_force(self):
        ctf.run(
            "resource safe-disable R1 --simulate --no-strict --force",
            exit_code=1,
            stderr=(
                "Error: '--force' cannot be used with '--no-strict', "
                "'--simulate'\n"
            ),
        )

    def test_force_no_strict(self):
        ctf.run(
            "resource safe-disable R1 --force --no-strict",
            exit_code=1,
            stderr="Error: '--force' cannot be used with '--no-strict'\n",
        )

    def test_f_not_supported(self):
        ctf.run(
            "resource safe-disable R1 -f foo",
            exit_code=1,
            stderr=(
                "Error: Specified option '-f' is not supported in this "
                "command\n"
            ),
        )
