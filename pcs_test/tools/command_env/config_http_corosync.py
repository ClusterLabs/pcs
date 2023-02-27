import base64
import json

from pcs_test.tools.command_env.mock_node_communicator import (
    place_multinode_call,
)


def corosync_running_check_response(running):
    return json.dumps(
        {
            "node": {
                "corosync": running,
                "services": {
                    "corosync": {
                        "installed": True,
                        "enabled": not running,
                        "running": running,
                    }
                },
            }
        }
    )


class CorosyncShortcuts:
    def __init__(self, calls):
        self.__calls = calls

    def check_corosync_offline(
        self,
        node_labels=None,
        communication_list=None,
        name="http.corosync.check_corosync_offline",
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
            param_list=[("version", "2")],
            output=corosync_running_check_response(False),
        )

    def get_corosync_online_targets(
        self,
        node_labels=None,
        communication_list=None,
        name="http.corosync.get_corosync_online_targets",
    ):
        """
        Create a call for getting corosync online targets

        list node_labels -- create success responses from these nodes
        list communication_list -- create custom responses
        string name -- the key of this call
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/status",
            param_list=[("version", "2")],
            output=corosync_running_check_response(True),
        )

    def get_corosync_conf(
        self,
        corosync_conf="",
        node_labels=None,
        communication_list=None,
        name="http.corosync.get_corosync_conf",
    ):
        """
        Create a call for loading corosync.conf text from remote nodes

        string corosync_conf -- corosync.conf text to be loaded
        list node_labels -- create success responses from these nodes
        list communication_list -- create custom responses
        string name -- the key of this call
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/get_corosync_conf",
            output=corosync_conf,
        )

    def set_corosync_conf(
        self,
        corosync_conf,
        node_labels=None,
        communication_list=None,
        name="http.corosync.set_corosync_conf",
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

    def reload_corosync_conf(
        self,
        node_labels=None,
        communication_list=None,
        name="http.corosync.reload_corosync_conf",
    ):
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/reload_corosync_conf",
            output=json.dumps(dict(code="reloaded", message="")),
        )

    def qdevice_client_enable(
        self,
        name="http.corosync.qdevice_client_enable",
        node_labels=None,
        communication_list=None,
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
        self,
        name="http.corosync.qdevice_client_disable",
        node_labels=None,
        communication_list=None,
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
        self,
        name="http.corosync.qdevice_client_start",
        node_labels=None,
        communication_list=None,
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
        self,
        name="http.corosync.qdevice_client_stop",
        node_labels=None,
        communication_list=None,
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

    def qdevice_net_get_ca_cert(
        self,
        ca_cert=b"ca_cert",
        node_labels=None,
        communication_list=None,
        name="http.corosync.qdevice_net_get_ca_cert",
    ):
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/qdevice_net_get_ca_certificate",
            output=base64.b64encode(ca_cert),
        )

    def qdevice_net_client_setup(
        self,
        ca_cert=b"ca_cert",
        node_labels=None,
        communication_list=None,
        name="http.corosync.qdevice_net_client_setup",
        before=None,
    ):
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/qdevice_net_client_init_certificate_storage",
            param_list=[("ca_certificate", base64.b64encode(ca_cert))],
            before=before,
        )

    def qdevice_net_sign_certificate(
        self,
        cluster_name,
        cert=b"cert",
        signed_cert=b"signed cert",
        node_labels=None,
        communication_list=None,
        name="http.corosync.qdevice_net_sign_certificate",
    ):
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/qdevice_net_sign_node_certificate",
            param_list=[
                ("certificate_request", base64.b64encode(cert)),
                ("cluster_name", cluster_name),
            ],
            output=base64.b64encode(signed_cert),
        )

    def qdevice_net_client_import_cert_and_key(
        self,
        cert=b"pk12 cert",
        node_labels=None,
        communication_list=None,
        name="http.corosync.qdevice_net_client_import_cert_and_key",
    ):
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/qdevice_net_client_import_certificate",
            param_list=[("certificate", base64.b64encode(cert))],
        )
