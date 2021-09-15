import json

from pcs.common import communication
from pcs.common.interface.dto import to_dict

from pcs_test.tools.command_env.mock_node_communicator import (
    place_communication,
)


class ScsiShortcuts:
    def __init__(self, calls):
        self.__calls = calls

    def unfence_node(
        self,
        original_devices=(),
        updated_devices=(),
        node_labels=None,
        communication_list=None,
        name="http.scsi.unfence_node",
    ):
        """
        Create a calls for node unfencing

        list original_devices -- list of scsi devices before an update
        list updated_devices -- list of scsi devices after an update
        list node_labels -- create success responses from these nodes
        list communication_list -- use these custom responses
        string name -- the key of this call
        """
        if (node_labels is None and communication_list is None) or (
            node_labels and communication_list
        ):
            raise AssertionError(
                "Exactly one of 'node_labels', 'communication_list' "
                "must be specified"
            )

        if node_labels:
            communication_list = [
                dict(
                    label=node,
                    raw_data=json.dumps(
                        dict(
                            node=node,
                            original_devices=original_devices,
                            updated_devices=updated_devices,
                        )
                    ),
                )
                for node in node_labels
            ]
        place_communication(
            self.__calls,
            name,
            communication_list,
            action="api/v1/scsi-unfence-node/v2",
            output=json.dumps(
                to_dict(
                    communication.dto.InternalCommunicationResultDto(
                        status=communication.const.COM_STATUS_SUCCESS,
                        status_msg=None,
                        report_list=[],
                        data=None,
                    )
                )
            ),
        )
