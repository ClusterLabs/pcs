import json
from urllib.parse import parse_qs

from pcs import settings
from pcs.common import pcs_pycurl as pycurl
from pcs.common.host import Destination
from pcs.common.node_communicator import (
    Request,
    RequestData,
    RequestTarget,
    Response,
)

from pcs_test.tools.custom_mock import MockCurlSimple

CALL_TYPE_HTTP_ADD_REQUESTS = "CALL_TYPE_HTTP_ADD_REQUESTS"
CALL_TYPE_HTTP_START_LOOP = "CALL_TYPE_HTTP_START_LOOP"


def log_request(request):
    label_data = [
        ("action", request.action),
        ("label", request.target.label),
        ("data", parse_qs(request.data)),
    ]

    if request.target.dest_list != [
        Destination(request.target.label, settings.pcsd_default_port)
    ]:
        label_data.append(("dest_list", request.target.dest_list))

    return "  ".join(
        ["{0}:'{1}'".format(key, value) for key, value in label_data]
    )


def log_response(response, indent=0):
    label_data = [
        ("action", response.request.action),
        ("label", response.request.target.label),
    ]

    if response.request.target.dest_list != [
        Destination(response.request.target.label, settings.pcsd_default_port),
    ]:
        label_data.append(("dest_list", response.request.target.dest_list))

    label_data.append(("was_connected", response.was_connected))

    if response.was_connected:
        label_data.append(("response_code", response.response_code))
    else:
        label_data.extend(
            [
                ("errno", response.errno),
                ("error_msg", response.error_msg),
            ]
        )

    label_data.append(("data", parse_qs(response.request.data)))

    return "{0}{1}".format(
        "  " * indent,
        "  ".join(
            ["{0}:'{1}'".format(key, value) for key, value in label_data]
        ),
    )


def different_request_lists(expected_request_list, request_list):
    return AssertionError(
        (
            "Method add_request of NodeCommunicator expected"
            " request_list:\n  * {0}\nbut got: \n  * {1}"
        ).format(
            "\n  * ".join(log_request(r) for r in expected_request_list),
            "\n  * ".join(log_request(r) for r in request_list),
        )
    )


def bad_request_list_content(errors):
    return AssertionError(
        (
            "NodeCommunicator.add_request got different requests than "
            "expected:{0}"
        ).format(
            "".join(
                [
                    "\n  call index {call_index}:{call_details}".format(
                        call_index=call_index,
                        call_details="".join(
                            [
                                "\n    mismatch in {option_name}:"
                                "\n      expected: {expected_value}"
                                "\n      real:     {real_value}".format(
                                    option_name=option_name,
                                    expected_value=pair[0],
                                    real_value=pair[1],
                                )
                                for option_name, pair in value.items()
                            ]
                        ),
                    )
                    for call_index, value in errors.items()
                ]
            )
        )
    )


