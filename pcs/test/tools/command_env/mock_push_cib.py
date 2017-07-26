from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.assertions import assert_xml_equal
from pcs.test.tools.xml import etree_to_str

CALL_TYPE_PUSH_CIB = "CALL_TYPE_PUSH_CIB"

class Call(object):
    type = CALL_TYPE_PUSH_CIB

    def __init__(self, cib_xml, wait=False):
        self.cib_xml = cib_xml
        self.wait = wait

    def __repr__(self):
        return str("<CibPush wait='{0}'>").format(self.wait)

def get_push_cib(call_queue):
    def push_cib(cib, wait):
        i, expected_call = call_queue.take(CALL_TYPE_PUSH_CIB)
        assert_xml_equal(
            expected_call.cib_xml,
            etree_to_str(cib),
            "Trying to call env.push cib (call no. {0}) with expected cib \n\n"
                .format(i)
        )
        if wait != expected_call.wait:
            raise AssertionError(
                (
                    "Trying to call push cib (call no. {0}) with 'wait' == {1}"
                    " but expected was 'wait' == {2}"
                ).format(i, wait, expected_call.wait)
            )
    return push_cib

def is_push_cib_call_in(call_queue):
    return call_queue.has_type(CALL_TYPE_PUSH_CIB)
