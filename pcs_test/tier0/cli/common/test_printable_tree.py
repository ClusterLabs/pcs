from unittest import TestCase

from pcs.cli.common import printable_tree as lib


class Node:
    def __init__(self, title, detail, is_leaf, members):
        self.title = title
        self.detail = detail
        self.is_leaf = is_leaf
        self.members = members

def node(an_id, detail=0, leaf=False, members=None):
    return Node(
        f"{an_id}-title",
        [f"{an_id}-detail{i}" for i in range(detail)],
        leaf,
        members=members or [],
    )

class TreeToLines(TestCase):
    def test_empty(self):
        self.assertEqual(["l0-title"], lib.tree_to_lines(node("l0")))

    def test_empty_leaf(self):
        self.assertEqual(
            ["l0-title [displayed elsewhere]"],
            lib.tree_to_lines(node("l0", leaf=True)),
        )

    def test_detail_simple(self):
        self.assertEqual(
            [
                "l0-title",
                "   l0-detail0",
            ],
            lib.tree_to_lines(node("l0", 1)),
        )

    def test_detail(self):
        self.assertEqual(
            [
                "l0-title",
                "   l0-detail0",
                "   l0-detail1",
                "   l0-detail2",
            ],
            lib.tree_to_lines(node("l0", 3)),
        )

    def test_detail_leaf(self):
        self.assertEqual(
            ["l0-title [displayed elsewhere]"],
            lib.tree_to_lines(node("l0", 3, True)),
        )

    def test_one_member(self):
        self.assertEqual(
            [
                "l0-title",
                "`- l1-title",
            ],
            lib.tree_to_lines(node("l0", members=[node("l1")])),
        )

    def test_one_member_leaf(self):
        self.assertEqual(
            ["l0-title [displayed elsewhere]"],
            lib.tree_to_lines(node("l0", leaf=True, members=[node("l1")])),
        )

    def test_multiple_members(self):
        self.assertEqual(
            [
                "l0-title",
                "|- l1-title",
                "|- l2-title",
                "`- l3-title",
            ],
            lib.tree_to_lines(
                node("l0", members=[node("l1"), node("l2"), node("l3")])
            ),
        )

    def test_multiple_members_detail(self):
        self.assertEqual(
            [
                "l0-title",
                "|  l0-detail0",
                "|  l0-detail1",
                "|- l1-title",
                "|- l2-title",
                "`- l3-title",
            ],
            lib.tree_to_lines(
                node(
                    "l0", detail=2, members=[node("l1"), node("l2"), node("l3")]
                )
            ),
        )

    def test_multiple_members_detail_leaf(self):
        self.assertEqual(
            ["l0-title [displayed elsewhere]"],
            lib.tree_to_lines(
                node("l0", 2, True, [node("l1"), node("l2"), node("l3")])
            ),
        )

    def test_complex_tree_wide(self):
        self.assertEqual(
            [
                "0-title",
                "|  0-detail0",
                "|  0-detail1",
                "|- 00-title",
                "|     00-detail0",
                "|     00-detail1",
                "|- 01-title",
                "|  |- 010-title",
                "|  |  `- 0100-title [displayed elsewhere]",
                "|  `- 011-title",
                "|- 02-title",
                "|  |  02-detail0",
                "|  |  02-detail1",
                "|  |  02-detail2",
                "|  |- 020-title",
                "|  `- 021-title",
                "|     |  021-detail0",
                "|     |- 0210-title [displayed elsewhere]",
                "|     |- 0211-title",
                "|     |     0211-detail0",
                "|     |     0211-detail1",
                "|     `- 0212-title",
                "|        `- 02120-title",
                "|- 03-title",
                "|  `- 030-title",
                "|     `- 0300-title",
                "|- 04-title [displayed elsewhere]",
                "`- 05-title",
                "      05-detail0",
            ],
            lib.tree_to_lines(
                node(
                    "0",
                    2,
                    members=[
                        node("00", 2),
                        node(
                            "01", members=[
                                node("010", members=[node("0100", leaf=True)]),
                                node("011"),
                            ],
                        ),
                        node(
                            "02", 3, members=[
                                node("020"),
                                node(
                                    "021", 1, members=[
                                        node("0210", leaf=True),
                                        node("0211", 2),
                                        node("0212", members=[node("02120")]),
                                    ],
                                ),
                            ],
                        ),
                        node(
                            "03", members=[node("030", members=[node("0300")])],
                        ),
                        node("04", leaf=True),
                        node("05", 1),
                    ],
                )
            ),
        )

    def test_complex_tree_deep(self):
        self.assertEqual(
            [
                "0-title",
                "|  0-detail0",
                "`- 00-title",
                "   |- 000-title",
                "   |     000-detail0",
                "   |     000-detail1",
                "   `- 001-title",
                "      |- 0010-title [displayed elsewhere]",
                "      |- 0011-title",
                "      |     0011-detail0",
                "      |     0011-detail1",
                "      `- 0012-title",
                "         `- 00120-title",
            ],
            lib.tree_to_lines(
                node("0", 1, members=[
                    node("00", members=[
                        node("000", 2),
                        node("001", members=[
                            node("0010", leaf=True),
                            node("0011", 2),
                            node("0012", members=[node("00120")]),
                        ]),
                    ]),
                ])
            ),
        )
