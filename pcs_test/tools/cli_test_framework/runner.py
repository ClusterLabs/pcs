import contextlib
import io
import shlex
from unittest import mock

from pcs import app, settings, utils
from pcs import usage as _usage
from pcs.cli.common.parse_args import InputModifiers
from pcs.cli.reports.processor import ReportProcessorToConsole
from pcs.common.reports import ReportItemList

from pcs_test.tools.cli_test_framework.mock_lib_wrapper import (
    LibCallSpec,
    MockLibrary,
)


class _SupportedFlagsTracker:
    def __init__(self, expected_flags: list[str]) -> None:
        self._expected_flags = set(expected_flags)
        self._recorded_flags: tuple[str, ...] | None = None
        self._real_ensure = InputModifiers.ensure_only_supported

    def patch(self):
        def ensure_tracking(modifiers, *flags, **kwargs):
            if self._recorded_flags is None:
                self._recorded_flags = tuple(flags)
            else:
                raise AssertionError(
                    f"Called ensure_only_supported multiple times, but only one"
                    " call is expected.\n"
                    f"  Last called flags:\n    {flags}\n"
                    f"  Last called kwargs:\n    {kwargs}\n"
                    f"  Previously recorded flags:\n    {self._recorded_flags}\n"
                )
            return self._real_ensure(modifiers, *flags, **kwargs)

        return mock.patch.object(
            InputModifiers,
            "ensure_only_supported",
            ensure_tracking,
        )

    def assert_flags_match_raise(self, argv: list[str]) -> None:
        if self._recorded_flags is None:
            raise AssertionError(
                f"ensure_only_supported was never called for command {argv},"
                " but it is expected to be called once."
            )
        if set(self._recorded_flags) != self._expected_flags:
            raise AssertionError(
                f"supported flags mismatch for command {argv}\n"
                f"  Expected flags:\n    {self._expected_flags}\n"
                f"  Recorded flags:\n    {set(self._recorded_flags)}\n"
            )


class _PreserveAttrs:
    def __init__(self, *attrs: tuple[object, str]) -> None:
        self._attrs = attrs
        self._saved: list[object] = []

    def __enter__(self) -> "_PreserveAttrs":
        self._saved = [getattr(obj, name) for obj, name in self._attrs]
        return self

    def __exit__(self, *exc_info: object) -> None:
        for (obj, name), value in zip(self._attrs, self._saved, strict=True):
            setattr(obj, name, value)


def run(
    command: str | list[str],
    lib_calls: list[LibCallSpec] | LibCallSpec | None = None,
    exit_code: int | str | None = 0,
    stdout: str = "",
    stderr: str = "",
    supported_flags: list[str] | None = None,
) -> None:
    argv = shlex.split(command) if isinstance(command, str) else list(command)
    if lib_calls is None:
        lib_calls = []
    elif isinstance(lib_calls, LibCallSpec):
        lib_calls = [lib_calls]

    mock_lib = MockLibrary(lib_calls)

    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    actual_exit_code: str | int | None = 0
    flags_tracker = (
        _SupportedFlagsTracker(supported_flags)
        if supported_flags is not None
        else None
    )

    with contextlib.ExitStack() as stack:
        # These globals get mutated while a command runs. They would leak into
        # later tests, so we snapshot them here and restore the originals
        # on exit.
        stack.enter_context(
            _PreserveAttrs(
                (app, "usefile"),
                (app, "filename"),
                (utils, "usefile"),
                (utils, "filename"),
                (utils, "pcs_options"),
                (settings, "corosync_conf_file"),
            )
        )
        stack.enter_context(mock.patch("os.getuid", return_value=0))
        stack.enter_context(
            mock.patch(
                "pcs.utils.get_library_wrapper",
                return_value=mock_lib,
            )
        )
        stack.enter_context(contextlib.redirect_stdout(captured_stdout))
        stack.enter_context(contextlib.redirect_stderr(captured_stderr))

        if flags_tracker is not None:
            stack.enter_context(flags_tracker.patch())

        try:
            app.main(argv)
        except SystemExit as e:
            actual_exit_code = e.code

    captured_stdout_str = captured_stdout.getvalue()
    captured_stderr_str = captured_stderr.getvalue()

    if actual_exit_code != exit_code:
        raise AssertionError(
            f"Exit code mismatch for command {argv}:"
            f" expected {exit_code}, got {actual_exit_code}\n"
            f"  stdout expected:\n    {stdout}\n"
            f"  stdout actual:\n    {captured_stdout_str}\n"
            f"  stderr expected:\n    {stderr}\n"
            f"  stderr actual:\n    {captured_stderr_str}"
        )

    if captured_stdout_str != stdout:
        raise AssertionError(
            f"stdout mismatch for command {argv}:\n"
            f"  Expected:\n    {stdout}\n"
            f"  Actual:\n    {captured_stdout_str}"
        )

    if captured_stderr_str != stderr:
        raise AssertionError(
            f"stderr mismatch for command {argv}:\n"
            f"  Expected:\n    {stderr}\n"
            f"  Actual:\n    {captured_stderr_str}"
        )

    mock_lib.assert_exhausted()

    if flags_tracker is not None:
        flags_tracker.assert_flags_match_raise(argv)


def prepare_stderr_usage(command: str, subcommand: str) -> str:
    usage_fn = getattr(_usage, command)
    return usage_fn([subcommand]) + "\n"


def prepare_stderr_reports(
    lib_reports: ReportItemList | None = None,
    additional_error: bool = False,
) -> str:
    captured_stderr = io.StringIO()
    if lib_reports:
        with contextlib.redirect_stderr(captured_stderr):
            ReportProcessorToConsole(debug=False).report_list(lib_reports)
    stderr = captured_stderr.getvalue()

    if additional_error:
        stderr = (
            stderr + "Error: Errors have occurred, "
            "therefore pcs is unable to continue\n"
        )

    return stderr
