from pcs.test.tools.command_env.mock_node_communicator import (
    place_multinode_call
)

class SbdShortcuts(object):
    def __init__(self, calls):
        self.__calls = calls

    def enable_sbd(
        self, node_labels=None, communication_list=None,
        name="http.sbd.enable_sbd"
    ):
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/sbd_enable"
        )

    def disable_sbd(
        self, node_labels=None, communication_list=None,
        name="http.sbd.disable_sbd"
    ):
        """
        Create a call for disabling sbd on nodes

        node_labels list -- create success responses from these nodes
        communication_list list -- create custom responses
        name string -- the key of this call
        """
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/sbd_disable"
        )

    def check_sbd(
        self, watchdog=None, device_list=(), node_labels=None,
        communication_list=None, name="http.sbd.check_sbd"
    ):
        place_multinode_call(
            self.__calls,
            name,
            node_labels,
            communication_list,
            action="remote/check_sbd",
        )

    def set_sbd_config(
        self, config_generator=None, node_labels=None, communication_list=None,
        name="http.sbd.set_sbd_config"
    ):
        if bool(config_generator) == bool(communication_list):
            raise AssertionError(
                "Exactly one of 'config_generator', 'communication_list' "
                "must be specified"
            )
        if config_generator and not node_labels:
            raise AssertionError(
                "'node_labels' has to be defined if 'config_generator' is used"
            )
        if communication_list is None:
            communication_list = [
                dict(
                    param_list=[("config", config_generator(node))],
                    label=node,
                ) for node in node_labels
            ]
        place_multinode_call(
            self.__calls,
            name,
            None,
            communication_list,
            action="remote/set_sbd_config",
        )
