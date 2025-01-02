import json

from pcs_test.tools.command_env.mock_node_communicator import (
    place_multinode_call,
)


class StatusShortcuts:
    def __init__(self, calls):
        self.__calls = calls

    def get_full_cluster_status_plaintext(  # noqa: PLR0913
        self,
        *,
        node_labels=None,
        communication_list=None,
        name="http.status.get_full_cluster_status_plaintext",
        hide_inactive_resources=False,
        verbose=False,
        cmd_status="success",
        cmd_status_msg="",
        report_list=None,
        cluster_status_plaintext="",
    ):
        # pylint: disable=too-many-arguments
        """
        Create a call for getting cluster status in plaintext

        node_labels list -- create success responses from these nodes
        communication_list list -- create custom responses
        name string -- the key of this call
        bool hide_inactive_resources -- input flag
        bool verbose -- input flag
        string cmd_status -- did the command succeed?
        string_cmd_status_msg -- details for cmd_status
        iterable report_list -- reports from a remote node
        string cluster_status_plaintext -- resulting cluster status
        """
        report_list = report_list or []
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/cluster_status_plaintext",
            param_list=[
                (
                    "data_json",
                    json.dumps(
                        dict(
                            hide_inactive_resources=hide_inactive_resources,
                            verbose=verbose,
                        )
                    ),
                )
            ],
            output=json.dumps(
                dict(
                    status=cmd_status,
                    status_msg=cmd_status_msg,
                    data=cluster_status_plaintext,
                    report_list=report_list,
                )
            ),
        )
