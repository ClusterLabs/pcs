import json
from collections.abc import Mapping

from pcs.common.file_type_codes import (
    PCS_KNOWN_HOSTS,
    PCS_SETTINGS_CONF,
    FileTypeCode,
)
from pcs.common.types import StringSequence

from pcs_test.tools.command_env.mock_node_communicator import (
    NodeCommunicatorType,
    place_multinode_call,
)


class PcsCfgsyncShortcuts:
    _FILETYPE_CODE_TO_LEGACY_NAME_MAP = {
        PCS_KNOWN_HOSTS: "known-hosts",
        PCS_SETTINGS_CONF: "pcs_settings.conf",
    }

    def __init__(self, calls):
        self.__calls = calls

    def set_configs(
        self,
        cluster_name: str = "test99",
        file_contents: Mapping[FileTypeCode, str] | None = None,
        force: bool = False,
        node_labels: StringSequence | None = None,
        communication_list: Mapping[str, str] | None = None,
        communicator_type: NodeCommunicatorType = NodeCommunicatorType.SIMPLE,
        name="http.pcs_cfgsync.set_configs",
    ):
        """
        Create a call for sending synced pcs config files to nodes

        cluster_name -- name of the cluster
        file_contents -- contents of files that are sent
        force -- whether the force flag is set in the request
        node_labels -- create success responses from these nodes
        communication_list -- create custom responses
        name -- name of this call
        """
        if file_contents:
            configs = {
                self._FILETYPE_CODE_TO_LEGACY_NAME_MAP[filetype_code]: {
                    "type": "file",
                    "text": content,
                }
                for filetype_code, content in file_contents.items()
            }
        else:
            configs = {}

        output = json.dumps(
            {"status": "ok", "result": dict.fromkeys(configs, "accepted")}
        )

        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            communicator_type,
            action="remote/set_configs",
            param_list=[
                (
                    "configs",
                    json.dumps(
                        {
                            "cluster_name": cluster_name,
                            "force": force,
                            "configs": configs,
                        }
                    ),
                )
            ],
            output=output,
        )
