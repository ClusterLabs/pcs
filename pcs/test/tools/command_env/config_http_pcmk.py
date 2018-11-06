import json

from pcs.test.tools.command_env.mock_node_communicator import (
    place_multinode_call
)

class PcmkShortcuts:
    def __init__(self, calls):
        self.__calls = calls

    def set_stonith_watchdog_timeout_to_zero(
        self, node_labels=None, communication_list=None,
        name="http.pcmk.set_stonith_watchdog_timeout_to_zero"
    ):
        """
        Create a call for setting on hosts

        node_labels list -- create success responses from these nodes
        communication_list list -- create custom responses
        name string -- the key of this call
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/set_stonith_watchdog_timeout_to_zero"
        )

    def remove_stonith_watchdog_timeout(
        self, node_labels=None, communication_list=None,
        name="http.pcmk.remove_stonith_watchdog_timeout"
    ):
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/remove_stonith_watchdog_timeout"
        )

    def remove_nodes_from_cib(
        self, nodes_to_remove, node_labels=None, communication_list=None,
        name="http.pcmk.remove_nodes_from_cib",
    ):
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/remove_nodes_from_cib",
            param_list=[
                ("data_json", json.dumps(dict(node_list=nodes_to_remove)))
            ],
            output=json.dumps(dict(
                code="success",
                message="",
            )),
        )
