import base64
from collections import namedtuple
from typing import (
    Any,
    Dict,
)

from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.lib.errors import LibraryError


def create_pcmk_remote_actions(action_list):
    return {
        f"pacemaker_remote {action}": service_cmd_format(
            "pacemaker_remote", action
        )
        for action in action_list
    }


def pcmk_authkey_format(authkey_content):
    """
    Return a dict usable in the communication with a remote/put_file
    authkey_content is raw authkey content
    """
    return {
        "data": base64.b64encode(authkey_content).decode("utf-8"),
        "type": "pcmk_remote_authkey",
        "rewrite_existing": True,
    }


def corosync_authkey_format(authkey_content):
    """
    Return a dict usable in the communication with a remote/put_file
    authkey_content is raw authkey content
    """
    return {
        "data": base64.b64encode(authkey_content).decode("utf-8"),
        "type": "corosync_authkey",
        "rewrite_existing": True,
    }


def pcmk_authkey_file(authkey_content):
    return {"pacemaker_remote authkey": pcmk_authkey_format(authkey_content)}


def corosync_authkey_file(authkey_content):
    return {"corosync authkey": corosync_authkey_format(authkey_content)}


def corosync_conf_format(corosync_conf_content):
    return {
        "type": "corosync_conf",
        "data": corosync_conf_content,
    }


def corosync_conf_file(corosync_conf_content):
    return {"corosync.conf": corosync_conf_format(corosync_conf_content)}


def pcs_dr_config_format(dr_conf_content: bytes) -> Dict[str, Any]:
    return {
        "type": "pcs_disaster_recovery_conf",
        "data": base64.b64encode(dr_conf_content).decode("utf-8"),
        "rewrite_existing": True,
    }


def pcs_dr_config_file(dr_conf_content: bytes) -> Dict[str, Any]:
    return {"disaster-recovery config": pcs_dr_config_format(dr_conf_content)}


def pcs_settings_conf_format(content):
    return {
        "data": content,
        "type": "pcs_settings_conf",
        "rewrite_existing": True,
    }


def pcs_settings_conf_file(content):
    return {"pcs_settings.conf": pcs_settings_conf_format(content)}


def service_cmd_format(service, command):
    """
    Return a dict usable in the communication with a remote/run_action
    string service is name of requested service (eg. pacemaker_remote)
    string command specifies an action on service (eg. start)
    """
    return {
        "type": "service_command",
        "service": service,
        "command": command,
    }


class Result(namedtuple("Result", "code message")):
    """Wrapper over some call results"""


def unpack_items_from_response(main_response, main_key, node_label):
    """
    Check format of main_response and return main_response[main_key].
    dict main_response has on the key 'main_key' dict with item name as key and
        dict with result as value. E.g.
        {
            "files": {
                "file1": {"code": "success", "message": ""}
            }
        }
    string main_key is name of key under that is a dict with results
    string node_label is a node label for reporting an invalid format
    """
    is_in_expected_format = (
        isinstance(main_response, dict)
        and main_key in main_response
        and isinstance(main_response[main_key], dict)
    )

    if not is_in_expected_format:
        raise LibraryError(
            ReportItem.error(reports.messages.InvalidResponseFormat(node_label))
        )

    return main_response[main_key]


def response_items_to_result(response_items, expected_keys, node_label):
    """
    Check format of response_items and return dict where keys are transformed to
    Result. E.g.
    {"file1": {"code": "success", "message": ""}}
    ->
    {"file1": Result("success", "")}}

    dict response_items has item name as key and dict with result as value.
    list expected_keys contains expected keys in a dict main_response[main_key]
    string node_label is a node label for reporting an invalid format
    """
    if set(expected_keys) != set(response_items.keys()):
        raise LibraryError(
            ReportItem.error(reports.messages.InvalidResponseFormat(node_label))
        )

    for result in response_items.values():
        if (
            not isinstance(result, dict)
            or "code" not in result
            or "message" not in result
        ):
            raise LibraryError(
                ReportItem.error(
                    reports.messages.InvalidResponseFormat(node_label)
                )
            )

    return {
        file_key: Result(raw_result["code"], raw_result["message"])
        for file_key, raw_result in response_items.items()
    }


def response_to_result(main_response, main_key, expected_keys, node_label):
    """
    Validate response (from remote/put_file or remote/run_action) and transform
    results from dict to Result.

    dict main_response has on the key 'main_key' dict with item name as key and
        dict with result as value. E.g.
        {
            "files": {
                "file1": {"code": "success", "message": ""}
            }
        }
    string main_key is name of key under that is a dict with results
    list expected_keys contains expected keys in a dict main_response[main_key]
    string node_label is a node label for reporting an invalid format
    """
    return response_items_to_result(
        unpack_items_from_response(main_response, main_key, node_label),
        expected_keys,
        node_label,
    )


def get_format_result(code_message_map):
    def format_result(result):
        if result.code in code_message_map:
            return code_message_map[result.code]

        return result.message

    return format_result
