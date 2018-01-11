from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.command_env.config_http_corosync import CorosyncShortcuts
from pcs.test.tools.command_env.mock_node_communicator import(
    AddRequestCall,
    create_communication,
    StartLoopCall,
)


class HttpConfig(object):
    def __init__(self, call_collection, wrap_helper):
        self.__calls = call_collection

        self.corosync = wrap_helper(CorosyncShortcuts(self.__calls))

    def add_communication(self, name, communication_list, **kwargs):
        """
        Create a generic call for network communication
        string name -- key of the call
        list of dict communication_list -- see
            pcs.test.tools.command_env.mock_node_communicator.create_communication
        **kwargs -- see
            pcs.test.tools.command_env.mock_node_communicator.create_communication
        """
        request_list, response_list = create_communication(
            communication_list, **kwargs
        )
        #TODO #when multiple add_request needed there should be:
        # * unique name for each add_request
        # * find start_loop by name and replace it with the new one that will
        #   have merged responses
        self.add_requests(request_list, name="{0}_requests".format(name))
        self.start_loop(response_list, name="{0}_responses".format(name))

    def add_requests(self, request_list, name, before=None, instead=None):
        self.__calls.place(
            name,
            AddRequestCall(request_list),
            before=before,
            instead=instead
        )

    def start_loop(self, response_list, name, before=None, instead=None):
        self.__calls.place(
            name,
            StartLoopCall(response_list),
            before=before,
            instead=instead
        )
