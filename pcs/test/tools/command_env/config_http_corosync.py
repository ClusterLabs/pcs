from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.command_env.mock_node_communicator import(
    AddRequestCall,
    create_communication,
    StartLoopCall,
)

class CorosyncShortcuts(object):
    def __init__(self, calls):
        self.__calls = calls

    def _check_node_labels_and_communication_list(
        self, node_labels, communication_list
    ):
        if (
            (not node_labels and not communication_list)
            or
            (node_labels and communication_list)
        ):
            raise AssertionError(
                "Exactly one of 'node_labels', 'communication_list' "
                "must be specified"
            )

    def _qdevice_client_call(
        self, name, action, output, node_labels=None, communication_list=None
    ):
        self._check_node_labels_and_communication_list(
            node_labels, communication_list
        )
        communication_list = communication_list or [
            {"label": label} for label in node_labels
        ]
        request_list, response_list = create_communication(
            communication_list,
            action=action,
            response_code=200,
            output=output
        )

        self.__calls.place(
            "{0}_requests".format(name),
            AddRequestCall(request_list),
        )
        self.__calls.place(
            "{0}_responses".format(name),
            StartLoopCall(response_list),
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
        self._qdevice_client_call(
            name,
            "remote/qdevice_client_enable",
            "corosync-qdevice enabled",
            node_labels,
            communication_list
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
        self._qdevice_client_call(
            name,
            "remote/qdevice_client_disable",
            "corosync-qdevice disabled",
            node_labels,
            communication_list
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
        self._qdevice_client_call(
            name,
            "remote/qdevice_client_start",
            "corosync-qdevice started",
            node_labels,
            communication_list
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
        self._qdevice_client_call(
            name,
            "remote/qdevice_client_stop",
            "corosync-qdevice stopped",
            node_labels,
            communication_list
        )
