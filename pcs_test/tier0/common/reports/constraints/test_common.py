from unittest import TestCase

from pcs.common.reports.constraints import common


class PrepareOptionsTest(TestCase):
    def test_prepare_options_with_id(self):
        self.assertEqual(
            ["a=b", "c=d", "(id:some_id)"],
            common.prepare_options({"c": "d", "a": "b", "id": "some_id"}),
        )


class ResourceSetsTest(TestCase):
    # pylint: disable=protected-access
    def test_prepare_resource_sets(self):
        self.assertEqual(
            [
                "set",
                "a",
                "b",
                "c=d",
                "e=f",
                "(id:some_id)",
                "set",
                "g",
                "h",
                "i=j",
                "k=l",
                "(id:some_id_2)",
            ],
            common._resource_sets(
                [
                    {
                        "ids": ["a", "b"],
                        "options": {"c": "d", "e": "f", "id": "some_id"},
                    },
                    {
                        "ids": ["g", "h"],
                        "options": {"i": "j", "k": "l", "id": "some_id_2"},
                    },
                ]
            ),
        )
