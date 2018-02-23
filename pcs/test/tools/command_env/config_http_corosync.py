from pcs.test.tools.command_env.mock_node_communicator import (
    place_multinode_call
)

class CorosyncShortcuts(object):
    def __init__(self, calls):
        self.__calls = calls

    def check_corosync_offline(
        self, node_labels=None, communication_list=None,
        name="http.corosync.check_corosync_offline"
    ):
        """
        Create a call for checking that corosync is offline

        string name -- the key of this call
        list node_labels -- create success responses from these nodes
        list communication_list -- create custom responses
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/status",
            output='{"corosync":false}'
        )

    def qdevice_client_enable(
        self, name="http.corosync.qdevice_client_enable",
        node_labels=None, communication_list=None
    ):
        """
        Create a call for enabling qdevice service

        string name -- the key of this call
        list node_labels -- create success responses from these nodes
        list communication_list -- create custom responses
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/qdevice_client_enable",
            output="corosync-qdevice enabled",
        )

    def qdevice_client_disable(
        self, name="http.corosync.qdevice_client_disable",
        node_labels=None, communication_list=None
    ):
        """
        Create a call for disabling qdevice service

        string name -- the key of this call
        list node_labels -- create success responses from these nodes
        list communication_list -- create custom responses
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/qdevice_client_disable",
            output="corosync-qdevice disabled",
        )

    def qdevice_client_start(
        self, name="http.corosync.qdevice_client_start",
        node_labels=None, communication_list=None
    ):
        """
        Create a call for starting qdevice service

        string name -- the key of this call
        list node_labels -- create success responses from these nodes
        list communication_list -- create custom responses
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/qdevice_client_start",
            output="corosync-qdevice started",
        )

    def qdevice_client_stop(
        self, name="http.corosync.qdevice_client_stop",
        node_labels=None, communication_list=None
    ):
        """
        Create a call for stopping qdevice service

        string name -- the key of this call
        list node_labels -- create success responses from these nodes
        list communication_list -- create custom responses
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/qdevice_client_stop",
            output="corosync-qdevice stopped",
        )

    def set_corosync_conf(
        self, corosync_conf, node_labels=None, communication_list=None,
        name="http.corosync.set_corosync_conf"
    ):
        """
        Create a call for sending corosync.conf text

        string corosync_conf -- corosync.conf text to be sent
        list node_labels -- create success responses from these nodes
        list communication_list -- create custom responses
        string name -- the key of this call
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/set_corosync_conf",
            param_list=[("corosync_conf", corosync_conf)],
            output="Succeeded",
        )
