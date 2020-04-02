from unittest import TestCase

from pcs.cli.cluster import command


class ParseNodeAddRemote(TestCase):
    # pylint: disable=protected-access
    def test_deal_with_explicit_address(self):
        self.assertEqual(
            command._node_add_remote_separate_name_and_addr(
                ["name", "address", "a=b"]
            ),
            ("name", "address", ["a=b"]),
        )

    def test_deal_with_implicit_address(self):
        self.assertEqual(
            command._node_add_remote_separate_name_and_addr(["name", "a=b"]),
            ("name", None, ["a=b"]),
        )
