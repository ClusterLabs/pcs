from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from collections import defaultdict, namedtuple
from pcs.lib import reports
from pcs.lib.errors import LibraryError
import base64

def create_pcmk_remote_actions(action_list):
    return dict([
        (
            "pacemaker_remote {0}".format(action),
            service_cmd_format(
                "pacemaker_remote",
                action
            )
        )
        for action in action_list
    ])

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

def pcmk_authkey_file(authkey_content):
    return {
        "pacemaker_remote authkey": pcmk_authkey_format(authkey_content)
    }

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
    """ Wrapper over some call results """

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
        and
        main_key in main_response
        and
        isinstance(main_response[main_key], dict)
    )

    if not is_in_expected_format:
        raise LibraryError(reports.invalid_response_format(node_label))

    return main_response[main_key]

def response_items_to_result(response_items, expected_keys, node_label):
    """
    Check format of response_items and return dict where keys are transformed to
    Result. E.g.
    {"file1": {"code": "success", "message": ""}}
    ->
    {"file1": Result("success", "")}}

    dict resposne_items has item name as key and dict with result as value.
    list expected_keys contains expected keys in a dict main_response[main_key]
    string node_label is a node label for reporting an invalid format
    """
    if set(expected_keys) != set(response_items.keys()):
        raise LibraryError(reports.invalid_response_format(node_label))

    for result in response_items.values():
        if(
            not isinstance(result, dict)
            or
            "code" not in result
            or
            "message" not in result
        ):
            raise LibraryError(reports.invalid_response_format(node_label))

    return dict([
        (
            file_key,
            Result(raw_result["code"], raw_result["message"])
        )
        for file_key, raw_result in response_items.items()
    ])


def response_to_result(
    main_response, main_key, expected_keys, node_label
):
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
        node_label
    )

def format_result(result):
    return "{code}{message}".format(
        code=result.code,
        message="" if not result.message else " ({0})".format(result.message)
    )

def responses_to_report_infos(
    node_responses_map, is_success, get_node_label=lambda name:name
):
    """
    Return tuple with information about success and errors deduced from
    node_responses_map.

    dict node_responses_map has node as key and on values is another dict.
        The nested dict has an action/file description as key and dict with a
        result as value. The result is Result.
        Example:
        {
            "node1": {
                "action1/file1 desc": Result("success", ""),
                "action2/file2 desc": Result("success", ""),
            },
            "node2": {
                "action1/file1 desc": Result("success", ""),
                "action2/file2 desc": Result("error", "something is wrong"),
            }
        }
    callable is_success takes "action/file description" and the result and
        returns bool: if the result means success
    callable get_node_label takes node (key from node_response_map) and returns
        string representation of node
    """
    success = defaultdict(list)
    errors = defaultdict(dict)
    for node, response_map in node_responses_map.items():
        for key, item_response in sorted(response_map.items()):
            if is_success(key, item_response):
                success[get_node_label(node)].append(key)
            else:
                errors[get_node_label(node)][key] = format_result(item_response)
    return success, errors
