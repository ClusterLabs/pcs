from pcs.test.tools.command_env.mock_node_communicator import (
    place_multinode_call
)

class HostShortcuts(object):
    def __init__(self, calls):
        self.__calls = calls

    def check_auth(
        self, node_labels=None, communication_list=None,
        name="http.host.check_auth"
    ):
        """
        Create a call for checking authentication on hosts

        node_labels list -- create success responses from these nodes
        communication_list list -- create custom responses
        name string -- the key of this call
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/check_auth",
            output='{"success":true}',
            param_list=[("check_auth_only", 1)],
        )
