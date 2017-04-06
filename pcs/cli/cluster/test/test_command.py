from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
from pcs.cli.cluster import command

class ParseNodeAddRemote(TestCase):
    def test_deal_with_explicit_name(self):
        self.assertEqual(
            command._node_add_remote_separate_host_and_name(
                ["host", "name", "a=b"]
            ),
            ("host", "name", ["a=b"])
        )

    def test_deal_with_implicit_name(self):
        self.assertEqual(
            command._node_add_remote_separate_host_and_name(["host", "a=b"]),
            ("host", "host", ["a=b"])
        )
