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
        self, modifiers=None, resources=None, name="env.push_cib",
        load_key="load_cib", wait=False
    ):
        cib_xml = modify_cib(
            self.__calls.get(load_key).stdout,
            modifiers,
            resources,
        )
        self.__calls.place(name, PushCibCall(cib_xml, wait=False))
