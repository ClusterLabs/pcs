from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.common import pcs_pycurl as pycurl
from pcs.common.node_communicator import(
    RequestTarget,
    RequestData,
    Request,
    Response,
)
from pcs.test.tools.command_env.mock_node_communicator import(
    AddRequestCall,
    StartLoopCall,
)
from pcs.test.tools.custom_mock import MockCurlSimple


class HttpConfig(object):
    def __init__(self, call_collection):
        self.__calls = call_collection

    def __communication_to_response(
        self, label, address_list, action, param_list, port, token,
        response_code, output, debug_output, was_connected, errno,
        error_msg
    ):
        return Response(
            MockCurlSimple(
                info={pycurl.RESPONSE_CODE: response_code},
                output=output.encode("utf-8"),
                debug_output=debug_output.encode("utf-8"),
                request=Request(
                    RequestTarget(label, address_list, port, token),
                    RequestData(action, param_list),
                )
            ),
            was_connected=was_connected,
            errno=6,
            error_msg= error_msg,
        )

    def add_communication(
        self, name, communication_list,
        action="", param_list=None, port="2224", token=None,
        response_code=None, output="", debug_output="", was_connected=True,
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
            param_list=param_list if param_list else [],
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
                self.__communication_to_response(**full)
            )

        request_list = [response.request for response in response_list]

        #TODO #when multiple add_request needed there should be:
        # * unique name for each add_request
        # * find start_loop by name and replace it with the new one that will
        #   have merged responses
        self.add_requests(request_list, name="{0}_requests".format(name))
        self.start_loop(response_list, name="{0}_responses".format(name))


    def add_requests(self, request_list, name):
        self.__calls.place(name, AddRequestCall(request_list))

    def start_loop(self, response_list, name):
        self.__calls.place(name, StartLoopCall(response_list))
