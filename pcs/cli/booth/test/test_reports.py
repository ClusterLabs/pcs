from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

from pcs.cli.booth.console_report import CODE_TO_MESSAGE_BUILDER_MAP
from pcs.common import report_codes as codes


class BoothConfigAccetedByNodeTest(TestCase):
    def setUp(self):
        self.build = CODE_TO_MESSAGE_BUILDER_MAP[
            codes.BOOTH_CONFIG_ACCEPTED_BY_NODE
        ]

    def test_crete_message_with_empty_name_list(self):
        self.assertEqual("Booth config saved.", self.build({
            "node": None,
            "name_list": [],
        }))

    def test_crete_message_with_name_booth_only(self):
        self.assertEqual("Booth config saved.", self.build({
            "node": None,
            "name_list": ["booth"],
        }))

    def test_crete_message_with_single_name(self):
        self.assertEqual("Booth config(s) (some) saved.", self.build({
            "node": None,
            "name_list": ["some"],
        }))

    def test_crete_message_with_multiple_name(self):
        self.assertEqual("Booth config(s) (some, another) saved.", self.build({
            "node": None,
            "name_list": ["some", "another"],
        }))

    def test_crete_message_with_empty_node(self):
        self.assertEqual(
            "node1: Booth config(s) (some, another) saved.",
            self.build({
                "node": "node1",
                "name_list": ["some", "another"],
            }),
        )

class BoothConfigDistributionNodeErrorTest(TestCase):
    def setUp(self):
        self.build = CODE_TO_MESSAGE_BUILDER_MAP[
            codes.BOOTH_CONFIG_DISTRIBUTION_NODE_ERROR
        ]

    def test_create_message_for_empty_name(self):
        self.assertEqual(
            "Unable to save booth config on node 'node1': reason1",
            self.build({
                "node": "node1",
                "reason": "reason1",
                "name": None,
            })
        )

    def test_create_message_for_booth_name(self):
        self.assertEqual(
            "Unable to save booth config on node 'node1': reason1",
            self.build({
                "node": "node1",
                "reason": "reason1",
                "name": "booth",
            })
        )

    def test_create_message_for_another_name(self):
        self.assertEqual(
            "Unable to save booth config (another) on node 'node1': reason1",
            self.build({
                "node": "node1",
                "reason": "reason1",
                "name": "another",
            })
        )

class BoothConfigReadErrorTest(TestCase):
    def setUp(self):
        self.build = CODE_TO_MESSAGE_BUILDER_MAP[
            codes.BOOTH_CONFIG_READ_ERROR
        ]

    def test_create_message_for_empty_name(self):
        self.assertEqual("Unable to read booth config.", self.build({
            "name": None,
        }))

    def test_create_message_for_booth_name(self):
        self.assertEqual("Unable to read booth config.", self.build({
            "name": "booth",
        }))

    def test_create_message_for_another_name(self):
        self.assertEqual("Unable to read booth config (another).", self.build({
            "name": "another",
        }))

class BoothFetchingConfigFromNodeTest(TestCase):
    def setUp(self):
        self.build = CODE_TO_MESSAGE_BUILDER_MAP[
            codes.BOOTH_FETCHING_CONFIG_FROM_NODE
        ]

    def test_create_message_for_empty_name(self):
        self.assertEqual(
            "Fetching booth config from node 'node1'...",
            self.build({
                "config": None,
                "node": "node1",
            })
        )

    def test_create_message_for_booth_name(self):
        self.assertEqual(
            "Fetching booth config from node 'node1'...",
            self.build({
                "config": "booth",
                "node": "node1",
            })
        )

    def test_create_message_for_another_name(self):
        self.assertEqual(
            "Fetching booth config 'another' from node 'node1'...",
            self.build({
                "config": "another",
                "node": "node1",
            })
        )
