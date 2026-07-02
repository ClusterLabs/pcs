CALL_TYPE_FCNTL = "CALL_TYPE_FCNTL"

_FUNC_ARGS = {"flock": ["fd", "operation"]}


def _ensure_consistent_args(func_name, call_args, call_kwargs):
    if len(call_args) > len(_FUNC_ARGS[func_name]):
        raise AssertionError(
            "{0}() too many positional arguments ({1} > {2})".format(
                func_name, len(call_args), len(_FUNC_ARGS[func_name])
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
    type = CALL_TYPE_FCNTL

    def __init__(
        self, func_name, return_value=None, side_effect=None, call_kwargs=None
    ):
        call_kwargs = call_kwargs if call_kwargs else {}

        self.type = CALL_TYPE_FCNTL
        self.func_name = func_name
        self.call_kwargs = call_kwargs
        self.return_value = return_value
        self.side_effect = side_effect

    def finish(self):
        if self.side_effect:
            if isinstance(self.side_effect, Exception):
                raise self.side_effect
            raise AssertionError(
                "side_effect other than instance of exception not supported yet"
            )

        return self.return_value

    def __repr__(self):
        return "<Fcntl '{0}' kwargs={1}>".format(
            self.func_name,
            self.call_kwargs,
        )

    def __ne__(self, other):
        return (
            self.func_name != other.func_name
            or self.call_kwargs != other.call_kwargs
        )


def get_fcntl_mock(call_queue):
    def get_fcntl_call(func_name, _original_call):
        def call_fcntl(*args, **kwargs):
            real_call = Call(
                func_name,
                call_kwargs=_get_all_args_as_kwargs(func_name, args, kwargs),
            )
            dummy_i, expected_call = call_queue.take(
                CALL_TYPE_FCNTL, repr(real_call)
            )

            if expected_call != real_call:
                raise call_queue.error_with_context(
                    "\n  expected: '{0}'\n  but was:  '{1}'".format(
                        expected_call, real_call
                    )
                )

            return expected_call.finish()

        return call_fcntl

    return get_fcntl_call


def is_fcntl_call_in(call_queue):
    return call_queue.has_type(CALL_TYPE_FCNTL)
