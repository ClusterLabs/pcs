from pcs import settings
from pcs.lib.sbd import DEVICE_INITIALIZATION_OPTIONS_MAPPING

from pcs_test.tools.command_env.mock_runner import Call as RunnerCall


class SbdShortcuts:
    def __init__(self, calls):
        self.__calls = calls

    def list_watchdogs(
        self,
        output,
        name="runner.sbd.list_watchdogs",
        stderr="",
        returncode=0,
        instead=None,
        before=None,
    ):
        self.__calls.place(
            name,
            RunnerCall(
                [settings.sbd_exec, "query-watchdog"],
                stdout=output,
                stderr=stderr,
                returncode=returncode,
            ),
            before=before,
            instead=instead,
        )

    def initialize_devices(
        self,
        devices,
        options,
        stdout="",
        stderr="",
        return_code=0,
        name="runner.sbd.initialize_devices",
    ):
        cmd = [settings.sbd_exec]
        for device in devices:
            cmd += ["-d", device]

        for opt, val in sorted(options.items()):
            cmd += [DEVICE_INITIALIZATION_OPTIONS_MAPPING[opt], str(val)]

        cmd.append("create")
        self.__calls.place(
            name,
            RunnerCall(
                cmd,
                stdout=stdout,
                stderr=stderr,
                returncode=return_code,
            ),
        )

    def get_device_info(
        self,
        device,
        stdout="",
        stderr="",
        return_code=0,
        name="runner.sbd.device.list",
    ):
        self.__calls.place(
            name,
            RunnerCall(
                [settings.sbd_exec, "-d", device, "list"],
                stdout=stdout,
                stderr=stderr,
                returncode=return_code,
            ),
        )

    def get_device_dump(
        self,
        device,
        stdout="",
        stderr="",
        return_code=0,
        name="runner.sbd.device.dump",
    ):
        self.__calls.place(
            name,
            RunnerCall(
                [settings.sbd_exec, "-d", device, "dump"],
                stdout=stdout,
                stderr=stderr,
                returncode=return_code,
            ),
        )

    def set_device_message(
        self,
        device,
        node,
        message,
        stdout="",
        stderr="",
        return_code=0,
        name="runner.sbd.device.set_message",
    ):
        self.__calls.place(
            name,
            RunnerCall(
                [settings.sbd_exec, "-d", device, "message", node, message],
                stdout=stdout,
                stderr=stderr,
                returncode=return_code,
            ),
        )
