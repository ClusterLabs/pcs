import json

from pcs import settings
from pcs.test.tools.command_env.mock_node_communicator import (
    place_multinode_call
)

def dest_dict_fixture(addr, port=settings.pcsd_default_port):
    return dict(
        addr=addr,
        port=port,
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
        # TODO
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
        # TODO
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/cluster_destroy",
        )

    def update_known_hosts(
        self, node_labels=None, to_add=None, communication_list=None,
        name="http.host.update_known_hosts",
    ):
        """
        # TODO
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/known_hosts_change",
            param_list=[(
                "data_json",
                json.dumps(dict(
                    known_hosts_add={
                        host: dict(
                            dest_list=[dest_dict_fixture(host)],
                            token=None,
                        ) for host in to_add
                    },
                    known_hosts_remove={}
                ))
            )],
        )

    def enable_cluster(
        self, node_labels=None, communication_list=None,
        name="http.host.enable_cluster",
    ):
        """
        # TODO
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
        # TODO
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/cluster_start",
        )

    def check_pacemaker_started(
        self, node_labels=None, communication_list=None,
        name="http.host.check_pacemaker_started",
    ):
        """
        # TODO
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/pacemaker_node_status",
            output=json.dumps(dict(
                pending=False,
                online=True,
            ))
        )
