from __future__ import (
    absolute_import,
    division,
    print_function,
)

CALL_TYPE_HTTP_ADD_REQUESTS = "CALL_TYPE_HTTP_ADD_REQUESTS"
CALL_TYPE_HTTP_START_LOOP = "CALL_TYPE_HTTP_START_LOOP"

class AddRequestCall(object):
    type = CALL_TYPE_HTTP_ADD_REQUESTS

    def __init__(self, request_list):
        self.request_list = request_list

    def __repr__(self):
        return str("<HttpAddRequest '{0}'>").format(self.request_list)

class StartLoopCall(object):
    type = CALL_TYPE_HTTP_START_LOOP

    def __init__(self, response_list):
        self.response_list = response_list

    def __repr__(self):
        return str("<HttpAddRequest '{0}'>").format(self.response_list)

class NodeCommunicator(object):
    def __init__(self, call_queue=None):
        self.__call_queue = call_queue

    def add_requests(self, request_list):
        #TODO compare requests!
        _, dummy_call = self.__call_queue.take(CALL_TYPE_HTTP_ADD_REQUESTS)

    def start_loop(self):
        _, call = self.__call_queue.take(CALL_TYPE_HTTP_START_LOOP)
        return call.response_list
