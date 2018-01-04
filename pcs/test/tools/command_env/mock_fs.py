from __future__ import (
    absolute_import,
    division,
    print_function,
)

import os.path


CALL_TYPE_FS = "CALL_TYPE_FS"

_FUNC_ARGS = {
    "open": ["name", "mode", "buffering"],
    "os.path.exists": ["path"],
}

def _ensure_consistent_args(func_name, call_args, call_kwargs):
    if len(call_args) > len(_FUNC_ARGS[func_name]):
        raise AssertionError(
            "{0}() too many positional arguments ({1} > {2})".format(
                func_name,
                len(call_args),
                len(_FUNC_ARGS[func_name]),
            )
        )

    param_intersection = (
        set(_FUNC_ARGS[func_name][:len(call_args)])
        .intersection(call_kwargs.keys())
    )
    if(param_intersection):
        raise TypeError(
            "{0}() got multiple values for keyword argument(s) '{1}'".format(
                func_name,
                "', '".join(param_intersection)
            )
        )

def _get_all_args_as_kwargs(func_name, call_args, call_kwargs):
    _ensure_consistent_args(func_name, call_args, call_kwargs)
    kwargs = call_kwargs.copy()
    for i, arg in enumerate(call_args):
        kwargs[_FUNC_ARGS[func_name][i]] = arg
    return kwargs

class Call(object):
    type = CALL_TYPE_FS

    def __init__(
        self, func_name, return_value=None, call_kwargs=None
    ):
        """
        callable check_stdin raises AssertionError when given stdin doesn't
            match
        """
        call_kwargs = call_kwargs if call_kwargs else {}

        self.type = CALL_TYPE_FS
        self.func_name = func_name
        self.call_kwargs = call_kwargs
        self.return_value = return_value


    def __repr__(self):
        return str("<Fs '{0}' kwargs={1}>").format(
            self.func_name,
            self.call_kwargs,
        )

    def __ne__(self, other):
        return (
            self.func_name != other.func_name
            or
            self.call_kwargs != other.call_kwargs
        )

def get_fs_mock(call_queue):
    package_dir = os.path.realpath(
        os.path.dirname(os.path.abspath(__file__))+"/../../.."
    )
    def get_fs_call(func_name, original_call):
        def call_fs(*args, **kwargs):
            # Standard python unittest tries to open the test file (for caching)
            # when the test raises AssertionError. Unittest do it before it
            # calls cleanup so at this moment the function open is still mocked.
            # Pcs should not open file inside its package in the command so
            # attempt to open file inside pcs package is almost certainly
            # outside of library command and we will provide the original
            # function.
            if func_name == "open" and args[0].startswith(package_dir):
                return original_call(*args, **kwargs)


            dummy_i, expected_call = call_queue.take(CALL_TYPE_FS)
            real_call = Call(
                func_name,
                call_kwargs=_get_all_args_as_kwargs(func_name, args, kwargs)
            )

            if expected_call != real_call:
                raise call_queue.error_with_context(
                    "\n  expected: '{0}'\n  but was:  '{1}'".format(
                        expected_call,
                        real_call
                    )
                )

            return expected_call.return_value
        return call_fs
    return get_fs_call

def is_fs_call_in(call_queue):
    return call_queue.has_type(CALL_TYPE_FS)
