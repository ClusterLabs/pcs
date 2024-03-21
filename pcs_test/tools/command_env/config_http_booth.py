import base64
import json

from pcs_test.tools.command_env.mock_node_communicator import (
    place_multinode_call,
)


class BoothShortcuts:
    def __init__(self, calls):
        self.__calls = calls

    def send_config(
        self,
        booth_name,
        config,
        authfile=None,
        authfile_data=None,
        node_labels=None,
        communication_list=None,
        name="http.booth.send_config",
    ):
        data = {
            "config": {
                "name": "{}.conf".format(booth_name),
                "data": config,
            }
        }
        if authfile and authfile_data:
            data["authfile"] = {
                "name": authfile,
                "data": base64.b64encode(authfile_data).decode("utf-8"),
            }
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/booth_set_config",
            param_list=[("data_json", json.dumps(data))],
        )

    def get_config(
        self,
        booth_name,
        config_data=None,
        authfile=None,
        authfile_data=None,
        node_labels=None,
        communication_list=None,
        name="http.booth.get_config",
    ):
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/booth_get_config",
            param_list=[("name", booth_name)],
            output=json.dumps(
                {
                    "config": {
                        "data": config_data,
                    },
                    "authfile": {
                        "name": authfile,
                        "data": (
                            base64.b64encode(authfile_data).decode("utf-8")
                            if authfile_data
                            else None
                        ),
                    },
                }
            ),
        )

    def save_files(
        self,
        files_data,
        saved=(),
        existing=(),
        failed=(),
        rewrite_existing=False,
        node_labels=None,
        communication_list=None,
        name="http.booth.save_files",
    ):
        # pylint: disable=too-many-arguments
        param_list = [("data_json", json.dumps(files_data))]
        if rewrite_existing:
            param_list.append(("rewrite_existing", "1"))

        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/booth_save_files",
            param_list=param_list,
            output=json.dumps(
                {
                    "saved": saved,
                    "existing": existing,
                    "failed": failed,
                }
            ),
        )
