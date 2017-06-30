from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.misc import create_setup_patch_mixin
from pcs.test.tools.pcs_unittest import TestCase

from pcs.common import report_codes
from pcs.lib import node_communication_format
from pcs.lib.errors import ReportItemSeverity as severity

SetupPatchMixin = create_setup_patch_mixin(node_communication_format)

class PcmkAuthkeyFormat(TestCase, SetupPatchMixin):
    def test_create_expected_dict(self):
        b64encode = self.setup_patch("base64.b64encode")
        b64encode.return_value = "encoded_content".encode()
        self.assertEqual(
            node_communication_format.pcmk_authkey_format("content"),
            {
                "data": b64encode.return_value.decode("utf-8"),
                "type": "pcmk_remote_authkey",
                "rewrite_existing": True,
            }
        )


class ServiceCommandFormat(TestCase):
    def test_create_expected_dict(self):
        self.assertEqual(
            node_communication_format.service_cmd_format("pcsd", "start"),
            {
                "type": "service_command",
                "service": "pcsd",
                "command": "start",
            }
        )

def fixture_invalid_response_format(node_label):
    return (
        severity.ERROR,
        report_codes.INVALID_RESPONSE_FORMAT,
        {
            "node": node_label
        },
        None
    )


class ResponseToNodeActionResults(TestCase):
    def setUp(self):
        self.expected_keys = ["file"]
        self.main_key = "files"
        self.node_label = "node1"

    def assert_result_causes_invalid_format(self, result):
        assert_raise_library_error(
            lambda: node_communication_format.response_to_result(
                result,
                self.main_key,
                self.expected_keys,
                self.node_label,
            ),
            fixture_invalid_response_format(self.node_label)
        )

    def test_report_response_is_not_dict(self):
        self.assert_result_causes_invalid_format("bad answer")

    def test_report_dict_without_mandatory_key(self):
        self.assert_result_causes_invalid_format({})

    def test_report_when_on_files_is_not_dict(self):
        self.assert_result_causes_invalid_format({"files": True})

    def test_report_when_on_some_result_is_not_dict(self):
        self.assert_result_causes_invalid_format({
            "files": {
                "file": True
            }
        })

    def test_report_when_on_some_result_is_without_code(self):
        self.assert_result_causes_invalid_format({
            "files": {
                "file": {"message": "some_message"}
            }
        })

    def test_report_when_on_some_result_is_without_message(self):
        self.assert_result_causes_invalid_format({
            "files": {
                "file": {"code": "some_code"}
            }
        })

    def test_report_when_some_result_key_is_missing(self):
        self.assert_result_causes_invalid_format({
            "files": {
            }
        })

    def test_report_when_some_result_key_is_extra(self):
        self.assert_result_causes_invalid_format({
            "files": {
                "file": {
                    "code": "some_code",
                    "message": "some_message",
                },
                "extra": {
                    "code": "some_extra_code",
                    "message": "some_extra_message",
                }
            }
        })
