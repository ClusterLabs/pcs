import inspect
from dataclasses import dataclass, field
from functools import partial
from typing import Any
from unittest import mock

from pcs.cli.common import lib_wrapper
from pcs.cli.reports.processor import ReportProcessorToConsole
from pcs.common.reports import ReportItemList


@dataclass(frozen=True)
class LibCallSpec:
    method: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any] = field(default_factory=dict)
    output: Any = None
    raises: Exception | None = None
    reports: ReportItemList = field(default_factory=list)


class MockLibrary:
    def __init__(self, calls: list[LibCallSpec]) -> None:
        self._calls = calls
        self._index = 0
        self._report_processor = ReportProcessorToConsole(debug=False)

    def __getattr__(self, module_name: str) -> Any:
        class MockModule:
            def __getattr__(_, method_name: str) -> Any:
                return partial(self._lib_call, f"{module_name}.{method_name}")

        return MockModule()

    def _lib_call(
        self,
        name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if self._index >= len(self._calls):
            raise AssertionError(
                f"Unexpected library call: {name}("
                f"{self._format_call_args(args, kwargs)})\n"
                f"All {len(self._calls)} expected call(s) were already "
                f"consumed.\n{self._format_all_calls()}"
            )

        expected = self._calls[self._index]
        self._index += 1

        if name != expected.method:
            raise AssertionError(
                f"Library call #{self._index}: expected "
                f"'{expected.method}' but got '{name}'\n"
                f"  Expected args: "
                f"{self._format_call_args(expected.args, expected.kwargs)}\n"
                f"  Actual args:   "
                f"{self._format_call_args(args, kwargs)}\n"
                f"{self._format_all_calls()}"
            )

        # Translate positional and keyword arguments into keyword arguments
        # using the real library function signature. This helps to determine if
        # the signature of function is correctly called.
        try:
            expected_kwargs = _convert_to_kwargs(
                expected.method, expected.args, expected.kwargs
            )
        except TypeError as e:
            raise AssertionError(
                f"Expected library call #{self._index} '{expected.method}' "
                f"does not match the command signature: {e}"
            ) from e
        try:
            actual_kwargs = _convert_to_kwargs(expected.method, args, kwargs)
        except TypeError as e:
            raise AssertionError(
                f"Actual library call #{self._index} '{expected.method}' "
                f"does not match the command signature: {e}"
            ) from e

        if actual_kwargs != expected_kwargs:
            raise AssertionError(
                f"Library call #{self._index} '{expected.method}': "
                f"args mismatch\n"
                f"  Expected: "
                f"{self._format_call_args(expected.args, expected.kwargs)}\n"
                f"  Actual:   "
                f"{self._format_call_args(args, kwargs)}\n"
                f"{self._format_all_calls()}"
            )

        if expected.reports:
            self._report_processor.report_list(expected.reports)

        if expected.raises is not None:
            raise expected.raises
        return expected.output

    def assert_exhausted(self) -> None:
        remaining = self._calls[self._index :]
        if remaining:
            raise AssertionError(
                f"{len(remaining)} expected library call(s) were not made:\n"
                + "\n".join(
                    f"  {i}. {call.method}("
                    f"{self._format_call_args(call.args, call.kwargs)})"
                    for i, call in enumerate(remaining, self._index + 1)
                )
            )

    @staticmethod
    def _format_call_args(
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> str:
        parts = [repr(a) for a in args]
        parts.extend(f"{k}={v!r}" for k, v in kwargs.items())
        return ", ".join(parts)

    def _format_all_calls(self) -> str:
        lines = [f"All expected calls (current index={self._index}):"]
        for i, call in enumerate(self._calls, 1):
            marker = " >>>" if i == self._index else "    "
            lines.append(
                f"{marker}{i}. {call.method}("
                f"{self._format_call_args(call.args, call.kwargs)})"
            )
        return "\n".join(lines)


def _resolve_lib_function(method: str) -> Any:
    module_name, _, method_name = method.partition(".")
    if not module_name or not method_name or "." in method_name:
        raise AssertionError(
            f"Library call name '{method}' is not in 'module.method' format"
        )
    # load_module wires real library functions through bind(). Making bind
    # return the raw function gives us a namedtuple mapping exposed names to the
    # actual library functions instead of their bound wrappers.
    with mock.patch.object(
        lib_wrapper, "bind", lambda env, run_with_middleware, fn: fn
    ):
        try:
            module = lib_wrapper.load_module(
                mock.Mock(), mock.Mock(), module_name
            )
        except Exception as e:
            raise AssertionError(
                f"Cannot resolve library module '{module_name}' "
                f"for call '{method}': {e}"
            ) from e
    try:
        return getattr(module, method_name)
    except AttributeError as e:
        raise AssertionError(
            f"Library module '{module_name}' has no command '{method_name}' "
            f"for call '{method}': {e}"
        ) from e


def _convert_to_kwargs(
    method: str, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> dict[str, Any]:
    func = _resolve_lib_function(method)
    signature = inspect.signature(func)
    # Drop the first parameter (env), which the CLI never passes.
    params = list(signature.parameters.values())[1:]
    bound = signature.replace(parameters=params).bind(*args, **kwargs)
    return dict(bound.arguments)
