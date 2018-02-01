from __future__ import (
    absolute_import,
    division,
    print_function,
)

import json
import base64

from pcs.test.tools.command_env.mock_node_communicator import (
    place_multinode_call
)

class BoothShortcuts(object):
    def __init__(self, calls):
        self.__calls = calls

    def send_config(
        self, booth_name, config,
        authfile=None,
        authfile_data=None,
        node_labels=None,
        communication_list=None,
        name="http.booth.send_config"
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
            param_list=[("data_json", json.dumps(data))]
        )

    def get_config(
        self, booth_name,
        config_data=None,
        authfile=None,
        authfile_data=None,
        node_labels=None,
        communication_list=None,
        name="http.booth.get_config"
    ):
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/booth_get_config",
            param_list=[("name", booth_name)],
            output=json.dumps({
                "config": {
                    "data": config_data,
                },
                "authfile": {
                    "name": authfile,
                "data":
                    base64.b64encode(authfile_data).decode("utf-8")
                    if authfile_data else None,
                },
            }),
        )
