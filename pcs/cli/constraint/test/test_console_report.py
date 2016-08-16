from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
from pcs.cli.constraint import console_report

class OptionsTest(TestCase):
    def test_get_console_options_from_lib_options(self):
        self.assertEqual(
            ["a=b", "c=d"],
            console_report.options({"c": "d", "a": "b", "id":"some_id"})
        )

class IdFromOptionsTest(TestCase):
    def test_get_id_from_options(self):
        self.assertEqual(
            '(id:some_id)',
            console_report.id_from_options({"c": "d", "a": "b", "id":"some_id"})
        )

class PrepareOptionsTest(TestCase):
    def test_prepare_options_with_id(self):
        self.assertEqual(
            ["a=b", "c=d", '(id:some_id)'],
            console_report.prepare_options({"c": "d", "a": "b", "id":"some_id"})
        )
    def test_prepare_options_without_id(self):
        self.assertEqual(
            ["a=b", "c=d"],
            console_report.prepare_options(
                {"c": "d", "a": "b", "id":"some_id"},
                with_id=False
            )
        )

class ResourceSetsTest(TestCase):
    def test_prepare_resource_sets_without_id(self):
        self.assertEqual(
            ['set', 'a', 'b', 'c=d', 'e=f', 'set', 'g', 'h', 'i=j', 'k=l'],
            console_report.resource_sets(
                [
                    {
                        "ids": ["a", "b"],
                        "options": {"c": "d", "e": "f", "id": "some_id"},
                    },
                    {
                        "ids": ["g", "h"],
                        "options": {"i": "j", "k": "l", "id": "some_id_2"},
                    },
                ],
                with_id=False
            )
        )

    def test_prepare_resource_sets_with_id(self):
        self.assertEqual(
            [
                'set', 'a', 'b', 'c=d', 'e=f', '(id:some_id)',
                'set', 'g', 'h', 'i=j', 'k=l', '(id:some_id_2)'
            ],
            console_report.resource_sets([
                {
                    "ids": ["a", "b"],
                    "options": {"c": "d", "e": "f", "id": "some_id"},
                },
                {
                    "ids": ["g", "h"],
                    "options": {"i": "j", "k": "l", "id": "some_id_2"},
                },
            ])
        )
