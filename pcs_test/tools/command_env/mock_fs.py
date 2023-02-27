import site

from pcs_test import PROJECT_ROOT

CALL_TYPE_FS = "CALL_TYPE_FS"

_FUNC_ARGS = {
    "open": ["name", "mode", "buffering"],
    "os.path.exists": ["path"],
    "os.path.isdir": ["path"],
    "os.path.isfile": ["path"],
    "os.chmod": ["fd", "mode"],
    "os.chown": ["fd", "uid", "gid"],
    "os.listdir": ["path"],
    "shutil.rmtree": ["path"],
    "os.makedirs": ["path", "mode"],
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

    param_intersection = set(
        _FUNC_ARGS[func_name][: len(call_args)]
    ).intersection(call_kwargs.keys())
    if param_intersection:
        raise TypeError(
            "{0}() got multiple values for keyword argument(s) '{1}'".format(
                func_name, "', '".join(param_intersection)
            )
        )


def _get_all_args_as_kwargs(func_name, call_args, call_kwargs):
    _ensure_consistent_args(func_name, call_args, call_kwargs)
    kwargs = call_kwargs.copy()
    for i, arg in enumerate(call_args):
        kwargs[_FUNC_ARGS[func_name][i]] = arg
    return kwargs


class Call:
    type = CALL_TYPE_FS

    def __init__(
        self, func_name, return_value=None, side_effect=None, call_kwargs=None
    ):
        """
        callable check_stdin raises AssertionError when given stdin doesn't
            match
        """
        call_kwargs = call_kwargs if call_kwargs else {}

        # TODO side effect with return_value - mutually exclusive

        self.type = CALL_TYPE_FS
        self.func_name = func_name
        self.call_kwargs = call_kwargs
        self.return_value = return_value
        self.side_effect = side_effect

    def finish(self):
        if self.side_effect:
            if isinstance(self.side_effect, Exception):
                # pylint: disable=raising-bad-type
                raise self.side_effect
            raise AssertionError(
                "side_effect other than instance of exception not supported yet"
            )

        return self.return_value

    def __repr__(self):
        return str("<Fs '{0}' kwargs={1}>").format(
            self.func_name,
            self.call_kwargs,
        )

    def __ne__(self, other):
        return (
            self.func_name != other.func_name
            or self.call_kwargs != other.call_kwargs
        )


def get_fs_mock(call_queue):
    package_dir_list = site.getsitepackages()
    package_dir_list.append(PROJECT_ROOT)

    def get_fs_call(func_name, original_call):
        def call_fs(*args, **kwargs):
            # Standard python unittest tries to open some python code (e.g. the
            # test file for caching  when the test raises AssertionError).
            # It is before it the cleanup is called so at this moment the
            # function open is still mocked.
            # Pcs should not open file inside python package in the command so
            # attempt to open file inside pcs package is almost certainly
            # outside of library command and we will provide the original
            # function.
            if func_name == "open":
                for python_package_dir in package_dir_list:
                    if args[0].startswith(python_package_dir):
                        return original_call(*args, **kwargs)

            real_call = Call(
                func_name,
                call_kwargs=_get_all_args_as_kwargs(func_name, args, kwargs),
            )
            dummy_i, expected_call = call_queue.take(
                CALL_TYPE_FS, repr(real_call)
            )

            if expected_call != real_call:
                raise call_queue.error_with_context(
                    "\n  expected: '{0}'\n  but was:  '{1}'".format(
                        expected_call, real_call
                    )
                )

            return expected_call.finish()

        return call_fs

    return get_fs_call


def is_fs_call_in(call_queue):
    return call_queue.has_type(CALL_TYPE_FS)
