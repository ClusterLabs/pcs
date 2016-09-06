from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
from pcs.cli.common.console_report import(
    indent,
    CODE_TO_MESSAGE_BUILDER_MAP,
    format_optional,
)
from pcs.common import report_codes as codes

class IndentTest(TestCase):
    def test_indent_list_of_lines(self):
        self.assertEqual(
            indent([
                "first",
                "second"
            ]),
            [
                "  first",
                "  second"
            ]
        )

class BuildInvalidOptionMessageTest(TestCase):
    def setUp(self):
        self.build = CODE_TO_MESSAGE_BUILDER_MAP[codes.INVALID_OPTION]
    def test_build_message_with_type(self):
        self.assertEqual(
            "invalid TYPE option 'NAME', allowed options are: FIRST, SECOND",
            self.build({
                "option_name": "NAME",
                "option_type": "TYPE",
                "allowed": sorted(["FIRST", "SECOND"]),
            })
        )

    def test_build_message_without_type(self):
        self.assertEqual(
            "invalid option 'NAME', allowed options are: FIRST, SECOND",
            self.build({
                "option_name": "NAME",
                "option_type": "",
                "allowed": sorted(["FIRST", "SECOND"]),
            })
        )

class BuildInvalidOptionValueMessageTest(TestCase):
    def setUp(self):
        self.build = CODE_TO_MESSAGE_BUILDER_MAP[codes.INVALID_OPTION_VALUE]
    def test_build_message_with_multiple_allowed_values(self):
        self.assertEqual(
            "'VALUE' is not a valid NAME value, use FIRST, SECOND",
            self.build({
                "option_name": "NAME",
                "option_value": "VALUE",
                "allowed_values": sorted(["FIRST", "SECOND"]),
            })
        )

    def test_build_message_with_hint(self):
        self.assertEqual(
            "'VALUE' is not a valid NAME value, use some hint",
            self.build({
                "option_name": "NAME",
                "option_value": "VALUE",
                "allowed_values": "some hint",
            })
        )

class BuildServiceStartErrorTest(TestCase):
    def setUp(self):
        self.build = CODE_TO_MESSAGE_BUILDER_MAP[codes.SERVICE_START_ERROR]

    def test_build_message_with_instance_and_node(self):
        self.assertEqual(
            "NODE: Unable to start SERVICE@INSTANCE: REASON",
            self.build({
                "service": "SERVICE",
                "reason": "REASON",
                "node": "NODE",
                "instance": "INSTANCE",
            })
        )
    def test_build_message_with_instance_only(self):
        self.assertEqual(
            "Unable to start SERVICE@INSTANCE: REASON",
            self.build({
                "service": "SERVICE",
                "reason": "REASON",
                "node": "",
                "instance": "INSTANCE",
            })
        )

    def test_build_message_with_node_only(self):
        self.assertEqual(
            "NODE: Unable to start SERVICE: REASON",
            self.build({
                "service": "SERVICE",
                "reason": "REASON",
                "node": "NODE",
                "instance": "",
            })
        )

    def test_build_message_without_node_and_instance(self):
        self.assertEqual(
            "Unable to start SERVICE: REASON",
            self.build({
                "service": "SERVICE",
                "reason": "REASON",
                "node": "",
                "instance": "",
            })
        )

class BuildInvalidIdTest(TestCase):
    def setUp(self):
        self.build = CODE_TO_MESSAGE_BUILDER_MAP[codes.INVALID_ID]

    def test_build_message_with_first_char_invalid(self):
        self.assertEqual(
            (
                "invalid ID_DESCRIPTION 'ID', 'INVALID_CHARACTER' is not a"
                " valid first character for a ID_DESCRIPTION"
            ),
            self.build({
                "id_description": "ID_DESCRIPTION",
                "id": "ID",
                "invalid_character": "INVALID_CHARACTER",
                "is_first_char": True,
            })
        )
    def test_build_message_with_non_first_char_invalid(self):
        self.assertEqual(
            (
                "invalid ID_DESCRIPTION 'ID', 'INVALID_CHARACTER' is not a"
                " valid character for a ID_DESCRIPTION"
            ),
            self.build({
                "id_description": "ID_DESCRIPTION",
                "id": "ID",
                "invalid_character": "INVALID_CHARACTER",
                "is_first_char": False,
            })
        )

class BuildRunExternalaStartedTest(TestCase):
    def setUp(self):
        self.build = CODE_TO_MESSAGE_BUILDER_MAP[
            codes.RUN_EXTERNAL_PROCESS_STARTED
        ]

    def test_build_message_with_stdin(self):
        self.assertEqual(
            (
                "Running: COMMAND\n"
                "--Debug Input Start--\n"
                "STDIN\n"
                "--Debug Input End--\n"
            ),
            self.build({
                "command": "COMMAND",
                "stdin": "STDIN",
            })
        )

    def test_build_message_without_stdin(self):
        self.assertEqual(
            "Running: COMMAND\n",
            self.build({
                "command": "COMMAND",
                "stdin": "",
            })
        )

class BuildNodeCommunicationStartedTest(TestCase):
    def setUp(self):
        self.build = CODE_TO_MESSAGE_BUILDER_MAP[
            codes.NODE_COMMUNICATION_STARTED
        ]

    def test_build_message_with_data(self):
        self.assertEqual(
            (
                "Sending HTTP Request to: TARGET\n"
                "--Debug Input Start--\n"
                "DATA\n"
                "--Debug Input End--\n"
            ),
            self.build({
                "target": "TARGET",
                "data": "DATA",
            })
        )

    def test_build_message_without_data(self):
        self.assertEqual(
            "Sending HTTP Request to: TARGET\n",
            self.build({
                "target": "TARGET",
                "data": "",
            })
        )

class FormatOptionalTest(TestCase):
    def test_info_key_is_falsy(self):
        self.assertEqual("", format_optional("", "{0}: "))

    def test_info_key_is_not_falsy(self):
        self.assertEqual("A: ", format_optional("A", "{0}: "))
