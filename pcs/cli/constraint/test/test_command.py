from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
from pcs.cli.constraint import command

from pcs.test.tools.pcs_unittest import mock

def fixture_constraint():
    return {
        "resource_sets": [
            {"ids": ["a", "b"], "options": {"c": "d", "e": "f"}},
            {"ids": ["g", "h"], "options": {"i": "j", "k": "l"}},
        ],
        "options": {"m": "n", "o":"p"}
    }

def fixture_constraint_console():
    return "  set a b c=d e=f (id:) set g h i=j k=l (id:) setoptions m=n o=p (id:)"


class ShowConstraintsWithSetTest(TestCase):
    def test_return_line_list(self):
        self.assertEqual(
            [
                "Resource Sets:",
                "  set a b c=d e=f set g h i=j k=l setoptions m=n o=p",
            ],
            command.show_constraints_with_set(
                [fixture_constraint()],
                show_detail=False
            )
        )

    def test_return_line_list_with_id(self):
        self.assertEqual(
            [
                "Resource Sets:",
                fixture_constraint_console(),
            ],
            command.show_constraints_with_set(
                [fixture_constraint()],
                show_detail=True
            )
        )

class ShowTest(TestCase):
    def test_show_only_caption_when_no_constraint_loaded(self):
        self.assertEqual(["caption"], command.show(
            "caption",
            load_constraints=lambda: {"plain": [], "with_resource_sets": []},
            format_options=lambda: None,
            modificators={"full": False}
        ))

    def test_show_constraints_full(self):
        load_constraints = mock.Mock()
        load_constraints.return_value = {
            "plain": [{"options": {"id": "plain_id"}}],
            "with_resource_sets": [fixture_constraint()]
        }
        format_options = mock.Mock()
        format_options.return_value = "plain constraint listing"
        self.assertEqual(
            [
                "caption",
                "  plain constraint listing",
                "  Resource Sets:",
                "  "+fixture_constraint_console(),
            ],
            command.show(
                "caption",
                load_constraints,
                format_options,
                {"full": True}
            )
        )
