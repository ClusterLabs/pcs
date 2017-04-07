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
            "meta", "e=f", "g=h",
            "op", "monitor", "i=j", "k=l", "start", "m=n",
            "clone", "o=p", "q=r",
        ], {
            "options": {
                "a": "b",
                "c": "d",
            },
            "op": [
                {"name": "monitor", "i": "j", "k": "l"},
                {"name": "start", "m": "n"},
            ],
            "meta": {
                "e": "f",
                "g": "h",
            },
            "clone": {
                "o": "p",
                "q": "r",
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


class ParseCreateSimple(TestCase):
    def assert_produce(self, arg_list, result):
        self.assertEqual(parse_args.parse_create_simple(arg_list), result)

    def test_without_args(self):
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

    def assert_raises_cmdline(self, args):
        self.assertRaises(
            CmdLineInputError,
            lambda: parse_args.parse_create_simple(args)
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


class ParseBundleCreateOptions(TestCase):
    def assert_produce(self, arg_list, result):
        self.assertEqual(
            result,
            parse_args.parse_bundle_create_options(arg_list)
        )

    def assert_raises_cmdline(self, arg_list):
        self.assertRaises(
            CmdLineInputError,
            lambda: parse_args.parse_bundle_create_options(arg_list)
        )

    def test_no_args(self):
        self.assert_produce(
            [],
            {
                "container_type": None,
                "container": {},
                "network": {},
                "port_map": [],
                "storage_map": [],
            }
        )

    def test_container_type(self):
        self.assert_produce(
            ["container", "docker"],
            {
                "container_type": "docker",
                "container": {},
                "network": {},
                "port_map": [],
                "storage_map": [],
            }
        )

    def test_container_options(self):
        self.assert_produce(
            ["container", "a=b", "c=d"],
            {
                "container_type": None,
                "container": {"a": "b", "c": "d"},
                "network": {},
                "port_map": [],
                "storage_map": [],
            }
        )

    def test_container_type_and_options(self):
        self.assert_produce(
            ["container", "docker", "a=b", "c=d"],
            {
                "container_type": "docker",
                "container": {"a": "b", "c": "d"},
                "network": {},
                "port_map": [],
                "storage_map": [],
            }
        )

    def test_container_type_must_be_first(self):
        self.assert_raises_cmdline(["container", "a=b", "docker", "c=d"])

    def test_container_missing_key(self):
        self.assert_raises_cmdline(["container", "docker", "=b", "c=d"])

    def test_network(self):
        self.assert_produce(
            ["network", "a=b", "c=d"],
            {
                "container_type": None,
                "container": {},
                "network": {"a": "b", "c": "d"},
                "port_map": [],
                "storage_map": [],
            }
        )

    def test_network_empty(self):
        self.assert_produce(
            ["network"],
            {
                "container_type": None,
                "container": {},
                "network": {},
                "port_map": [],
                "storage_map": [],
            }
        )

    def test_network_missing_value(self):
        self.assert_raises_cmdline(["network", "a", "c=d"])

    def test_network_missing_key(self):
        self.assert_raises_cmdline(["network", "=b", "c=d"])

    def test_port_map_empty(self):
        self.assert_produce(
            ["port-map"],
            {
                "container_type": None,
                "container": {},
                "network": {},
                "port_map": [{}],
                "storage_map": [],
            }
        )

    def test_port_map_one(self):
        self.assert_produce(
            ["port-map", "a=b", "c=d"],
            {
                "container_type": None,
                "container": {},
                "network": {},
                "port_map": [{"a": "b", "c": "d"}],
                "storage_map": [],
            }
        )

    def test_port_map_more(self):
        self.assert_produce(
            ["port-map", "a=b", "c=d", "port-map", "e=f"],
            {
                "container_type": None,
                "container": {},
                "network": {},
                "port_map": [{"a": "b", "c": "d"}, {"e": "f"}],
                "storage_map": [],
            }
        )

    def test_port_map_missing_value(self):
        self.assert_raises_cmdline(["port-map", "a", "c=d"])

    def test_port_map_missing_key(self):
        self.assert_raises_cmdline(["port-map", "=b", "c=d"])

    def test_storage_map_empty(self):
        self.assert_produce(
            ["storage-map"],
            {
                "container_type": None,
                "container": {},
                "network": {},
                "port_map": [],
                "storage_map": [{}],
            }
        )

    def test_storage_map_one(self):
        self.assert_produce(
            ["storage-map", "a=b", "c=d"],
            {
                "container_type": None,
                "container": {},
                "network": {},
                "port_map": [],
                "storage_map": [{"a": "b", "c": "d"}],
            }
        )

    def test_storage_map_more(self):
        self.assert_produce(
            ["storage-map", "a=b", "c=d", "storage-map", "e=f"],
            {
                "container_type": None,
                "container": {},
                "network": {},
                "port_map": [],
                "storage_map": [{"a": "b", "c": "d"}, {"e": "f"}],
            }
        )

    def test_storage_map_missing_value(self):
        self.assert_raises_cmdline(["storage-map", "a", "c=d"])

    def test_storage_map_missing_key(self):
        self.assert_raises_cmdline(["storage-map", "=b", "c=d"])

    def test_all(self):
        self.assert_produce(
            [
                "container", "docker", "a=b", "c=d",
                "network", "e=f", "g=h",
                "port-map", "i=j", "k=l",
                "port-map", "m=n", "o=p",
                "storage-map", "q=r", "s=t",
                "storage-map", "u=v", "w=x",
            ],
            {
                "container_type": "docker",
                "container": {"a": "b", "c": "d"},
                "network": {"e": "f", "g": "h"},
                "port_map": [{"i": "j", "k": "l"}, {"m": "n", "o": "p"}],
                "storage_map": [{"q": "r", "s": "t"}, {"u": "v", "w": "x"}],
            }
        )

    def test_all_mixed(self):
        self.assert_produce(
            [
                "storage-map", "q=r", "s=t",
                "port-map", "i=j", "k=l",
                "network", "e=f",
                "container", "docker", "a=b",
                "storage-map", "u=v", "w=x",
                "port-map", "m=n", "o=p",
                "network", "g=h",
                "container", "c=d",
            ],
            {
                "container_type": "docker",
                "container": {"a": "b", "c": "d"},
                "network": {"e": "f", "g": "h"},
                "port_map": [{"i": "j", "k": "l"}, {"m": "n", "o": "p"}],
                "storage_map": [{"q": "r", "s": "t"}, {"u": "v", "w": "x"}],
            }
        )


class BuildOperations(TestCase):
    def assert_produce(self, arg_list, result):
        self.assertEqual(result, parse_args.build_operations(arg_list))

    def assert_raises_cmdline(self, arg_list):
        self.assertRaises(
            CmdLineInputError,
            lambda: parse_args.build_operations(arg_list)
        )

    def test_return_empty_list_on_empty_input(self):
        self.assert_produce([], [])

    def test_return_all_operations_specified_in_the_same_group(self):
        self.assert_produce(
            [
                ["monitor", "interval=10s", "start", "timeout=20s"]
            ],
            [
                ["name=monitor", "interval=10s"],
                ["name=start", "timeout=20s"],
            ]
        )

    def test_return_all_operations_specified_in_different_groups(self):
        self.assert_produce(
            [
                ["monitor", "interval=10s"],
                ["start", "timeout=20s"],
            ],
            [
                ["name=monitor", "interval=10s"],
                ["name=start", "timeout=20s"],
            ]
        )

    def test_refuse_empty_operation(self):
        self.assert_raises_cmdline([[]])

    def test_refuse_operation_without_attribute(self):
        self.assert_raises_cmdline([["monitor"]])

    def test_refuse_operation_without_name(self):
        self.assert_raises_cmdline([["interval=10s"]])
