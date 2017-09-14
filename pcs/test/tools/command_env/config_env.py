from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.command_env.mock_push_cib import Call as PushCibCall
from pcs.test.tools.fixture import modify_cib


class EnvConfig(object):
    def __init__(self, call_collection):
        self.__calls = call_collection

    def push_cib(
        self, modifiers=None, name="env.push_cib",
        load_key="load_cib", wait=False, exception=None, instead=None,
        **modifier_shortcuts
    ):
        cib_xml = modify_cib(
            self.__calls.get(load_key).stdout,
            modifiers,
            **modifier_shortcuts
        )
        self.__calls.place(
            name,
            PushCibCall(cib_xml, wait=wait, exception=exception),
            instead=instead
        )

    def push_cib_custom(
        self, name="env.push_cib", custom_cib=None, wait=False, exception=None,
        instead=None
    ):
        self.__calls.place(
            name,
            PushCibCall(
                custom_cib, custom_cib=True, wait=wait, exception=exception
            ),
            instead=instead
        )
