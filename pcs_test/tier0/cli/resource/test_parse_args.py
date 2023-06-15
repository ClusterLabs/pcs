from unittest import (
    TestCase,
    mock,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.resource import parse_args


class ParseCloneArgs(TestCase):
    def setUp(self):
        print_patcher = mock.patch("pcs.cli.reports.output.print_to_stderr")
        self.print_mock = print_patcher.start()
        self.addCleanup(print_patcher.stop)
        self.meta_deprecated = (
            "Deprecation Warning: configuring meta attributes without "
            "specifying the 'meta' keyword is deprecated and will be removed "
            "in a future release"
        )

    def assert_stderr(self, stderr=None):
        if stderr is None:
            self.print_mock.assert_not_called()
        else:
            self.print_mock.assert_called_once_with(stderr)

    def assert_produce(self, arg_list, result, promotable=False, stderr=None):
        self.assertEqual(
            parse_args.parse_clone(arg_list, promotable=promotable),
            result,
        )
        self.assert_stderr(stderr)

    def assert_raises_cmdline(
        self, args, expected_msg, promotable=False, stderr=None
    ):
        with self.assertRaises(CmdLineInputError) as cm:
            parse_args.parse_clone(args, promotable=promotable)
        self.assertEqual(cm.exception.message, expected_msg)
        self.assert_stderr(stderr)

    def test_no_args(self):
        self.assert_produce([], {"clone_id": None, "meta": {}})

    def test_clone_id(self):
        self.assert_produce(
            ["CustomCloneId"],
            {"clone_id": "CustomCloneId", "meta": {}},
        )

    def test_clone_options(self):
        self.assert_produce(
            ["a=b", "c=d"],
            {"clone_id": None, "meta": {"a": "b", "c": "d"}},
            stderr=self.meta_deprecated,
        )

    def test_meta_options(self):
        self.assert_produce(
            ["meta", "a=b", "c=d"],
            {"clone_id": None, "meta": {"a": "b", "c": "d"}},
        )

    def test_clone_id_and_clone_meta_options(self):
        self.assert_produce(
            ["CustomCloneId", "a=b", "c=d", "meta", "e=f", "g=h"],
            {
                "clone_id": "CustomCloneId",
                "meta": {"a": "b", "c": "d", "e": "f", "g": "h"},
            },
            stderr=self.meta_deprecated,
        )

    def test_op_options(self):
        self.assert_raises_cmdline(
            ["op", "start", "timeout=30s"],
            "op settings must be changed on base resource, not the clone",
        )

    def test_op_options_and_clone_id(self):
        self.assert_raises_cmdline(
            ["CloneId", "op", "start", "timeout=30s"],
            "op settings must be changed on base resource, not the clone",
        )

    def test_missing_option_value(self):
        self.assert_raises_cmdline(
            ["CloneId", "a"],
            "missing value of 'a' option",
            stderr=self.meta_deprecated,
        )

    def test_missing_meta_option_value(self):
        self.assert_raises_cmdline(["meta", "m"], "missing value of 'm' option")

    def test_promotable_keyword_and_option(self):
        self.assert_raises_cmdline(
            ["CloneId", "promotable=true", "meta", "promotable=true"],
            "you cannot specify both promotable option and promotable keyword",
            promotable=True,
            stderr=self.meta_deprecated,
        )

    def test_different_values_of_option_and_meta_option(self):
        self.assert_raises_cmdline(
            ["CloneId", "promotable=true", "meta", "promotable=false"],
            (
                "duplicate option 'promotable' with different values 'true' and"
                " 'false'"
            ),
            promotable=True,
            stderr=self.meta_deprecated,
        )


class ParseCreateArgs(TestCase):
    # pylint: disable=too-many-public-methods
    future = False
    msg_clone_without_meta = (
        "Deprecation Warning: Configuring clone meta attributes without "
        "specifying the 'meta' keyword after the 'clone' keyword is deprecated "
        "and will be removed in a future release. Specify --future to switch "
        "to the future behavior."
    )
    msg_clone_without_meta_err = (
        "Specifying instance attributes for a clone is not supported. Use "
        "'meta' after 'clone' if you want to specify meta attributes."
    )
    msg_promotable_without_meta = (
        "Deprecation Warning: Configuring promotable meta attributes without "
        "specifying the 'meta' keyword after the 'promotable' keyword is deprecated "
        "and will be removed in a future release. Specify --future to switch "
        "to the future behavior."
    )
    msg_promotable_without_meta_err = (
        "Specifying instance attributes for a promotable is not supported. Use "
        "'meta' after 'promotable' if you want to specify meta attributes."
    )
    msg_meta_after_clone = (
        "Deprecation Warning: Specifying 'meta' after 'clone' now defines "
        "meta attributes for the base resource. In future, this will define "
        "meta attributes for the clone. Specify --future to switch to the "
        "future behavior."
    )
    msg_op_after_clone = (
        "Deprecation Warning: Specifying 'op' after 'clone' now defines "
        "operations for the base resource. In future, this will be removed and "
        "operations will have to be specified before 'clone'. Specify --future "
        "to switch to the future behavior."
    )
    msg_op_after_clone_err = (
        "op settings must be defined on the base resource, not the clone"
    )
    msg_meta_after_bundle = (
        "Deprecation Warning: Specifying 'meta' after 'bundle' now defines "
        "meta options for the base resource. In future, this will be removed "
        "and meta options will have to be specified before 'bundle'. Specify "
        "--future to switch to the future behavior."
    )
    msg_meta_after_bundle_err = (
        "meta options must be defined on the base resource, not the bundle"
    )
    msg_op_after_bundle = (
        "Deprecation Warning: Specifying 'op' after 'bundle' now defines "
        "operations for the base resource. In future, this will be removed and "
        "operations will have to be specified before 'bundle'. Specify "
        "--future to switch to the future behavior."
    )
    msg_op_after_bundle_err = (
        "op settings must be defined on the base resource, not the bundle"
    )

    def setUp(self):
        print_patcher = mock.patch("pcs.cli.reports.output.print_to_stderr")
        self.print_mock = print_patcher.start()
        self.addCleanup(print_patcher.stop)

    def assert_stderr(self, stderr=None):
        if stderr is None:
            self.print_mock.assert_not_called()
        else:
            calls = [mock.call(item) for item in stderr]
            self.print_mock.assert_has_calls(calls)
            self.assertEqual(self.print_mock.call_count, len(calls))

    def assert_produce(self, arg_list, result):
        self.assertEqual(parse_args.parse_create(arg_list, self.future), result)

    def assert_raises_cmdline(self, args, msg=""):
        with self.assertRaises(CmdLineInputError) as cm:
            parse_args.parse_create(args, self.future)
        exception = cm.exception
        self.assertEqual(msg, exception.message)

    def test_no_args(self):
        self.assert_produce(
            [],
            {
                "meta": {},
                "options": {},
                "op": [],
            },
        )
        self.assert_stderr()

    def test_only_instance_attributes(self):
        self.assert_produce(
            ["a=b", "c=d"],
            {
                "meta": {},
                "options": {
                    "a": "b",
                    "c": "d",
                },
                "op": [],
            },
        )
        self.assert_stderr()

    def test_only_meta(self):
        self.assert_produce(
            ["meta", "a=b", "c=d"],
            {
                "options": {},
                "op": [],
                "meta": {
                    "a": "b",
                    "c": "d",
                },
            },
        )
        self.assert_stderr()

    def test_only_clone(self):
        self.assert_produce(
            ["clone", "a=b", "c=d"],
            {
                "meta": {},
                "options": {},
                "op": [],
                "clone": {
                    "a": "b",
                    "c": "d",
                },
            },
        )
        self.assert_stderr([self.msg_clone_without_meta])

    def test_only_clone_with_custom_id(self):
        self.assert_produce(
            ["clone", "CustomCloneId"],
            {
                "meta": {},
                "options": {},
                "op": [],
                "clone": {},
                "clone_id": "CustomCloneId",
            },
        )
        self.assert_stderr()

    def test_only_clone_with_custom_id_and_meta(self):
        self.assert_produce(
            ["clone", "CustomCloneId", "a=b", "c=d"],
            {
                "meta": {},
                "options": {},
                "op": [],
                "clone": {
                    "a": "b",
                    "c": "d",
                },
                "clone_id": "CustomCloneId",
            },
        )
        self.assert_stderr([self.msg_clone_without_meta])

    def test_only_promotable(self):
        self.assert_produce(
            ["promotable", "a=b", "c=d"],
            {
                "meta": {},
                "options": {},
                "op": [],
                "promotable": {
                    "a": "b",
                    "c": "d",
                },
            },
        )
        self.assert_stderr([self.msg_promotable_without_meta])

    def test_only_promotable_with_custom_id(self):
        self.assert_produce(
            ["promotable", "CustomCloneId"],
            {
                "meta": {},
                "options": {},
                "op": [],
                "promotable": {},
                "clone_id": "CustomCloneId",
            },
        )
        self.assert_stderr()

    def test_only_promotable_with_custom_id_and_meta(self):
        self.assert_produce(
            ["promotable", "CustomCloneId", "a=b", "c=d"],
            {
                "meta": {},
                "options": {},
                "op": [],
                "promotable": {
                    "a": "b",
                    "c": "d",
                },
                "clone_id": "CustomCloneId",
            },
        )
        self.assert_stderr([self.msg_promotable_without_meta])

    def test_only_operations(self):
        self.assert_produce(
            [
                "op",
                "monitor",
                "a=b",
                "c=d",
                "start",
                "e=f",
            ],
            {
                "meta": {},
                "options": {},
                "op": [
                    {"name": "monitor", "a": "b", "c": "d"},
                    {"name": "start", "e": "f"},
                ],
            },
        )
        self.assert_stderr()

    def test_args_op_clone_meta(self):
        self.assert_produce(
            [
                "a=b",
                "c=d",
                "meta",
                "e=f",
                "g=h",
                "op",
                "monitor",
                "i=j",
                "k=l",
                "start",
                "m=n",
                "clone",
                "o=p",
                "q=r",
            ],
            {
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
            },
        )
        self.assert_stderr([self.msg_clone_without_meta])

    def test_raises_when_operation_name_does_not_follow_op_keyword(self):
        msg = "When using 'op' you must specify an operation name after 'op'"
        self.assert_raises_cmdline(["op", "a=b"], msg)
        self.assert_raises_cmdline(["op", "monitor", "a=b", "op", "c=d"], msg)

    def test_raises_when_operation_have_no_option(self):
        msg = (
            "When using 'op' you must specify an operation name and at least "
            "one option"
        )
        self.assert_raises_cmdline(
            ["op", "monitor", "a=b", "start", "stop", "c=d"], msg
        )
        self.assert_raises_cmdline(
            ["op", "monitor", "a=b", "stop", "c=d", "op", "start"], msg
        )

    def test_allow_to_repeat_op(self):
        self.assert_produce(
            [
                "op",
                "monitor",
                "a=b",
                "c=d",
                "op",
                "start",
                "e=f",
            ],
            {
                "meta": {},
                "options": {},
                "op": [
                    {"name": "monitor", "a": "b", "c": "d"},
                    {"name": "start", "e": "f"},
                ],
            },
        )
        self.assert_stderr()

    def test_deal_with_empty_operatins(self):
        msg = (
            "When using 'op' you must specify an operation name and at least "
            "one option"
        )
        self.assert_raises_cmdline(["op", "monitoring", "a=b", "op"], msg)

    def test_op_after_clone(self):
        self.assert_produce(
            [
                "a=b",
                "c=d",
                "meta",
                "e=f",
                "g=h",
                "clone",
                "o=p",
                "q=r",
                "op",
                "monitor",
                "i=j",
                "k=l",
                "start",
                "m=n",
            ],
            {
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
            },
        )
        self.assert_stderr(
            [self.msg_clone_without_meta, self.msg_op_after_clone]
        )

    def test_meta_after_clone(self):
        self.assert_produce(
            [
                "a=b",
                "c=d",
                "op",
                "monitor",
                "i=j",
                "k=l",
                "start",
                "m=n",
                "clone",
                "o=p",
                "q=r",
                "meta",
                "e=f",
                "g=h",
            ],
            {
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
            },
        )
        self.assert_stderr(
            [self.msg_clone_without_meta, self.msg_meta_after_clone]
        )

    def test_bundle_no_options(self):
        self.assert_produce(
            ["bundle"],
            {
                "bundle": [],
                "meta": {},
                "op": [],
                "options": {},
            },
        )
        self.assert_stderr()

    def test_bundle(self):
        self.assert_produce(
            ["bundle", "b"],
            {
                "bundle": ["b"],
                "meta": {},
                "op": [],
                "options": {},
            },
        )
        self.assert_stderr()

    def test_op_after_bundle(self):
        self.assert_produce(
            ["bundle", "b", "op", "monitor", "a=b", "c=d", "start", "e=f"],
            {
                "bundle": ["b"],
                "meta": {},
                "op": [
                    {"name": "monitor", "a": "b", "c": "d"},
                    {"name": "start", "e": "f"},
                ],
                "options": {},
            },
        )
        self.assert_stderr([self.msg_op_after_bundle])

    def test_meta_after_bundle(self):
        self.assert_produce(
            ["bundle", "b", "meta", "a=b", "c=d"],
            {
                "bundle": ["b"],
                "meta": {"a": "b", "c": "d"},
                "op": [],
                "options": {},
            },
        )
        self.assert_stderr([self.msg_meta_after_bundle])

    def test_multiple_meta(self):
        self.assert_produce(
            [
                "a=b",
                "c=d",
                "meta",
                "e=f",
                "meta",
                "g=h",
                "clone",
                "meta",
                "m=n",
                "meta",
                "o=p",
            ],
            {
                "options": {"a": "b", "c": "d"},
                "meta": {"e": "f", "g": "h", "m": "n", "o": "p"},
                "op": [],
                "clone": {},
            },
        )
        self.assert_stderr([self.msg_meta_after_clone])


class ParseCreateArgsFuture(ParseCreateArgs):
    future = True

    def test_op_after_clone(self):
        self.assert_raises_cmdline(
            ["clone", "op", "monitor", "i=j", "k=l"],
            self.msg_op_after_clone_err,
        )

    def test_only_clone(self):
        self.assert_raises_cmdline(
            ["clone", "a=b", "c=d"], self.msg_clone_without_meta_err
        )

    def test_only_clone_with_custom_id_and_meta(self):
        self.assert_raises_cmdline(
            ["clone", "CustomCloneId", "a=b", "c=d"],
            self.msg_clone_without_meta_err,
        )

    def test_only_clone_with_custom_id_and_meta_correct(self):
        self.assert_produce(
            ["clone", "CustomCloneId", "meta", "a=b", "c=d"],
            {
                "meta": {},
                "options": {},
                "op": [],
                "clone": {"a": "b", "c": "d"},
                "clone_id": "CustomCloneId",
            },
        )

    def test_only_promotable(self):
        self.assert_raises_cmdline(
            ["promotable", "a=b", "c=d"], self.msg_promotable_without_meta_err
        )

    def test_only_promotable_with_custom_id_and_meta(self):
        self.assert_raises_cmdline(
            ["promotable", "CustomCloneId", "a=b", "c=d"],
            self.msg_promotable_without_meta_err,
        )

    def test_only_promotable_with_custom_id_and_meta_correct(self):
        self.assert_produce(
            ["promotable", "CustomCloneId", "meta", "a=b", "c=d"],
            {
                "meta": {},
                "options": {},
                "op": [],
                "promotable": {"a": "b", "c": "d"},
                "clone_id": "CustomCloneId",
            },
        )

    def test_args_op_clone_meta(self):
        self.assert_raises_cmdline(
            [
                "a=b",
                "c=d",
                "meta",
                "e=f",
                "g=h",
                "op",
                "monitor",
                "i=j",
                "k=l",
                "start",
                "m=n",
                "clone",
                "o=p",
                "q=r",
            ],
            self.msg_clone_without_meta_err,
        )

    def test_meta_after_clone(self):
        self.assert_produce(
            [
                "a=b",
                "c=d",
                "op",
                "monitor",
                "i=j",
                "k=l",
                "start",
                "m=n",
                "clone",
                "meta",
                "e=f",
                "g=h",
            ],
            {
                "options": {"a": "b", "c": "d"},
                "op": [
                    {"name": "monitor", "i": "j", "k": "l"},
                    {"name": "start", "m": "n"},
                ],
                "meta": {},
                "clone": {"e": "f", "g": "h"},
            },
        )
        self.assert_stderr()

    def test_op_after_bundle(self):
        self.assert_raises_cmdline(
            ["bundle", "b", "op", "monitor", "a=b", "c=d", "start", "e=f"],
            self.msg_op_after_bundle_err,
        )

    def test_meta_after_bundle(self):
        self.assert_raises_cmdline(
            ["bundle", "b", "meta", "a=b", "c=d"],
            self.msg_meta_after_bundle_err,
        )

    def test_multiple_meta(self):
        self.assert_produce(
            [
                "a=b",
                "c=d",
                "meta",
                "e=f",
                "meta",
                "g=h",
                "clone",
                "meta",
                "m=n",
                "meta",
                "o=p",
            ],
            {
                "options": {"a": "b", "c": "d"},
                "meta": {"e": "f", "g": "h"},
                "op": [],
                "clone": {"m": "n", "o": "p"},
            },
        )
        self.assert_stderr()


class ParseCreateSimple(TestCase):
    def assert_produce(self, arg_list, result):
        self.assertEqual(parse_args.parse_create_simple(arg_list), result)

    def test_without_args(self):
        self.assert_produce(
            [],
            {
                "meta": {},
                "options": {},
                "op": [],
            },
        )

    def test_only_instance_attributes(self):
        self.assert_produce(
            ["a=b", "c=d"],
            {
                "meta": {},
                "options": {
                    "a": "b",
                    "c": "d",
                },
                "op": [],
            },
        )

    def test_only_meta(self):
        self.assert_produce(
            ["meta", "a=b", "c=d"],
            {
                "options": {},
                "op": [],
                "meta": {
                    "a": "b",
                    "c": "d",
                },
            },
        )

    def test_only_operations(self):
        self.assert_produce(
            [
                "op",
                "monitor",
                "a=b",
                "c=d",
                "start",
                "e=f",
            ],
            {
                "meta": {},
                "options": {},
                "op": [
                    {"name": "monitor", "a": "b", "c": "d"},
                    {"name": "start", "e": "f"},
                ],
            },
        )

    def assert_raises_cmdline(self, args):
        self.assertRaises(
            CmdLineInputError, lambda: parse_args.parse_create_simple(args)
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
        self.assert_produce(
            [
                "op",
                "monitor",
                "a=b",
                "c=d",
                "op",
                "start",
                "e=f",
            ],
            {
                "meta": {},
                "options": {},
                "op": [
                    {"name": "monitor", "a": "b", "c": "d"},
                    {"name": "start", "e": "f"},
                ],
            },
        )


class ParseBundleCreateOptions(TestCase):
    # pylint: disable=too-many-public-methods
    def assert_produce(self, arg_list, result):
        self.assertEqual(
            result, parse_args.parse_bundle_create_options(arg_list)
        )

    def assert_raises_cmdline(self, arg_list):
        self.assertRaises(
            CmdLineInputError,
            lambda: parse_args.parse_bundle_create_options(arg_list),
        )

    def test_no_args(self):
        self.assert_produce(
            [],
            {
                "container_type": "",
                "container": {},
                "network": {},
                "port_map": [],
                "storage_map": [],
                "meta": {},
            },
        )

    def test_container_empty(self):
        self.assert_raises_cmdline(["container"])

    def test_container_type(self):
        self.assert_produce(
            ["container", "docker"],
            {
                "container_type": "docker",
                "container": {},
                "network": {},
                "port_map": [],
                "storage_map": [],
                "meta": {},
            },
        )

    def test_container_options(self):
        self.assert_produce(
            ["container", "a=b", "c=d"],
            {
                "container_type": "",
                "container": {"a": "b", "c": "d"},
                "network": {},
                "port_map": [],
                "storage_map": [],
                "meta": {},
            },
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
                "meta": {},
            },
        )

    def test_container_type_must_be_first(self):
        self.assert_raises_cmdline(["container", "a=b", "docker", "c=d"])

    def test_container_missing_value(self):
        self.assert_raises_cmdline(["container", "docker", "a", "c=d"])

    def test_container_missing_key(self):
        self.assert_raises_cmdline(["container", "docker", "=b", "c=d"])

    def test_network(self):
        self.assert_produce(
            ["network", "a=b", "c=d"],
            {
                "container_type": "",
                "container": {},
                "network": {"a": "b", "c": "d"},
                "port_map": [],
                "storage_map": [],
                "meta": {},
            },
        )

    def test_network_empty(self):
        self.assert_raises_cmdline(["network"])

    def test_network_missing_value(self):
        self.assert_raises_cmdline(["network", "a", "c=d"])

    def test_network_missing_key(self):
        self.assert_raises_cmdline(["network", "=b", "c=d"])

    def test_port_map_empty(self):
        self.assert_raises_cmdline(["port-map"])

    def test_one_of_port_map_empty(self):
        self.assert_raises_cmdline(
            ["port-map", "a=b", "port-map", "network", "c=d"]
        )

    def test_port_map_one(self):
        self.assert_produce(
            ["port-map", "a=b", "c=d"],
            {
                "container_type": "",
                "container": {},
                "network": {},
                "port_map": [{"a": "b", "c": "d"}],
                "storage_map": [],
                "meta": {},
            },
        )

    def test_port_map_more(self):
        self.assert_produce(
            ["port-map", "a=b", "c=d", "port-map", "e=f"],
            {
                "container_type": "",
                "container": {},
                "network": {},
                "port_map": [{"a": "b", "c": "d"}, {"e": "f"}],
                "storage_map": [],
                "meta": {},
            },
        )

    def test_port_map_missing_value(self):
        self.assert_raises_cmdline(["port-map", "a", "c=d"])

    def test_port_map_missing_key(self):
        self.assert_raises_cmdline(["port-map", "=b", "c=d"])

    def test_storage_map_empty(self):
        self.assert_raises_cmdline(["storage-map"])

    def test_one_of_storage_map_empty(self):
        self.assert_raises_cmdline(
            ["storage-map", "port-map", "a=b", "storage-map", "c=d"]
        )

    def test_storage_map_one(self):
        self.assert_produce(
            ["storage-map", "a=b", "c=d"],
            {
                "container_type": "",
                "container": {},
                "network": {},
                "port_map": [],
                "storage_map": [{"a": "b", "c": "d"}],
                "meta": {},
            },
        )

    def test_storage_map_more(self):
        self.assert_produce(
            ["storage-map", "a=b", "c=d", "storage-map", "e=f"],
            {
                "container_type": "",
                "container": {},
                "network": {},
                "port_map": [],
                "storage_map": [{"a": "b", "c": "d"}, {"e": "f"}],
                "meta": {},
            },
        )

    def test_storage_map_missing_value(self):
        self.assert_raises_cmdline(["storage-map", "a", "c=d"])

    def test_storage_map_missing_key(self):
        self.assert_raises_cmdline(["storage-map", "=b", "c=d"])

    def test_meta(self):
        self.assert_produce(
            ["meta", "a=b", "c=d"],
            {
                "container_type": "",
                "container": {},
                "network": {},
                "port_map": [],
                "storage_map": [],
                "meta": {"a": "b", "c": "d"},
            },
        )

    def test_meta_empty(self):
        self.assert_raises_cmdline(["meta"])

    def test_meta_missing_value(self):
        self.assert_raises_cmdline(["meta", "a", "c=d"])

    def test_meta_missing_key(self):
        self.assert_raises_cmdline(["meta", "=b", "c=d"])

    def test_all(self):
        self.assert_produce(
            [
                "container",
                "docker",
                "a=b",
                "c=d",
                "network",
                "e=f",
                "g=h",
                "port-map",
                "i=j",
                "k=l",
                "port-map",
                "m=n",
                "o=p",
                "storage-map",
                "q=r",
                "s=t",
                "storage-map",
                "u=v",
                "w=x",
                "meta",
                "y=z",
                "A=B",
            ],
            {
                "container_type": "docker",
                "container": {"a": "b", "c": "d"},
                "network": {"e": "f", "g": "h"},
                "port_map": [{"i": "j", "k": "l"}, {"m": "n", "o": "p"}],
                "storage_map": [{"q": "r", "s": "t"}, {"u": "v", "w": "x"}],
                "meta": {"y": "z", "A": "B"},
            },
        )

    def test_all_mixed(self):
        self.assert_produce(
            [
                "storage-map",
                "q=r",
                "s=t",
                "meta",
                "y=z",
                "port-map",
                "i=j",
                "k=l",
                "network",
                "e=f",
                "container",
                "docker",
                "a=b",
                "storage-map",
                "u=v",
                "w=x",
                "port-map",
                "m=n",
                "o=p",
                "meta",
                "A=B",
                "network",
                "g=h",
                "container",
                "c=d",
            ],
            {
                "container_type": "docker",
                "container": {"a": "b", "c": "d"},
                "network": {"e": "f", "g": "h"},
                "port_map": [{"i": "j", "k": "l"}, {"m": "n", "o": "p"}],
                "storage_map": [{"q": "r", "s": "t"}, {"u": "v", "w": "x"}],
                "meta": {"y": "z", "A": "B"},
            },
        )


class ParseBundleUpdateOptions(TestCase):
    # pylint: disable=too-many-public-methods
    def assert_produce(self, arg_list, result):
        self.assertEqual(
            result, parse_args.parse_bundle_update_options(arg_list)
        )

    def assert_raises_cmdline(self, arg_list):
        self.assertRaises(
            CmdLineInputError,
            lambda: parse_args.parse_bundle_update_options(arg_list),
        )

    def test_no_args(self):
        self.assert_produce(
            [],
            {
                "container": {},
                "network": {},
                "port_map_add": [],
                "port_map_remove": [],
                "storage_map_add": [],
                "storage_map_remove": [],
                "meta": {},
            },
        )

    def test_container_options(self):
        self.assert_produce(
            ["container", "a=b", "c=d"],
            {
                "container": {"a": "b", "c": "d"},
                "network": {},
                "port_map_add": [],
                "port_map_remove": [],
                "storage_map_add": [],
                "storage_map_remove": [],
                "meta": {},
            },
        )

    def test_container_empty(self):
        self.assert_raises_cmdline(["container"])

    def test_container_missing_value(self):
        self.assert_raises_cmdline(["container", "a", "c=d"])

    def test_container_missing_key(self):
        self.assert_raises_cmdline(["container", "=b", "c=d"])

    def test_network(self):
        self.assert_produce(
            ["network", "a=b", "c=d"],
            {
                "container": {},
                "network": {"a": "b", "c": "d"},
                "port_map_add": [],
                "port_map_remove": [],
                "storage_map_add": [],
                "storage_map_remove": [],
                "meta": {},
            },
        )

    def test_network_empty(self):
        self.assert_raises_cmdline(["network"])

    def test_network_missing_value(self):
        self.assert_raises_cmdline(["network", "a", "c=d"])

    def test_network_missing_key(self):
        self.assert_raises_cmdline(["network", "=b", "c=d"])

    def test_port_map_empty(self):
        self.assert_raises_cmdline(["port-map"])

    def test_one_of_port_map_empty(self):
        self.assert_raises_cmdline(
            ["port-map", "a=b", "port-map", "network", "c=d"]
        )

    def test_port_map_missing_params(self):
        self.assert_raises_cmdline(["port-map"])
        self.assert_raises_cmdline(["port-map add"])
        self.assert_raises_cmdline(["port-map remove"])

    def test_port_map_wrong_keyword(self):
        self.assert_raises_cmdline(["port-map", "wrong", "a=b"])

    def test_port_map_missing_value(self):
        self.assert_raises_cmdline(["port-map", "add", "a", "c=d"])

    def test_port_map_missing_key(self):
        self.assert_raises_cmdline(["port-map", "add", "=b", "c=d"])

    def test_port_map_more(self):
        self.assert_produce(
            [
                "port-map",
                "add",
                "a=b",
                "port-map",
                "remove",
                "c",
                "d",
                "port-map",
                "add",
                "e=f",
                "g=h",
                "port-map",
                "remove",
                "i",
            ],
            {
                "container": {},
                "network": {},
                "port_map_add": [
                    {
                        "a": "b",
                    },
                    {
                        "e": "f",
                        "g": "h",
                    },
                ],
                "port_map_remove": ["c", "d", "i"],
                "storage_map_add": [],
                "storage_map_remove": [],
                "meta": {},
            },
        )

    def test_storage_map_empty(self):
        self.assert_raises_cmdline(["storage-map"])

    def test_one_of_storage_map_empty(self):
        self.assert_raises_cmdline(
            ["storage-map", "port-map", "a=b", "storage-map", "c=d"]
        )

    def test_storage_map_missing_params(self):
        self.assert_raises_cmdline(["storage-map"])
        self.assert_raises_cmdline(["storage-map add"])
        self.assert_raises_cmdline(["storage-map remove"])

    def test_storage_map_wrong_keyword(self):
        self.assert_raises_cmdline(["storage-map", "wrong", "a=b"])

    def test_storage_map_missing_value(self):
        self.assert_raises_cmdline(["storage-map", "add", "a", "c=d"])

    def test_storage_map_missing_key(self):
        self.assert_raises_cmdline(["storage-map", "add", "=b", "c=d"])

    def test_storage_map_more(self):
        self.assert_produce(
            [
                "storage-map",
                "add",
                "a=b",
                "storage-map",
                "remove",
                "c",
                "d",
                "storage-map",
                "add",
                "e=f",
                "g=h",
                "storage-map",
                "remove",
                "i",
            ],
            {
                "container": {},
                "network": {},
                "port_map_add": [],
                "port_map_remove": [],
                "storage_map_add": [
                    {
                        "a": "b",
                    },
                    {
                        "e": "f",
                        "g": "h",
                    },
                ],
                "storage_map_remove": ["c", "d", "i"],
                "meta": {},
            },
        )

    def test_meta(self):
        self.assert_produce(
            ["meta", "a=b", "c=d"],
            {
                "container": {},
                "network": {},
                "port_map_add": [],
                "port_map_remove": [],
                "storage_map_add": [],
                "storage_map_remove": [],
                "meta": {"a": "b", "c": "d"},
            },
        )

    def test_meta_empty(self):
        self.assert_raises_cmdline(["meta"])

    def test_meta_missing_value(self):
        self.assert_raises_cmdline(["meta", "a", "c=d"])

    def test_meta_missing_key(self):
        self.assert_raises_cmdline(["meta", "=b", "c=d"])

    def test_all(self):
        self.assert_produce(
            [
                "container",
                "a=b",
                "c=d",
                "network",
                "e=f",
                "g=h",
                "port-map",
                "add",
                "i=j",
                "k=l",
                "port-map",
                "add",
                "m=n",
                "port-map",
                "remove",
                "o",
                "p",
                "port-map",
                "remove",
                "q",
                "storage-map",
                "add",
                "r=s",
                "t=u",
                "storage-map",
                "add",
                "v=w",
                "storage-map",
                "remove",
                "x",
                "y",
                "storage-map",
                "remove",
                "z",
                "meta",
                "A=B",
                "C=D",
            ],
            {
                "container": {"a": "b", "c": "d"},
                "network": {"e": "f", "g": "h"},
                "port_map_add": [
                    {"i": "j", "k": "l"},
                    {"m": "n"},
                ],
                "port_map_remove": ["o", "p", "q"],
                "storage_map_add": [
                    {"r": "s", "t": "u"},
                    {"v": "w"},
                ],
                "storage_map_remove": ["x", "y", "z"],
                "meta": {"A": "B", "C": "D"},
            },
        )

    def test_all_mixed(self):
        self.assert_produce(
            [
                "storage-map",
                "remove",
                "x",
                "y",
                "meta",
                "A=B",
                "port-map",
                "remove",
                "o",
                "p",
                "network",
                "e=f",
                "g=h",
                "storage-map",
                "add",
                "r=s",
                "t=u",
                "port-map",
                "add",
                "i=j",
                "k=l",
                "container",
                "a=b",
                "c=d",
                "meta",
                "C=D",
                "port-map",
                "remove",
                "q",
                "storage-map",
                "remove",
                "z",
                "storage-map",
                "add",
                "v=w",
                "port-map",
                "add",
                "m=n",
            ],
            {
                "container": {"a": "b", "c": "d"},
                "network": {"e": "f", "g": "h"},
                "port_map_add": [
                    {"i": "j", "k": "l"},
                    {"m": "n"},
                ],
                "port_map_remove": ["o", "p", "q"],
                "storage_map_add": [
                    {"r": "s", "t": "u"},
                    {"v": "w"},
                ],
                "storage_map_remove": ["x", "y", "z"],
                "meta": {"A": "B", "C": "D"},
            },
        )


class BuildOperations(TestCase):
    def assert_produce(self, arg_list, result):
        self.assertEqual(result, parse_args.build_operations(arg_list))

    def assert_raises_cmdline(self, arg_list):
        self.assertRaises(
            CmdLineInputError, lambda: parse_args.build_operations(arg_list)
        )

    def test_return_empty_list_on_empty_input(self):
        self.assert_produce([], [])

    def test_return_all_operations_specified_in_the_same_group(self):
        self.assert_produce(
            [["monitor", "interval=10s", "start", "timeout=20s"]],
            [
                ["name=monitor", "interval=10s"],
                ["name=start", "timeout=20s"],
            ],
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
            ],
        )

    def test_refuse_empty_operation(self):
        self.assert_raises_cmdline([[]])

    def test_refuse_operation_without_attribute(self):
        self.assert_raises_cmdline([["monitor"]])

    def test_refuse_operation_without_name(self):
        self.assert_raises_cmdline([["interval=10s"]])
