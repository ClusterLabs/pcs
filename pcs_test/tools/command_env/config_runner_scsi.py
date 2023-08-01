import os.path

from pcs import settings

from pcs_test.tools.command_env.mock_runner import Call as RunnerCall


class ScsiShortcuts:
    def __init__(self, calls):
        self.__calls = calls

    def unfence_node(
        self,
        plug,
        devices,
        fence_agent,
        stdout="",
        stderr="",
        return_code=0,
        name="runner.scsi.unfence_node",
    ):
        """
        Create a calls for node scsi/mpath unfencing

        string plug -- a nodename or key for fence_scsi/fence_mpath agents
        list devices -- list of devices to unfence
        string fence_agent -- name of fence agent script
        string stdout -- stdout from fence agent script
        string stderr -- stderr from fence agent script
        int return_code -- return code of the fence agent script
        string name -- the key of this call
        """
        self.__calls.place(
            name,
            RunnerCall(
                [
                    os.path.join(settings.fence_agent_execs, fence_agent),
                    "--action=on",
                    "--devices",
                    ",".join(sorted(devices)),
                    f"--plug={plug}",
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
        fence_agent,
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
                    os.path.join(settings.fence_agent_execs, fence_agent),
                    "--action=status",
                    f"--devices={device}",
                    f"--plug={node}",
                ],
                stdout=stdout,
                stderr=stderr,
                returncode=return_code,
            ),
        )
