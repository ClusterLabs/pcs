from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.command_env.mock_node_communicator import (
    place_multinode_call
)

class PcmkShortcuts(object):
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
