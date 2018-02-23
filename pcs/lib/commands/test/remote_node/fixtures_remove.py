from pcs.common import report_codes
from pcs.test.tools import fixture

OFFLINE_ERROR_MSG = "Could not resolve host"

class EnvConfigMixin(object):
    def __init__(self, call_collection, wrap_helper, config):
        self.__calls = call_collection
        self.config = config

    def destroy_pacemaker_remote(
        self, label=None, address_list=None, result=None, **kwargs
    ):
        if kwargs.get("was_connected", True):
            result = result if result is not None else {
                "code": "success",
                "message": "",
            }

            kwargs["results"] = {
                "pacemaker_remote stop": result,
                "pacemaker_remote disable": result
            }
        elif result is not None:
            raise AssertionError(
                "Keyword 'result' makes no sense with 'was_connected=False'"
            )

        if label or address_list:
            if kwargs.get("communication_list", None):
                raise AssertionError(
                    "Keywords 'label' and 'address_list' makes no sense with"
                    " 'communication_list != None'"
                )
            kwargs["communication_list"] = [
                dict(label=label, address_list=address_list)
            ]

        self.config.http.manage_services(
            action_map={
                "pacemaker_remote stop": {
                    "type": "service_command",
                    "service": "pacemaker_remote",
                    "command": "stop",
                },
                "pacemaker_remote disable": {
                    "type": "service_command",
                    "service": "pacemaker_remote",
                    "command": "disable",
                },
            },
            **kwargs
        )

    def remove_authkey(
        self, communication_list, result=None, **kwargs
    ):
        if kwargs.get("was_connected", True):
            result = result if result is not None else {
                "code": "deleted",
                "message": "",
            }

            kwargs["results"] = {
                "pacemaker_remote authkey": result
            }
        elif result is not None:
            raise AssertionError(
                "Keyword 'result' makes no sense with 'was_connected=False'"
            )
        self.config.http.remove_file(
            communication_list=communication_list,
            files={
                "pacemaker_remote authkey": {
                    "type": "pcmk_remote_authkey",
                }
            },
            **kwargs
        )

REPORTS = (fixture.ReportStore()
    .info(
        "pcmk_remote_disable_stop_started",
        report_codes.SERVICE_COMMANDS_ON_NODES_STARTED,
        #python 3 has dict_keys so list is not the right structure
        action_list={
            "pacemaker_remote disable": None,
            "pacemaker_remote stop": None,
        }.keys(),
        description="stop of service pacemaker_remote",
    )
    .info(
        "pcmk_remote_disable_success",
        report_codes.SERVICE_COMMAND_ON_NODE_SUCCESS,
        service_command_description="pacemaker_remote disable",
    )
    .info(
        "pcmk_remote_stop_success",
        report_codes.SERVICE_COMMAND_ON_NODE_SUCCESS,
        service_command_description="pacemaker_remote stop",
    )
    .info(
        "authkey_remove_started" ,
        report_codes.FILES_REMOVE_FROM_NODE_STARTED,
        #python 3 has dict_keys so list is not the right structure
        file_list={"pacemaker_remote authkey": None}.keys(),
        description="remote node files",
    )
    .info(
        "authkey_remove_success",
        report_codes.FILE_REMOVE_FROM_NODE_SUCCESS,
        file_description="pacemaker_remote authkey",
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
        "remove_file_connection_failed",
        command="remote/remove_file",
    )
    .as_warn(
        "remove_file_connection_failed",
        "remove_file_connection_failed_warn",
    )
    .error(
        "authkey_remove_failed",
        report_codes.FILE_REMOVE_FROM_NODE_ERROR,
        reason="Access denied",
        file_description="pacemaker_remote authkey",
        force_code=report_codes.SKIP_FILE_DISTRIBUTION_ERRORS,
    )
    .as_warn(
        "authkey_remove_failed",
        "authkey_remove_failed_warn",
    )
    .error(
        "pcmk_remote_disable_failed",
        report_codes.SERVICE_COMMAND_ON_NODE_ERROR,
        reason="Operation failed.",
        service_command_description="pacemaker_remote disable",
        force_code=report_codes.SKIP_ACTION_ON_NODES_ERRORS,
    )
    .as_warn(
        "pcmk_remote_disable_failed",
        "pcmk_remote_disable_failed_warn",
    )
    .copy(
        "pcmk_remote_disable_failed",
        "pcmk_remote_stop_failed",
        service_command_description="pacemaker_remote stop",
    )
    .as_warn(
        "pcmk_remote_stop_failed",
        "pcmk_remote_stop_failed_warn",
    )
)
