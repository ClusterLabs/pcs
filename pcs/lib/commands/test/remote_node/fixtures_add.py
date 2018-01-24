from __future__ import (
    absolute_import,
    division,
    print_function,
)

import base64
import json

from pcs.common import report_codes
from pcs.test.tools import fixture
from pcs.test.tools.pcs_unittest import mock


OFFLINE_ERROR_MSG = "Could not resolve host"
FAIL_HTTP_KWARGS = dict(
    output="",
    was_connected=False,
    errno='6',
    error_msg_template=OFFLINE_ERROR_MSG,
)

class EnvConfigMixin(object):
    PCMK_AUTHKEY_PATH = "/etc/pacemaker/authkey"
    def __init__(self, call_collection, wrap_helper, config):
        self.__calls = call_collection
        self.config = config

    def distribute_authkey(
        self, communication_list, pcmk_authkey_content, result=None, **kwargs
    ):
        if kwargs.get("was_connected", True):
            result = result if result is not None else {
                "code": "written",
                "message": "",
            }

            kwargs["results"] = {
                "pacemaker_remote authkey": result
            }
        elif result is not None:
            raise AssertionError(
                "Keyword 'result' makes no sense with 'was_connected=False'"
            )
        self.config.http.put_file(
            communication_list=communication_list,
            files={
                "pacemaker_remote authkey": {
                    "type": "pcmk_remote_authkey",
                    "data": base64
                        .b64encode(pcmk_authkey_content)
                        .decode("utf-8")
                    ,
                    "rewrite_existing": True
                }
            },
            **kwargs
        )

    def check_node_availability(self, label, result=True, **kwargs):
        if "output" not in kwargs:
            kwargs["output"] = json.dumps({"node_available": result})

        self.config.http.place_multinode_call(
            "node_available",
            communication_list=[dict(label=label)],
            action="remote/node_available",
            **kwargs
        )

    def authkey_exists(self, return_value):
        self.config.fs.exists(self.PCMK_AUTHKEY_PATH, return_value=return_value)

    def open_authkey(self, pcmk_authkey_content="", fail=False):
        kwargs = {}
        if fail:
            kwargs["side_effect"] = EnvironmentError("open failed")
        else:
            kwargs["return_value"] = mock.mock_open(
                read_data=pcmk_authkey_content
            )()

        self.config.fs.open(
            self.PCMK_AUTHKEY_PATH,
            **kwargs
        )

    def push_existing_authkey_to_remote(
        self, remote_host, distribution_result=None
    ):
        pcmk_authkey_content = b"password"
        (self.config
            .local.authkey_exists(return_value=True)
            .local.open_authkey(pcmk_authkey_content)
            .local.distribute_authkey(
                communication_list=[dict(label=remote_host)],
                pcmk_authkey_content=pcmk_authkey_content,
                result=distribution_result
            )
         )

    def run_pacemaker_remote(self, label, result=None, **kwargs):
        if kwargs.get("was_connected", True):
            result = result if result is not None else {
                "code": "success",
                "message": "",
            }

            kwargs["results"] = {
                "pacemaker_remote enable": result,
                "pacemaker_remote start": result
            }
        elif result is not None:
            raise AssertionError(
                "Keyword 'result' makes no sense with 'was_connected=False'"
            )

        self.config.http.manage_services(
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
            **kwargs
        )

REPORTS = (fixture.ReportStore()
    .info(
        "authkey_distribution_started" ,
        report_codes.FILES_DISTRIBUTION_STARTED,
        #python 3 has dict_keys so list is not the right structure
        file_list={"pacemaker_remote authkey": None}.keys(),
        description="remote node configuration files",
    )
    .info(
        "authkey_distribution_success",
        report_codes.FILE_DISTRIBUTION_SUCCESS,
        file_description="pacemaker_remote authkey",
    )
    .info(
        "pcmk_remote_start_enable_started",
        report_codes.SERVICE_COMMANDS_ON_NODES_STARTED,
        #python 3 has dict_keys so list is not the right structure
        action_list={
            "pacemaker_remote start": None,
            "pacemaker_remote enable": None,
        }.keys(),
        description="start of service pacemaker_remote",
    )
    .info(
        "pcmk_remote_enable_success",
        report_codes.SERVICE_COMMAND_ON_NODE_SUCCESS,
        service_command_description="pacemaker_remote enable",
    )
    .info(
        "pcmk_remote_start_success",
        report_codes.SERVICE_COMMAND_ON_NODE_SUCCESS,
        service_command_description="pacemaker_remote start",
    )
)

EXTRA_REPORTS = (fixture.ReportStore()
    .error(
        "manage_services_connection_failed",
        report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
        command="remote/manage_services",
        reason=OFFLINE_ERROR_MSG,
        force_code=report_codes.SKIP_OFFLINE_NODES
    )
    .as_warn(
        "manage_services_connection_failed",
        "manage_services_connection_failed_warn",
    )
    .copy(
        "manage_services_connection_failed",
        "check_availability_connection_failed",
        command="remote/node_available",
    )
    .as_warn(
        "check_availability_connection_failed",
        "check_availability_connection_failed_warn",
    )
    .copy(
        "manage_services_connection_failed",
        "put_file_connection_failed",
        command="remote/put_file",
    )
    .as_warn(
        "put_file_connection_failed",
        "put_file_connection_failed_warn",
    )
    .error(
        "pcmk_remote_enable_failed",
        report_codes.SERVICE_COMMAND_ON_NODE_ERROR,
        reason="Operation failed.",
        service_command_description="pacemaker_remote enable",
        force_code=report_codes.SKIP_ACTION_ON_NODES_ERRORS,
    )
    .as_warn("pcmk_remote_enable_failed", "pcmk_remote_enable_failed_warn")
    .copy(
        "pcmk_remote_enable_failed",
        "pcmk_remote_start_failed",
        service_command_description="pacemaker_remote start",
    )
    .as_warn("pcmk_remote_start_failed", "pcmk_remote_start_failed_warn")
    .error(
        "authkey_distribution_failed",
        report_codes.FILE_DISTRIBUTION_ERROR,
        reason="File already exists",
        file_description="pacemaker_remote authkey",
        force_code=report_codes.SKIP_FILE_DISTRIBUTION_ERRORS
    )
    .as_warn("authkey_distribution_failed", "authkey_distribution_failed_warn")
)
