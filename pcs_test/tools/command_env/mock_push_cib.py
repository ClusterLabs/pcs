from pcs_test.tools.assertions import assert_xml_equal
from pcs_test.tools.xml import etree_to_str

CALL_TYPE_PUSH_CIB = "CALL_TYPE_PUSH_CIB"


class Call:
    type = CALL_TYPE_PUSH_CIB

    def __init__(
        self, cib_xml, custom_cib=False, wait_timeout=-1, exception=None
    ):
        self.cib_xml = cib_xml
        self.custom_cib = custom_cib
        self.wait_timeout = wait_timeout
        self.exception = exception

    def __repr__(self):
        return str("<CibPush wait_timeout='{0}'>").format(self.wait_timeout)


def get_push_cib(call_queue):
    def push_cib(lib_env, custom_cib=None, wait_timeout=-1):
        i, expected_call = call_queue.take(CALL_TYPE_PUSH_CIB)

        if custom_cib is None and expected_call.custom_cib:
            raise AssertionError(
                (
                    "Trying to call env.push_cib (call no. {0}) without "
                    "a custom cib but a custom cib was expected"
                ).format(i)
            )
        if custom_cib is not None and not expected_call.custom_cib:
            raise AssertionError(
                (
                    "Trying to call env.push_cib (call no. {0}) with a custom "
                    "cib but no custom cib was expected"
                ).format(i)
            )

        assert_xml_equal(
            expected_call.cib_xml,
            etree_to_str(lib_env.cib),
            (
                "Trying to call env.push_cib (call no. {0}) but cib in env does"
                " not match\n\n"
            ).format(i),
        )

        if wait_timeout != expected_call.wait_timeout:
            raise AssertionError(
                (
                    "Trying to call env.push_cib (call no. {index}) with "
                    "'wait_timeout' == {real_value} ({real_type}) but it was "
                    "expected 'wait_timeout' == {expected_value} "
                    "({expected_type})"
                ).format(
                    index=i,
                    real_value=wait_timeout,
                    real_type=type(wait_timeout),
                    expected_value=expected_call.wait_timeout,
                    expected_type=type(expected_call.wait_timeout),
                )
            )

        if expected_call.exception:
            raise expected_call.exception

    return push_cib


def is_push_cib_call_in(call_queue):
    return call_queue.has_type(CALL_TYPE_PUSH_CIB)
