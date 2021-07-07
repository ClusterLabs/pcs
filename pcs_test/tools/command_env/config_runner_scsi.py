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
        self.__calls.place(
            name,
            RunnerCall(
                [
                    os.path.join(settings.fence_agent_binaries, "fence_scsi"),
                    "--action=on",
                    "--devices",
                    ",".join(devices),
                    f"--plug={node}",
                ],
                stdout=stdout,
                stderr=stderr,
                returncode=return_code,
            ),
        )
