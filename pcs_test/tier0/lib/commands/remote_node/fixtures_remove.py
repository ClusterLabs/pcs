from pcs.common.reports import codes as report_codes

from pcs_test.tools import fixture

OFFLINE_ERROR_MSG = "Could not resolve host"


class EnvConfigMixin:
    def __init__(self, call_collection, wrap_helper, config):
        del wrap_helper, call_collection
        self.config = config

    def destroy_pacemaker_remote(
        self, label=None, dest_list=None, result=None, **kwargs
    ):
        if kwargs.get("was_connected", True):
            result = (
                result
                if result is not None
                else {
                    "code": "success",
                    "message": "",
                }
            )

            kwargs["results"] = {
                "pacemaker_remote stop": result,
                "pacemaker_remote disable": result,
            }
        elif result is not None:
            raise AssertionError(
                "Keyword 'result' makes no sense with 'was_connected=False'"
            )

        if label or dest_list:
            if kwargs.get("communication_list"):
                raise AssertionError(
                    "Keywords 'label' and 'dest_list' makes no sense with"
                    " 'communication_list != None'"
                )
            kwargs["communication_list"] = [
                dict(label=label, dest_list=dest_list)
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
            **kwargs,
        )

    def remove_authkey(self, communication_list, result=None, **kwargs):
        if kwargs.get("was_connected", True):
            result = (
                result
                if result is not None
                else {
                    "code": "deleted",
                    "message": "",
                }
            )

            kwargs["results"] = {"pacemaker_remote authkey": result}
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
            **kwargs,
        )


def base_reports_for_host(host):
    return (
        fixture.ReportSequenceBuilder()
        .info(
            report_codes.SERVICE_COMMANDS_ON_NODES_STARTED,
            action_list=[
                "pacemaker_remote stop",
                "pacemaker_remote disable",
            ],
            node_list=[host],
            _name="pcmk_remote_disable_stop_started",
        )
        .info(
            report_codes.SERVICE_COMMAND_ON_NODE_SUCCESS,
            service_command_description="pacemaker_remote disable",
            node=host,
            _name="pcmk_remote_disable_success",
        )
        .info(
            report_codes.SERVICE_COMMAND_ON_NODE_SUCCESS,
            service_command_description="pacemaker_remote stop",
            node=host,
            _name="pcmk_remote_stop_success",
        )
        .info(
            report_codes.FILES_REMOVE_FROM_NODES_STARTED,
            file_list=["pacemaker authkey"],
            node_list=[host],
            _name="authkey_remove_started",
        )
        .info(
            report_codes.FILE_REMOVE_FROM_NODE_SUCCESS,
            file_description="pacemaker authkey",
            node=host,
            _name="authkey_remove_success",
        )
        .fixtures
    )


def report_remove_file_connection_failed(node):
    return fixture.error(
        report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
        force_code=report_codes.SKIP_OFFLINE_NODES,
        command="remote/remove_file",
        reason=OFFLINE_ERROR_MSG,
        node=node,
    )


def report_authkey_remove_failed(node):
    return fixture.error(
        report_codes.FILE_REMOVE_FROM_NODE_ERROR,
        force_code=report_codes.FORCE,
        reason="Access denied",
        file_description="pacemaker authkey",
        node=node,
    )


def report_pcmk_remote_disable_failed(node):
    return fixture.error(
        report_codes.SERVICE_COMMAND_ON_NODE_ERROR,
        force_code=report_codes.FORCE,
        reason="Operation failed.",
        service_command_description="pacemaker_remote disable",
        node=node,
    )


def report_pcmk_remote_stop_failed(node):
    return fixture.error(
        report_codes.SERVICE_COMMAND_ON_NODE_ERROR,
        force_code=report_codes.FORCE,
        reason="Operation failed.",
        service_command_description="pacemaker_remote stop",
        node=node,
    )
