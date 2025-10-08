import json
import pprint

from pcs_test.tools.command_env.config_http_booth import BoothShortcuts
from pcs_test.tools.command_env.config_http_corosync import CorosyncShortcuts
from pcs_test.tools.command_env.config_http_files import FilesShortcuts
from pcs_test.tools.command_env.config_http_host import HostShortcuts
from pcs_test.tools.command_env.config_http_pcmk import PcmkShortcuts
from pcs_test.tools.command_env.config_http_pcs_cfgsync import (
    PcsCfgsyncShortcuts,
)
from pcs_test.tools.command_env.config_http_sbd import SbdShortcuts
from pcs_test.tools.command_env.config_http_scsi import ScsiShortcuts
from pcs_test.tools.command_env.config_http_status import StatusShortcuts
from pcs_test.tools.command_env.mock_node_communicator import (
    place_communication,
    place_multinode_call,
    place_requests,
    place_responses,
)


def _mutual_exclusive(param_names, **kwargs):
    entered = {
        key: value
        for key, value in kwargs.items()
        if key in param_names and value is not None
    }
    if len(entered) != 1:
        raise AssertionError(
            "Exactly one of '{0}' must be specified, \nwas specified:\n{1}".format(
                "', '".join(param_names),
                pprint.pformat(entered) if entered else "  nothing",
            )
        )


class HttpConfig:
    # pylint: disable=too-many-instance-attributes
    def __init__(self, call_collection, wrap_helper):
        self.__calls = call_collection

        self.booth = wrap_helper(BoothShortcuts(self.__calls))
        self.corosync = wrap_helper(CorosyncShortcuts(self.__calls))
        self.files = wrap_helper(FilesShortcuts(self.__calls))
        self.host = wrap_helper(HostShortcuts(self.__calls))
        self.pcmk = wrap_helper(PcmkShortcuts(self.__calls))
        self.pcs_cfgsync = wrap_helper(PcsCfgsyncShortcuts(self.__calls))
        self.sbd = wrap_helper(SbdShortcuts(self.__calls))
        self.scsi = wrap_helper(ScsiShortcuts(self.__calls))
        self.status = wrap_helper(StatusShortcuts(self.__calls))

    def add_communication(self, name, communication_list, **kwargs):
        """
        Create a generic call for network communication.
        string name -- key of the call
        list of dict communication_list -- see
            pcs_test.tools.command_env.mock_node_communicator.create_communication
        **kwargs -- see
            pcs_test.tools.command_env.mock_node_communicator.create_communication
        """
        place_communication(self.__calls, name, communication_list, **kwargs)

    def add_requests(self, request_list, name):
        place_requests(self.__calls, name, request_list)

    def start_loop(self, response_list, name):
        place_responses(self.__calls, name, response_list)

    def put_file(
        self,
        communication_list,
        name="http.common.put_file",
        results=None,
        files=None,
        **kwargs,
    ):
        """
        Example:
        config.http.put_file(
            communication_list=[dict(label="node")],
            files={
                "pacemaker_remote authkey": {
                    "type": "pcmk_remote_authkey",
                    "data": base64.b64encode(pcmk_authkey_content),
                    "rewrite_existing": True
                }
            },
            results={
                "pacemaker_remote authkey": {
                    "code": "written",
                    "message": "",
                }
            }
        )
        """

        _mutual_exclusive(["output", "results"], results=results, **kwargs)
        _mutual_exclusive(["files", "param_list"], files=files, **kwargs)

        if results:
            kwargs["output"] = json.dumps({"files": results})

        if files:
            kwargs["param_list"] = [("data_json", json.dumps(files))]

        self.place_multinode_call(
            name,
            communication_list=communication_list,
            action="remote/put_file",
            **kwargs,
        )

    def remove_file(
        self,
        communication_list,
        name="http.common.remove_file",
        results=None,
        files=None,
        **kwargs,
    ):
        """
        Example:
        config.http.remove_file(
            communication_list=[dict(label="node")],
            files={
                "pacemaker_remote authkey": {
                    "type": "pcmk_remote_authkey",
                }
            },
            results={
                "pacemaker_remote authkey": {
                    "code": "deleted",
                    "message": "",
                }
            }
        )
        """

        _mutual_exclusive(["output", "results"], results=results, **kwargs)
        _mutual_exclusive(["files", "param_list"], files=files, **kwargs)

        if results:
            kwargs["output"] = json.dumps({"files": results})

        if files:
            kwargs["param_list"] = [("data_json", json.dumps(files))]

        self.place_multinode_call(
            name,
            communication_list=communication_list,
            action="remote/remove_file",
            **kwargs,
        )

    def manage_services(
        self,
        communication_list,
        name="http.common.manage_services",
        results=None,
        action_map=None,
        **kwargs,
    ):
        """
        Example:
        config.http.manage_services(
            communication_list=[dict(label=label)],
            action_map={
                "pacemaker_remote enable": {
                    "type": "service_command",
                    "service": "pacemaker_remote",
                    "command": "enable",
                },
                "pacemaker_remote start": {
                    "type": "service_command",
                    "service": "pacemaker_remote",
                    "command": "start",
                },
            },
            results={
                "pacemaker_remote enable": {
                    "code": "success",
                    "message": "",
                },
                "pacemaker_remote start": {
                    "code": "success",
                    "message": "",
                }
            }
        )
        """
        _mutual_exclusive(["output", "results"], results=results, **kwargs)
        _mutual_exclusive(
            ["action_map", "param_list"], action_map=action_map, **kwargs
        )

        if results:
            kwargs["output"] = json.dumps({"actions": results})

        if action_map:
            kwargs["param_list"] = [("data_json", json.dumps(action_map))]

        self.place_multinode_call(
            name,
            communication_list=communication_list,
            action="remote/manage_services",
            **kwargs,
        )

    def place_multinode_call(self, *args, **kwargs):
        place_multinode_call(self.__calls, *args, **kwargs)
