import os.path

from pcs_test.tools.command_env.mock_runner import Call as RunnerCall

from pcs import settings


class ScsiShortcuts:
    def __init__(self, calls):
        self.__calls = calls

    def unfence_node(
        self,
        node,
        devices,
        stdout="",
        stderr="",
        return_code=0,
        name="runner.scsi.unfence_node",
    ):
        """
        Create a calls for node scsi unfencing

        string node -- a node from which is unfencing performed
        list devices -- list of devices to unfence
        string stdout -- stdout from fence_scsi agent script
        string stderr -- stderr from fence_scsi agent script
        int return_code -- return code of the fence_scsi agent script
        string name -- the key of this call
        """
        self.__calls.place(
            name,
            RunnerCall(
                [
                    os.path.join(settings.fence_agent_binaries, "fence_scsi"),
                    "--action=on",
                    "--devices",
                    ",".join(sorted(devices)),
                    f"--plug={node}",
                ],
                stdout=stdout,
                stderr=stderr,
                returncode=return_code,
            ),
        )

    def get_status(
        self,
        node,
        device,
        stdout="",
        stderr="",
        return_code=0,
        name="runner.scsi.is_fenced",
    ):
        """
        Create a call for getting scsi status

        string node -- a node from which is unfencing performed
        str device -- a device to check
        string stdout -- stdout from fence_scsi agent script
        string stderr -- stderr from fence_scsi agent script
        int return_code -- return code of the fence_scsi agent script
        string name -- the key of this call
        """
        self.__calls.place(
            name,
            RunnerCall(
                [
                    os.path.join(settings.fence_agent_binaries, "fence_scsi"),
                    "--action=status",
                    f"--devices={device}",
                    f"--plug={node}",
                ],
                stdout=stdout,
                stderr=stderr,
                returncode=return_code,
            ),
        )
