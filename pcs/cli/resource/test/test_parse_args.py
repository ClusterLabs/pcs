from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
from pcs.cli.resource import parse_args
from pcs.cli.common.errors import CmdLineInputError

class ParseCreateArgs(TestCase):
    def assert_produce(self, arg_list, result):
        self.assertEqual(parse_args.parse_create(arg_list), result)

    def test_no_args(self):
        self.assert_produce([], {
            "meta": {},
            "options": {},
            "op": [],
        })

    def test_only_instance_attributes(self):
        self.assert_produce(["a=b", "c=d"], {
            "meta": {},
            "options": {
                "a": "b",
                "c": "d",
            },
            "op": [],
        })

    def test_only_meta(self):
        self.assert_produce(["meta", "a=b", "c=d"], {
            "options": {},
            "op": [],
            "meta": {
                "a": "b",
                "c": "d",
            },
        })

    def test_only_clone(self):
        self.assert_produce(["clone", "a=b", "c=d"], {
            "meta": {},
            "options": {},
            "op": [],
            "clone": {
                "a": "b",
                "c": "d",
            },
        })

    def test_only_operations(self):
        self.assert_produce([
            "op", "monitor", "a=b", "c=d", "start", "e=f",
        ], {
            "meta": {},
            "options": {},
            "op": [
                {"name": "monitor", "a": "b", "c": "d"},
                {"name": "start", "e": "f"},
            ],
        })

    def test_args_op_clone_meta(self):
        self.assert_produce([
            "a=b", "c=d",
            "meta", "a=b", "c=d",
            "op", "monitor", "a=b", "c=d", "start", "e=f",
            "clone", "a=b", "c=d",
        ], {
            "options": {
                "a": "b",
                "c": "d",
            },
            "op": [
                {"name": "monitor", "a": "b", "c": "d"},
                {"name": "start", "e": "f"},
            ],
            "meta": {
                "a": "b",
                "c": "d",
            },
            "clone": {
                "a": "b",
                "c": "d",
            },
        })

    def assert_raises_cmdline(self, args):
        self.assertRaises(
            CmdLineInputError,
            lambda: parse_args.parse_create(args)
        )


    def test_raises_when_operation_name_does_not_follow_op_keyword(self):
        self.assert_raises_cmdline(["op", "a=b"])
        self.assert_raises_cmdline(["op", "monitor", "a=b", "op", "c=d"])

    def test_raises_when_operation_have_no_option(self):
        self.assert_raises_cmdline(
            ["op", "monitor", "a=b", "start", "stop", "c=d"]
        )
        self.assert_raises_cmdline(
            ["op", "monitor", "a=b", "stop", "c=d", "op", "start"]
        )

    def test_allow_to_repeat_op(self):
        self.assert_produce([
            "op", "monitor", "a=b", "c=d",
            "op", "start", "e=f",
        ], {
            "meta": {},
            "options": {},
            "op": [
                {"name": "monitor", "a": "b", "c": "d"},
                {"name": "start", "e": "f"},
            ],
        })

    def test_deal_with_empty_operatins(self):
        self.assert_raises_cmdline(["op", "monitoring", "a=b", "op"])
