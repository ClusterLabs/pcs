import json
from urllib.parse import parse_qs

from pcs.common import pcs_pycurl as pycurl
from pcs.common.node_communicator import(
    RequestTarget,
    RequestData,
    Request,
    Response,
)
from pcs.test.tools.custom_mock import MockCurlSimple

CALL_TYPE_HTTP_ADD_REQUESTS = "CALL_TYPE_HTTP_ADD_REQUESTS"
CALL_TYPE_HTTP_START_LOOP = "CALL_TYPE_HTTP_START_LOOP"

def log_request(request):
    label_data = [
            ("action", request.action),
            ("label", request.target.label),
            ("data", parse_qs(request.data)),
        ]

    if request.target.address_list != [request.target.label]:
        label_data.append(("address_list", request.target.address_list))

    if request.target.port != "2224":
        label_data.append(("port", request.target.port))


    return "  ".join([
        "{0}:'{1}'".format(key, value) for key, value in label_data
    ])

def log_response(response, indent=0):
    label_data = [
        ("action", response.request.action),
        ("label", response.request.target.label),
    ]

    if response.request.target.address_list != [response.request.target.label]:
        label_data.append(("address_list", response.request.target.address_list))

    label_data.append(("was_connected", response.was_connected))

    if response.request.target.port != "2224":
        label_data.append(("port", response.request.target.port))

    if response.was_connected:
        label_data.append(("respose_code", response.response_code))
    else:
        label_data.extend([
            ("errno", response.errno),
            ("error_msg", response.error_msg),
        ])

    label_data.append(("data", parse_qs(response.request.data)))

    return "{0}{1}".format(
        "  "*indent,
        "  ".join([
            "{0}:'{1}'".format(key, value) for key, value in label_data
        ]),
    )

def different_request_lists(expected_request_list, request_list):
    return AssertionError(
        (
            "Method add_request of NodeCommunicator expected"
            " request_list:\n  * {0}\nbut got: \n  * {1}"
        )
        .format(
            "\n  * ".join(log_request(r) for r in expected_request_list),
            "\n  * ".join(log_request(r) for r in request_list),
        )
    )

def bad_request_list_content(errors):
    return AssertionError(
        "Method add_request of NodeCommunicator get different requests"
        " than expected (key: (expected, real)): \n  {0}".format(
            "\n  ".join([
                "{0}:\n    {1}".format(
                    index,
                    "\n    ".join([
                        "{0}:\n      {1}\n      {2}"
                        .format(key, pair[0], pair[1])
                        for key, pair in value.items()
                    ])
                )
                for index, value in errors.items()
            ]),
        )
    )

def _communication_to_response(
    label, address_list, action, param_list, port, token, response_code,
    output, debug_output, was_connected, errno, error_msg
):
    return Response(
        MockCurlSimple(
            info={pycurl.RESPONSE_CODE: response_code},
            output=output,
            debug_output=debug_output,
            request=Request(
                RequestTarget(label, address_list, port, token),
                RequestData(action, param_list),
            )
        ),
        was_connected=was_connected,
        errno=errno,
        error_msg=error_msg,
    )

def create_communication(
    communication_list, action="", param_list=None, port=None, token=None,
    response_code=200, output="", debug_output="", was_connected=True,
    errno=0, error_msg_template=None
):
    """
    list of dict communication_list -- is setting for one request - response
        it accepts keys:
            label -- required, see RequestTarget
            action -- pcsd url, see RequestData
            param_list -- list of pairs, see RequestData
            port -- see RequestTarget
            token=None -- see RequestTarget
            response_code -- http response code
            output -- http response output
            debug_output -- pycurl debug output
            was_connected -- see Response
            errno -- see Response
            error_msg -- see Response
        if some key is not present, it is put here from common values - rest
        args of this fuction(except name, communication_list,
        error_msg_template)
    string error_msg_template -- template, the keys for format function will
        be taken from appropriate item of communication_list
    string action -- pcsd url, see RequestData
    list of pairs (tuple) param_list -- see RequestData
    string port -- see RequestTarget
    string token=None -- see RequestTarget
    string response_code -- http response code
    string output -- http response output
    string debug_output -- pycurl debug output
    bool was_connected -- see Response
    int errno -- see Response
    string error_msg -- see Response
    """
    response_list = []

    common = dict(
        action=action,
        param_list=param_list if param_list else (),
        port=port,
        token=token,
        response_code=response_code,
        output=output,
        debug_output=debug_output,
        was_connected=was_connected,
        errno=errno,
    )
    for communication in communication_list:
        if "address_list" not in communication:
            communication["address_list"] = [communication["label"]]

        full = common.copy()
        full.update(communication)

        if "error_msg" not in full:
            full["error_msg"] = (
                "" if not error_msg_template
                else error_msg_template.format(**full)
            )
        response_list.append(
            _communication_to_response(**full)
        )

    request_list = [response.request for response in response_list]

    return request_list, response_list

