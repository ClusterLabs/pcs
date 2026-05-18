from pcs_test.tools.command_env.mock_fcntl import Call as FcntlCall


class FcntlConfig:
    """
    Any new call must be manually added to the patch_env function in the
    pcs_test.tools.command_env.assistant module otherwise it will be ignored!
    Also its arguments must be described in the _FUNC_ARGS mapping in the
    pcs_test.tools.command_env.mock_fcntl module.
    """

    def __init__(self, call_collection):
        self.__calls = call_collection

    def flock(self, mock_file, operation, side_effect=None, name="fcntl.flock"):
        call = FcntlCall(
            "flock",
            call_kwargs={
                "fd": mock_file.fileno.return_value,
                "operation": operation,
            },
            side_effect=side_effect,
        )
        self.__calls.place(name, call)
