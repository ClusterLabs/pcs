from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.command_env.mock_fs import Call as FsCall


class FsConfig(object):
    def __init__(self, call_collection):
        self.__calls = call_collection

    def open(
        self, path, return_value, name="fs.open", mode="r",
        before=None, instead=None
    ):
        call = FsCall(
            "open",
            call_kwargs={"name": path, "mode": mode},
            # TODO use mock_open here. Allow to use simply "read_data",
            # "side_effect" etc. It depends on future use cases...
            return_value=return_value,
        )
        self.__calls.place(name, call, before, instead)

    def exists(
        self, path, return_value="", name="fs.exists", before=None, instead=None
    ):
        call = FsCall(
            "os.path.exists",
            call_kwargs={"path": path},
            return_value=return_value,
        )
        self.__calls.place(name, call, before, instead)
