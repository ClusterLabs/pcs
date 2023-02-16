from pcs_test.tools.command_env.mock_fs import Call as FsCall


class FsConfig:
    """
    Any new call must be manually added to the patch_env function in the
    pcs_test.tools.command_env.assistant module otherwise it will be ignored!
    Also its arguments must be described in the _FUNC_ARGS mapping in the
    pcs_test.tools.command_env.mock_fs module.
    """

    def __init__(self, call_collection):
        self.__calls = call_collection

    def open(
        self,
        path,
        return_value=None,
        side_effect=None,
        name="fs.open",
        mode="r",
        before=None,
        instead=None,
    ):
        call = FsCall(
            "open",
            call_kwargs={"name": path, "mode": mode},
            # TODO use mock_open here. Allow to use simply "read_data",
            # "side_effect" etc. It depends on future use cases...
            return_value=return_value,
            side_effect=side_effect,
        )
        self.__calls.place(name, call, before, instead)

    def exists(
        self,
        path,
        return_value=True,
        name="fs.exists",
        before=None,
        instead=None,
    ):
        call = FsCall(
            "os.path.exists",
            call_kwargs={"path": path},
            return_value=return_value,
        )
        self.__calls.place(name, call, before, instead)

    def chmod(
        self,
        path,
        mode,
        side_effect=None,
        name="os.chmod",
        before=None,
        instead=None,
    ):
        call = FsCall(
            "os.chmod",
            call_kwargs=dict(
                fd=path,
                mode=mode,
            ),
            side_effect=side_effect,
        )
        self.__calls.place(name, call, before, instead)

    def chown(
        self,
        path,
        uid,
        gid,
        side_effect=None,
        name="os.chown",
        before=None,
        instead=None,
    ):
        call = FsCall(
            "os.chown",
            call_kwargs=dict(
                fd=path,
                uid=uid,
                gid=gid,
            ),
            side_effect=side_effect,
        )
        self.__calls.place(name, call, before, instead)

    def isfile(
        self,
        path,
        return_value=True,
        name="fs.isfile",
        before=None,
        instead=None,
    ):
        call = FsCall(
            "os.path.isfile",
            call_kwargs={"path": path},
            return_value=return_value,
        )
        self.__calls.place(name, call, before, instead)

    def isdir(
        self,
        path,
        return_value=True,
        name="fs.isdir",
        before=None,
        instead=None,
    ):
        call = FsCall(
            "os.path.isdir",
            call_kwargs={"path": path},
            return_value=return_value,
        )
        self.__calls.place(name, call, before, instead)

    def listdir(
        self,
        path,
        return_value=(),
        name="fs.listdir",
        before=None,
        instead=None,
    ):
        call = FsCall(
            "os.listdir",
            call_kwargs={"path": path},
            return_value=list(return_value),
        )
        self.__calls.place(name, call, before, instead)

    def rmtree(
        self,
        path,
        return_value=None,
        name="fs.rmtree",
        before=None,
        instead=None,
    ):
        call = FsCall(
            "shutil.rmtree",
            call_kwargs={"path": path},
            return_value=return_value,
        )
        self.__calls.place(name, call, before, instead)

    def makedirs(
        self,
        path,
        mode,
        side_effect=None,
        name="fs.rmtree",
        before=None,
        instead=None,
    ):
        call = FsCall(
            "os.makedirs",
            call_kwargs={"path": path, "mode": mode},
            side_effect=side_effect,
        )
        self.__calls.place(name, call, before, instead)
