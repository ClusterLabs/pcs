import base64
import json

from pcs_test.tools.command_env.mock_node_communicator import (
    place_multinode_call,
)


class FilesShortcuts:
    def __init__(self, calls):
        self.__calls = calls

    def put_files(
        self,
        node_labels=None,
        pcmk_authkey=None,
        corosync_authkey=None,
        corosync_conf=None,
        pcs_disaster_recovery_conf=None,
        pcs_settings_conf=None,
        communication_list=None,
        name="http.files.put_files",
    ):
        # pylint: disable=too-many-arguments
        """
        Create a call for the files distribution to the nodes.

        node_labels list -- create success responses from these nodes
        pcmk_authkey bytes -- content of pacemaker authkey file
        corosync_authkey bytes -- content of corosync authkey file
        corosync_conf string -- content of corosync.conf
        pcs_disaster_recovery_conf string -- content of pcs DR config
        pcs_settings_conf string -- content of pcs_settings.conf
        communication_list list -- create custom responses
        name string -- the key of this call
        """
        input_data = {}
        output_data = {}
        written_output_dict = dict(
            code="written",
            message="",
        )

        if pcmk_authkey:
            file_id = "pacemaker_remote authkey"
            input_data[file_id] = dict(
                data=base64.b64encode(pcmk_authkey).decode("utf-8"),
                type="pcmk_remote_authkey",
                rewrite_existing=True,
            )
            output_data[file_id] = written_output_dict

        if corosync_authkey:
            file_id = "corosync authkey"
            input_data[file_id] = dict(
                data=base64.b64encode(corosync_authkey).decode("utf-8"),
                type="corosync_authkey",
                rewrite_existing=True,
            )
            output_data[file_id] = written_output_dict

        if corosync_conf:
            file_id = "corosync.conf"
            input_data[file_id] = dict(
                data=corosync_conf,
                type="corosync_conf",
            )
            output_data[file_id] = written_output_dict

        if pcs_disaster_recovery_conf:
            file_id = "disaster-recovery config"
            input_data[file_id] = dict(
                data=base64.b64encode(pcs_disaster_recovery_conf).decode(
                    "utf-8"
                ),
                type="pcs_disaster_recovery_conf",
                rewrite_existing=True,
            )
            output_data[file_id] = written_output_dict

        if pcs_settings_conf:
            file_id = "pcs_settings.conf"
            input_data[file_id] = dict(
                data=pcs_settings_conf,
                type="pcs_settings_conf",
                rewrite_existing=True,
            )
            output_data[file_id] = written_output_dict

        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/put_file",
            param_list=[("data_json", json.dumps(input_data))],
            output=json.dumps(dict(files=output_data)),
        )

    def remove_files(
        self,
        node_labels=None,
        pcsd_settings=False,
        pcs_disaster_recovery_conf=False,
        communication_list=None,
        name="http.files.remove_files",
    ):
        """
        Create a call for removing the files on the nodes.

        node_labels list -- create success responses from these nodes
        pcsd_settings bool -- if True, remove file pcsd_settings
        pcs_disaster_recovery_conf bool -- if True, remove pcs DR config
        communication_list list -- create custom responses
        name string -- the key of this call
        """
        input_data = {}
        output_data = {}

        if pcsd_settings:
            file_id = "pcsd settings"
            input_data[file_id] = dict(type="pcsd_settings")
            output_data[file_id] = dict(
                code="deleted",
                message="",
            )

        if pcs_disaster_recovery_conf:
            file_id = "pcs disaster-recovery config"
            input_data[file_id] = dict(type="pcs_disaster_recovery_conf")
            output_data[file_id] = dict(
                code="deleted",
                message="",
            )

        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/remove_file",
            param_list=[("data_json", json.dumps(input_data))],
            output=json.dumps(dict(files=output_data)),
        )