def _communication_to_response(  # noqa: PLR0913
    label,
    dest_list,
    action,
    param_list,
    response_code,
    output,
    debug_output,
    was_connected,
    errno,
    error_msg,
    raw_data,
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    return Response(
        MockCurlSimple(
            info={pycurl.RESPONSE_CODE: response_code},
            output=output,
            debug_output=debug_output,
            request=Request(
                # We do not need to check if token is the right one in tests:
                # 1) Library commands tests do not care about tokens. That
                #    should be covered once in a specialized test, not in every
                #    single library command test.
                # 2) If we need to test the case when a token is not accepted
                #    by pcsd, we will do so by setting an appropriate response.
                #    The actual token value doesn't matter.
                RequestTarget(label, dest_list=dest_list, token=None),
                RequestData(action, param_list, raw_data),
            ),
        ),
        was_connected=was_connected,
        errno=errno,
        error_msg=error_msg,
    )


def create_communication(  # noqa: PLR0913
    communication_list,
    *,
    action="",
    param_list=None,
    response_code=200,
    output="",
    debug_output="",
    was_connected=True,
    errno=0,
    error_msg=None,
    raw_data=None,
):
    """
    list of dict communication_list -- each dict describes one request-response
        it accepts keys:
            string label -- required, the label of a node to talk with
            dest_list -- list of pcs.common.host.Destination where to send
                a request, defaults to [(label, default_pcsd_port)]
            string action -- pcsd url, see RequestData
            list of pairs param_list -- see RequestData
            int response_code -- http response code
            string output -- http response output
            string debug_output -- pycurl debug output
            bool was_connected -- see Response
            int errno -- see Response
            string error_msg -- see Response
            string raw_data -- see data attrib in RequestData
        if some key is not present, it is put here from common values - rest
        args of this function(except name, communication_list,
        error_msg_template)
    string action -- pcsd url, see RequestData
    list of pairs (tuple) param_list -- see RequestData
    string response_code -- http response code
    string output -- http response output
    string debug_output -- pycurl debug output
    bool was_connected -- see Response
    int errno -- see Response
    string error_msg -- see Response
    string raw_data -- see data attrib in RequestData
    """
    # pylint: disable=too-many-arguments
    # We don't care about tokens, see _communication_to_response.
    common = dict(
        action=action,
        param_list=param_list if param_list else (),
        response_code=response_code,
        output=output,
        debug_output=debug_output,
        was_connected=was_connected,
        errno=errno,
        error_msg=error_msg,
        raw_data=raw_data,
    )

    response_list = []
    for communication in communication_list:
        if "dest_list" not in communication:
            communication["dest_list"] = [
                Destination(communication["label"], settings.pcsd_default_port)
            ]
        full = common.copy()
        full.update(communication)
        response_list.append(_communication_to_response(**full))

    request_list = [response.request for response in response_list]
    return request_list, response_list


def place_multinode_call(
    calls,
    name,
    node_labels=None,
    communication_list=None,
    before=None,
    **kwargs,
):
    """
    Shortcut for adding a call sending the same request to one or more nodes

    CallListBuilder calls -- list of expected calls
    string name -- the key of this call
    list node_labels -- create success responses from these nodes
    list communication_list -- use these custom responses
    **kwargs -- see __module__.create_communication
    """
    if (node_labels is None and communication_list is None) or (
        node_labels and communication_list
    ):
        raise AssertionError(
            "Exactly one of 'node_labels', 'communication_list' "
            "must be specified"
        )
    communication_list = (
        communication_list
        if communication_list is not None
        else [{"label": label} for label in node_labels]
    )
    place_communication(
        calls, name, communication_list, before=before, **kwargs
    )


def place_requests(calls, name, request_list, before=None):
    calls.place(name, AddRequestCall(request_list), before=before)


def place_responses(calls, name, response_list, before=None):
    calls.place(name, StartLoopCall(response_list), before=before)


def place_communication(calls, name, communication_list, before=None, **kwargs):
    if not communication_list:
        # If code runs a communication command with no targets specified, the
        # whole communicator and CURL machinery gets started. It doesn't
        # actually send any HTTP requests but it adds an empty list of requests
        # to CURL and starts the CURL loop. And the mock must do the same.
        place_requests(calls, f"{name}_requests", [], before=before)
        place_responses(calls, f"{name}_responses", [], before=before)
        return

    if isinstance(communication_list[0], dict):
        communication_list = [communication_list]

    request_list = []
    response_list = []
    for com_list in communication_list:
        req_list, res_list = create_communication(com_list, **kwargs)
        request_list.append(req_list)
        response_list.extend(res_list)

    place_requests(calls, f"{name}_requests", request_list[0], before=before)
    place_responses(calls, f"{name}_responses", response_list, before=before)
    for i, req_list in enumerate(request_list[1:], start=1):
        place_requests(calls, f"{name}_requests_{i}", req_list, before=before)


class AddRequestCall:
    type = CALL_TYPE_HTTP_ADD_REQUESTS

    def __init__(self, request_list):
        self.request_list = request_list

    def format(self):
        return "Requests:\n    * {0}".format(
            "\n    * ".join(
                [log_request(request) for request in self.request_list]
            )
        )

    def __repr__(self):
        return str("<HttpAddRequest '{0}'>").format(self.request_list)


class StartLoopCall:
    type = CALL_TYPE_HTTP_START_LOOP

    def format(self):
        return "Responses:\n    * {0}".format(
            "\n    * ".join(
                [log_response(response) for response in self.response_list]
            )
        )

    def __init__(self, response_list):
        self.response_list = response_list

    def __repr__(self):
        return str("<HttpStartLoop '{0}'>").format(self.response_list)


def _compare_request_data(expected, real):
    if expected == real:
        return True

    # If data is in json format, it is not possible to compare it as string,
    # because python 3 does not keep key order of dict. So if a response is
    # built by json.dumps(some_dict), the result string can vary.

    # Let's try known use: [('data_json', 'some_json_here')]
    # It means only one pair "data_json" + json string: everything else is False

    if len(expected) != 1:
        return False

    if len(real) != 1:
        return False

    if expected[0][0] != real[0][0] or expected[0][0] != "data_json":
        return False

    try:
        expected_data = json.loads(expected[0][1])
        real_data = json.loads(real[0][1])
        return expected_data == real_data
    except ValueError:
        return False


class NodeCommunicator:
    def __init__(self, call_queue=None):
        self.__call_queue = call_queue

    def add_requests(self, request_list):
        _, add_request_call = self.__call_queue.take(
            CALL_TYPE_HTTP_ADD_REQUESTS,
            request_list,
        )

        expected_request_list = add_request_call.request_list

        if len(expected_request_list) != len(request_list):
            raise different_request_lists(expected_request_list, request_list)

        errors = {}
        for i, real_request in enumerate(request_list):
            # We don't care about tokens, see _communication_to_response.
            expected_request = add_request_call.request_list[i]

            diff = {}
            if expected_request.action != real_request.action:
                diff["action"] = (expected_request.action, real_request.action)

            if expected_request.target.label != real_request.target.label:
                diff["target.label"] = (
                    expected_request.target.label,
                    real_request.target.label,
                )

            if (
                expected_request.target.dest_list
                != real_request.target.dest_list
            ):
                diff["target.dest_list"] = (
                    expected_request.target.dest_list,
                    real_request.target.dest_list,
                )

            # pylint: disable=protected-access
            if not _compare_request_data(
                expected_request._data.structured_data,
                real_request._data.structured_data,
            ):
                diff["data"] = (
                    expected_request._data.structured_data,
                    real_request._data.structured_data,
                )

            if diff:
                errors[i] = diff

        if errors:
            raise self.__call_queue.error_with_context(
                bad_request_list_content(errors)
            )

    def start_loop(self):
        _, call = self.__call_queue.take(CALL_TYPE_HTTP_START_LOOP)
        return call.response_list