def place_multinode_call(
    calls, name, node_labels=None, communication_list=None, **kwargs
):
    """
    Shortcut for adding a call sending the same request to one or more nodes

    CallListBuilder calls -- list of expected calls
    string name -- the key of this call
    list node_labels -- create success responses from these nodes
    list communication_list -- use these custom responses
    **kwargs -- see __module__.create_communication
    """
    if (
        (not node_labels and not communication_list)
        or
        (node_labels and communication_list)
    ):
        raise AssertionError(
            "Exactly one of 'node_labels', 'communication_list' "
            "must be specified"
        )
    communication_list = communication_list or [
        {"label": label} for label in node_labels
    ]
    place_communication(calls, name, communication_list, **kwargs)


def place_requests(calls, name, request_list):
    calls.place(name, AddRequestCall(request_list))


def place_responses(calls, name, response_list):
    calls.place(name, StartLoopCall(response_list))


def place_communication(calls, name, communication_list, **kwargs):
    if isinstance(communication_list[0], dict):
        communication_list = [communication_list]

    request_list = []
    response_list = []
    for com_list in communication_list:
        req_list, res_list = create_communication(com_list, **kwargs)
        request_list.append(req_list)
        response_list.extend(res_list)

    place_requests(calls, "{0}_requests".format(name), request_list[0])
    place_responses(calls, "{0}_responses".format(name), response_list)
    for i, req_list in enumerate(request_list[1:], start=1):
        place_requests(calls, "{0}_requests_{1}".format(name, i), req_list)


class AddRequestCall(object):
    type = CALL_TYPE_HTTP_ADD_REQUESTS

    def __init__(self, request_list):
        self.request_list = request_list

    def format(self):
        return "Requests:\n    * {0}".format(
            "\n    * ".join([
                log_request(request) for request in self.request_list
            ])
        )

    def __repr__(self):
        return str("<HttpAddRequest '{0}'>").format(self.request_list)

class StartLoopCall(object):
    type = CALL_TYPE_HTTP_START_LOOP

    def format(self):
        return "Responses:\n    * {0}".format(
            "\n    * ".join([
                log_response(response) for response in self.response_list
            ])
        )

    def __init__(self, response_list):
        self.response_list = response_list

    def __repr__(self):
        return str("<HttpStartLoop '{0}'>").format(self.response_list)

def _compare_request_data(expected, real):
    if expected == real:
        return True

    # If data is in json format it is not possible to compare it as string.
    # Because python 3 does not keep key order of dict. So if is response
    # builded by json.dumps(some_dict) the result string can vary.

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


class NodeCommunicator(object):
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
            expected_request = add_request_call.request_list[i]

            diff = {}
            if expected_request.action != real_request.action:
                diff["action"] = (
                    expected_request.action,
                    real_request.action
                )

            if expected_request.target.label != real_request.target.label:
                diff["target.label"] = (
                    expected_request.target.label,
                    real_request.target.label
                )

            if expected_request.target.token != real_request.target.token:
                diff["target.token"] = (
                    expected_request.target.token,
                    real_request.target.token
                )

            if expected_request.target.port != real_request.target.port:
                diff["target.port"] = (
                    expected_request.target.port,
                    real_request.target.port
                )

            if not _compare_request_data(
                expected_request._data.structured_data,
                real_request._data.structured_data
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
