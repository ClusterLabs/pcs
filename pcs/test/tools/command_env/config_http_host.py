import json

from pcs import settings
from pcs.test.tools.command_env.mock_node_communicator import (
    place_communication,
    place_multinode_call,
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

    def get_host_info(
        self, node_labels=None, output_data=None, communication_list=None,
        name="http.host.get_host_info",
    ):
        """
        Create a call for getting overall info about a host

        node_labels list -- create success responses from these nodes
        output_data dict -- default output data which will be converted to JSON
        communication_list list -- create custom responses
        name string -- the key of this call
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/check_host",
            output=json.dumps(output_data) if output_data else "",
        )

    def cluster_destroy(
        self, node_labels=None, communication_list=None,
        name="http.host.cluster_destroy",
    ):
        """
        Create a call for destroying a cluster on the hosts

        node_labels list -- create success responses from these nodes
        communication_list list -- create custom responses
        name string -- the key of this call
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/cluster_destroy",
        )

    def update_known_hosts(
        self, node_labels=None, to_add=None, to_add_hosts=None,
        communication_list=None, name="http.host.update_known_hosts",
    ):
        """
        Create a call for updating known hosts on the hosts.

        node_labels list -- create success responses from these nodes
        dict to_add -- records to add:
                {host_name: {dest_list: [{"addr": , "port": ,}]}}
        list to_add_hosts -- constructs to_add from host names
        communication_list list -- create custom responses
        name string -- the key of this call
        """
        if to_add_hosts and to_add:
            raise AssertionError(
                "Cannot specify both 'to_add_hosts' and 'to_add'"
            )
        if to_add_hosts:
            to_add = {
                name: {
                    "dest_list": [
                        {"addr": name, "port": settings.pcsd_default_port}
                    ]
                }
                for name in to_add_hosts
            }
        add_with_token = {
            name: dict(data, token=None)
            for name, data in to_add.items()
        }
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/known_hosts_change",
            param_list=[(
                "data_json",
                json.dumps(dict(
                    known_hosts_add=add_with_token,
                    known_hosts_remove={}
                ))
            )],
        )

    def enable_cluster(
        self, node_labels=None, communication_list=None,
        name="http.host.enable_cluster",
    ):
        """
        Create a call for enabling cluster on the nodes.

        node_labels list -- create success responses from these nodes
        communication_list list -- create custom responses
        name string -- the key of this call
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/cluster_enable",
        )

    def start_cluster(
        self, node_labels=None, communication_list=None,
        name="http.host.start_cluster",
    ):
        """
        Create a call for starting cluster on the nodes.

        node_labels list -- create success responses from these nodes
        communication_list list -- create custom responses
        name string -- the key of this call
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/cluster_start",
        )

    def check_pacemaker_started(
        self, pacemaker_started_node_list=(),
        pacemaker_not_started_node_list=(), communication_list=None,
        name="http.host.check_pacemaker_started",
    ):
        """
        Create a call for checking pacemaker status on nodes.

        pacemaker_started_node_list list -- list of node names on which
            pacemaker is fully running
        pacemaker_not_started_node_list list -- listof node names on which
            pacemaker is not fully started yet
        communication_list list -- create custom responses
        name string -- the key of this call
        """
        if (
            bool(pacemaker_started_node_list or pacemaker_not_started_node_list)
            ==
            bool(communication_list)
        ):
            raise AssertionError(
                "Exactly one of 'pacemaker_started_node_list and/or "
                "pacemaker_not_started_node_list', 'communication_list' must "
                "be specified"
            )
        if not communication_list:
            communication_list = [
                dict(
                    label=node,
                    output=json.dumps(dict(
                        pending=False,
                        online=True,
                    ))
                ) for node in pacemaker_started_node_list
            ] + [
                dict(
                    label=node,
                    output=json.dumps(dict(
                        pending=True,
                        online=False,
                    ))
                ) for node in pacemaker_not_started_node_list
            ]

        place_communication(
            self.__calls,
            name,
            communication_list,
            action="remote/pacemaker_node_status",
        )
