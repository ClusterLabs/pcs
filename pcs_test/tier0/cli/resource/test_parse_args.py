# pylint: disable=too-many-lines
from unittest import (
    TestCase,
    mock,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import InputModifiers
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
        self.assert_produce(
            [],
            parse_args.CloneOptions(clone_id=None, meta_attrs={}),
        )

    def test_clone_id(self):
        self.assert_produce(
            ["CustomCloneId"],
            parse_args.CloneOptions(clone_id="CustomCloneId", meta_attrs={}),
        )

    def test_clone_options(self):
        self.assert_produce(
            ["a=b", "c=d"],
            parse_args.CloneOptions(
                clone_id=None, meta_attrs={"a": "b", "c": "d"}
            ),
            stderr=self.meta_deprecated,
        )

    def test_meta_options(self):
        self.assert_produce(
            ["meta", "a=b", "c=d"],
            parse_args.CloneOptions(
                clone_id=None, meta_attrs={"a": "b", "c": "d"}
            ),
        )

    def test_clone_id_and_clone_meta_options(self):
        self.assert_produce(
            ["CustomCloneId", "a=b", "c=d", "meta", "e=f", "g=h"],
            parse_args.CloneOptions(
                clone_id="CustomCloneId",
                meta_attrs={"a": "b", "c": "d", "e": "f", "g": "h"},
            ),
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
                "duplicate option 'promotable' with different values 'false' "
                "and 'true'"
            ),
            promotable=True,
            stderr=self.meta_deprecated,
        )


class ParseCreateArgsCommonMixin:
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

    def test_no_args(self):
        self.assert_produce(
            [],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=None,
                clone=None,
                promotable=None,
                bundle_id=None,
            ),
        )
        self.assert_stderr()

    def test_only_instance_attributes(self):
        self.assert_produce(
            ["a=b", "c=d"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={"a": "b", "c": "d"},
                    meta_attrs={},
                    operations=[],
                ),
                group=None,
                clone=None,
                promotable=None,
                bundle_id=None,
            ),
        )
        self.assert_stderr()

    def test_only_meta(self):
        self.assert_produce(
            ["meta", "a=b", "c=d"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={"a": "b", "c": "d"},
                    operations=[],
                ),
                group=None,
                clone=None,
                promotable=None,
                bundle_id=None,
            ),
        )
        self.assert_stderr()

    def test_only_clone(self):
        self.assert_produce(
            ["clone"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=None,
                clone=parse_args.CloneOptions(clone_id=None, meta_attrs={}),
                promotable=None,
                bundle_id=None,
            ),
        )
        self.assert_stderr()

    def test_only_clone_with_custom_id(self):
        self.assert_produce(
            ["clone", "CustomCloneId"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=None,
                clone=parse_args.CloneOptions(
                    clone_id="CustomCloneId", meta_attrs={}
                ),
                promotable=None,
                bundle_id=None,
            ),
        )
        self.assert_stderr()

    def test_only_promotable(self):
        self.assert_produce(
            ["promotable"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=None,
                clone=None,
                promotable=parse_args.CloneOptions(
                    clone_id=None, meta_attrs={}
                ),
                bundle_id=None,
            ),
        )
        self.assert_stderr()

    def test_only_promotable_with_custom_id(self):
        self.assert_produce(
            ["promotable", "CustomCloneId"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=None,
                clone=None,
                promotable=parse_args.CloneOptions(
                    clone_id="CustomCloneId", meta_attrs={}
                ),
                bundle_id=None,
            ),
        )
        self.assert_stderr()

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
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[
                        {"name": "monitor", "a": "b", "c": "d"},
                        {"name": "start", "e": "f"},
                    ],
                ),
                group=None,
                clone=None,
                promotable=None,
                bundle_id=None,
            ),
        )
        self.assert_stderr()

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
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[
                        {"name": "monitor", "a": "b", "c": "d"},
                        {"name": "start", "e": "f"},
                    ],
                ),
                group=None,
                clone=None,
                promotable=None,
                bundle_id=None,
            ),
        )
        self.assert_stderr()

    def test_deal_with_empty_operations(self):
        msg = (
            "When using 'op' you must specify an operation name and at least "
            "one option"
        )
        self.assert_raises_cmdline(["op", "monitoring", "a=b", "op"], msg)

    def test_bundle_no_options(self):
        self.assert_raises_cmdline(
            ["bundle"],
            "you have to specify exactly one bundle",
        )

    def test_bundle(self):
        self.assert_produce(
            ["bundle", "b"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=None,
                clone=None,
                promotable=None,
                bundle_id="b",
            ),
        )
        self.assert_stderr()


class ParseCreateArgsOld(ParseCreateArgsCommonMixin, TestCase):
    # pylint: disable=too-many-public-methods
    # to keep the order of tests, so that the order can be kept once dropping
    # the old parsing function and merging the test classes back together
    # pylint: disable=useless-parent-delegation
    msg_clone_without_meta = (
        "Deprecation Warning: Configuring clone meta attributes without "
        "specifying the 'meta' keyword after the 'clone' keyword is deprecated "
        "and will be removed in a future release. Specify --future to switch "
        "to the future behavior."
    )
    msg_promotable_without_meta = (
        "Deprecation Warning: Configuring promotable meta attributes without "
        "specifying the 'meta' keyword after the 'promotable' keyword is deprecated "
        "and will be removed in a future release. Specify --future to switch "
        "to the future behavior."
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
    msg_meta_after_bundle = (
        "Deprecation Warning: Specifying 'meta' after 'bundle' now defines "
        "meta options for the base resource. In future, this will be removed "
        "and meta options will have to be specified before 'bundle'. Specify "
        "--future to switch to the future behavior."
    )
    msg_op_after_bundle = (
        "Deprecation Warning: Specifying 'op' after 'bundle' now defines "
        "operations for the base resource. In future, this will be removed and "
        "operations will have to be specified before 'bundle'. Specify "
        "--future to switch to the future behavior."
    )

    def assert_produce(self, arg_list, result, modifiers=None):
        self.assertEqual(
            parse_args.parse_create_old(
                arg_list, InputModifiers(modifiers or {})
            ),
            result,
        )

    def assert_raises_cmdline(self, arg_list, msg="", modifiers=None):
        with self.assertRaises(CmdLineInputError) as cm:
            parse_args.parse_create_old(
                arg_list, InputModifiers(modifiers or {})
            )
        exception = cm.exception
        self.assertEqual(msg, exception.message)

    def test_no_args(self):
        super().test_no_args()

    def test_only_instance_attributes(self):
        super().test_only_instance_attributes()

    def test_only_meta(self):
        super().test_only_meta()

    def test_group_and_id(self):
        self.assert_produce(
            [],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=parse_args.GroupOptions(
                    group_id="G1", after_resource=None, before_resource=None
                ),
                clone=None,
                promotable=None,
                bundle_id=None,
            ),
            {"--group": "G1"},
        )

    def test_group_after_and_id(self):
        self.assert_produce(
            [],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=parse_args.GroupOptions(
                    group_id="G1", after_resource="R1", before_resource=None
                ),
                clone=None,
                promotable=None,
                bundle_id=None,
            ),
            {"--group": "G1", "--after": "R1"},
        )

    def test_group_before_and_id(self):
        self.assert_produce(
            [],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=parse_args.GroupOptions(
                    group_id="G1", after_resource=None, before_resource="R2"
                ),
                clone=None,
                promotable=None,
                bundle_id=None,
            ),
            {"--group": "G1", "--before": "R2"},
        )

    def test_group_after_and_before(self):
        self.assert_produce(
            [],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=parse_args.GroupOptions(
                    group_id="G1", after_resource="R1", before_resource="R2"
                ),
                clone=None,
                promotable=None,
                bundle_id=None,
            ),
            {"--group": "G1", "--after": "R1", "--before": "R2"},
        )

    def test_after_without_group(self):
        self.assert_raises_cmdline(
            [], "you cannot use --after without --group", {"--after": "R2"}
        )

    def test_before_without_group(self):
        self.assert_raises_cmdline(
            [], "you cannot use --before without --group", {"--before": "R2"}
        )

    def test_only_clone(self):
        super().test_only_clone()

    def test_only_clone_with_options(self):
        self.assert_produce(
            ["clone", "a=b", "c=d"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=None,
                clone=parse_args.CloneOptions(
                    clone_id=None, meta_attrs={"a": "b", "c": "d"}
                ),
                promotable=None,
                bundle_id=None,
            ),
        )
        self.assert_stderr([self.msg_clone_without_meta])

    def test_only_clone_with_custom_id(self):
        super().test_only_clone_with_custom_id()

    def test_only_clone_with_custom_id_and_meta(self):
        self.assert_produce(
            ["clone", "CustomCloneId", "a=b", "c=d"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=None,
                clone=parse_args.CloneOptions(
                    clone_id="CustomCloneId", meta_attrs={"a": "b", "c": "d"}
                ),
                promotable=None,
                bundle_id=None,
            ),
        )
        self.assert_stderr([self.msg_clone_without_meta])

    def test_only_clone_with_custom_id_and_meta_new(self):
        self.assert_produce(
            ["clone", "CustomCloneId", "meta", "a=b", "c=d"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={"a": "b", "c": "d"},
                    operations=[],
                ),
                group=None,
                clone=parse_args.CloneOptions(
                    clone_id="CustomCloneId", meta_attrs={}
                ),
                promotable=None,
                bundle_id=None,
            ),
        )

    def test_only_promotable(self):
        super().test_only_promotable()

    def test_only_promotable_with_options(self):
        self.assert_produce(
            ["promotable", "a=b", "c=d"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=None,
                clone=None,
                promotable=parse_args.CloneOptions(
                    clone_id=None, meta_attrs={"a": "b", "c": "d"}
                ),
                bundle_id=None,
            ),
        )
        self.assert_stderr([self.msg_promotable_without_meta])

    def test_only_promotable_with_custom_id(self):
        super().test_only_promotable_with_custom_id()

    def test_only_promotable_with_custom_id_and_meta(self):
        self.assert_produce(
            ["promotable", "CustomCloneId", "a=b", "c=d"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=None,
                clone=None,
                promotable=parse_args.CloneOptions(
                    clone_id="CustomCloneId", meta_attrs={"a": "b", "c": "d"}
                ),
                bundle_id=None,
            ),
        )
        self.assert_stderr([self.msg_promotable_without_meta])

    def test_only_promotable_with_custom_id_and_meta_new(self):
        self.assert_produce(
            ["promotable", "CustomCloneId", "meta", "a=b", "c=d"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={"a": "b", "c": "d"},
                    operations=[],
                ),
                group=None,
                clone=None,
                promotable=parse_args.CloneOptions(
                    clone_id="CustomCloneId", meta_attrs={}
                ),
                bundle_id=None,
            ),
        )

    def test_only_operations(self):
        super().test_only_operations()

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
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={"a": "b", "c": "d"},
                    meta_attrs={"e": "f", "g": "h"},
                    operations=[
                        {"name": "monitor", "i": "j", "k": "l"},
                        {"name": "start", "m": "n"},
                    ],
                ),
                group=None,
                clone=parse_args.CloneOptions(
                    clone_id=None, meta_attrs={"o": "p", "q": "r"}
                ),
                promotable=None,
                bundle_id=None,
            ),
        )
        self.assert_stderr([self.msg_clone_without_meta])

    def test_raises_when_operation_name_does_not_follow_op_keyword(self):
        super().test_raises_when_operation_name_does_not_follow_op_keyword()

    def test_raises_when_operation_have_no_option(self):
        super().test_raises_when_operation_have_no_option()

    def test_allow_to_repeat_op(self):
        super().test_allow_to_repeat_op()

    def test_deal_with_empty_operations(self):
        super().test_deal_with_empty_operations()

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
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={"a": "b", "c": "d"},
                    meta_attrs={"e": "f", "g": "h"},
                    operations=[
                        {"name": "monitor", "i": "j", "k": "l"},
                        {"name": "start", "m": "n"},
                    ],
                ),
                group=None,
                clone=parse_args.CloneOptions(
                    clone_id=None, meta_attrs={"o": "p", "q": "r"}
                ),
                promotable=None,
                bundle_id=None,
            ),
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
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={"a": "b", "c": "d"},
                    meta_attrs={"e": "f", "g": "h"},
                    operations=[
                        {"name": "monitor", "i": "j", "k": "l"},
                        {"name": "start", "m": "n"},
                    ],
                ),
                group=None,
                clone=parse_args.CloneOptions(
                    clone_id=None, meta_attrs={"o": "p", "q": "r"}
                ),
                promotable=None,
                bundle_id=None,
            ),
        )
        self.assert_stderr(
            [self.msg_clone_without_meta, self.msg_meta_after_clone]
        )

    def test_bundle_no_options(self):
        super().test_bundle_no_options()

    def test_bundle(self):
        super().test_bundle()

    def test_op_after_bundle(self):
        self.assert_produce(
            ["bundle", "b", "op", "monitor", "a=b", "c=d", "start", "e=f"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[
                        {"name": "monitor", "a": "b", "c": "d"},
                        {"name": "start", "e": "f"},
                    ],
                ),
                group=None,
                clone=None,
                promotable=None,
                bundle_id="b",
            ),
        )
        self.assert_stderr([self.msg_op_after_bundle])

    def test_meta_after_bundle(self):
        self.assert_produce(
            ["bundle", "b", "meta", "a=b", "c=d"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={"a": "b", "c": "d"},
                    operations=[],
                ),
                group=None,
                clone=None,
                promotable=None,
                bundle_id="b",
            ),
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
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={"a": "b", "c": "d"},
                    meta_attrs={"e": "f", "g": "h", "m": "n", "o": "p"},
                    operations=[],
                ),
                group=None,
                clone=parse_args.CloneOptions(clone_id=None, meta_attrs={}),
                promotable=None,
                bundle_id=None,
            ),
        )
        self.assert_stderr([self.msg_meta_after_clone])


class ParseCreateArgsNew(ParseCreateArgsCommonMixin, TestCase):
    # pylint: disable=too-many-public-methods
    # to keep the order of tests, so that the order can be kept once dropping
    # the old parsing function and merging the test classes back together
    # pylint: disable=useless-parent-delegation
    msg_clone_without_meta_err = (
        "Specifying instance attributes for a clone is not supported. Use "
        "'meta' after 'clone' if you want to specify meta attributes."
    )
    msg_promotable_without_meta_err = (
        "Specifying instance attributes for a promotable is not supported. Use "
        "'meta' after 'promotable' if you want to specify meta attributes."
    )
    msg_op_after_clone_err = (
        "op settings must be defined on the base resource, not the clone"
    )
    msg_meta_after_bundle_err = (
        "meta options must be defined on the base resource, not the bundle"
    )
    msg_op_after_bundle_err = (
        "op settings must be defined on the base resource, not the bundle"
    )
    msg_meta_after_group_err = (
        "meta options must be defined on the base resource, not the group"
    )
    msg_op_after_group_err = (
        "op settings must be defined on the base resource, not the group"
    )

    def assert_produce(self, arg_list, result):
        self.assertEqual(parse_args.parse_create_new(arg_list), result)

    def assert_raises_cmdline(self, args, msg=""):
        with self.assertRaises(CmdLineInputError) as cm:
            parse_args.parse_create_new(args)
        exception = cm.exception
        self.assertEqual(msg, exception.message)

    def test_no_args(self):
        super().test_no_args()

    def test_only_instance_attributes(self):
        super().test_only_instance_attributes()

    def test_only_meta(self):
        super().test_only_meta()

    def test_group_no_options(self):
        self.assert_raises_cmdline(
            ["group"], "You have to specify exactly one group after 'group'"
        )

    def test_group_and_id(self):
        self.assert_produce(
            ["group", "G1"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=parse_args.GroupOptions(
                    group_id="G1", after_resource=None, before_resource=None
                ),
                clone=None,
                promotable=None,
                bundle_id=None,
            ),
        )

    def test_group_multiple_ids(self):
        self.assert_raises_cmdline(
            ["group", "G1", "G2"],
            "You have to specify exactly one group after 'group'",
        )

    def test_group_after(self):
        self.assert_raises_cmdline(
            ["group", "G1", "after"],
            "You have to specify exactly one resource after 'after'",
        )

    def test_group_after_and_id(self):
        self.assert_produce(
            ["group", "G1", "after", "R1"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=parse_args.GroupOptions(
                    group_id="G1", after_resource="R1", before_resource=None
                ),
                clone=None,
                promotable=None,
                bundle_id=None,
            ),
        )

    def test_group_after_multiple_ids(self):
        self.assert_raises_cmdline(
            ["group", "G1", "after", "R1", "R2"],
            "You have to specify exactly one resource after 'after'",
        )

    def test_group_before(self):
        self.assert_raises_cmdline(
            ["group", "G1", "before"],
            "You have to specify exactly one resource after 'before'",
        )

    def test_group_before_and_id(self):
        self.assert_produce(
            ["group", "G1", "before", "R1"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=parse_args.GroupOptions(
                    group_id="G1", after_resource=None, before_resource="R1"
                ),
                clone=None,
                promotable=None,
                bundle_id=None,
            ),
        )

    def test_group_before_multiple_ids(self):
        self.assert_raises_cmdline(
            ["group", "G1", "before", "R1", "R2"],
            "You have to specify exactly one resource after 'before'",
        )

    def test_group_after_and_before(self):
        self.assert_produce(
            ["group", "G1", "before", "R1", "after", "R2"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=parse_args.GroupOptions(
                    group_id="G1", after_resource="R2", before_resource="R1"
                ),
                clone=None,
                promotable=None,
                bundle_id=None,
            ),
        )

    def test_op_after_group(self):
        self.assert_raises_cmdline(
            ["group", "g", "op", "monitor", "a=b", "c=d", "start", "e=f"],
            self.msg_op_after_group_err,
        )

    def test_meta_after_group(self):
        self.assert_raises_cmdline(
            ["group", "g", "meta", "a=b", "c=d"],
            self.msg_meta_after_group_err,
        )

    def test_only_clone(self):
        super().test_only_clone()

    def test_only_clone_with_options(self):
        self.assert_raises_cmdline(
            ["clone", "a=b", "c=d"], self.msg_clone_without_meta_err
        )

    def test_only_clone_with_custom_id(self):
        super().test_only_clone_with_custom_id()

    def test_only_clone_with_custom_id_and_meta(self):
        self.assert_raises_cmdline(
            ["clone", "CustomCloneId", "a=b", "c=d"],
            self.msg_clone_without_meta_err,
        )

    def test_only_clone_with_custom_id_and_meta_new(self):
        self.assert_produce(
            ["clone", "CustomCloneId", "meta", "a=b", "c=d"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=None,
                clone=parse_args.CloneOptions(
                    clone_id="CustomCloneId", meta_attrs={"a": "b", "c": "d"}
                ),
                promotable=None,
                bundle_id=None,
            ),
        )

    def test_only_promotable(self):
        super().test_only_promotable()

    def test_only_promotable_with_options(self):
        self.assert_raises_cmdline(
            ["promotable", "a=b", "c=d"], self.msg_promotable_without_meta_err
        )

    def test_only_promotable_with_custom_id(self):
        super().test_only_promotable_with_custom_id()

    def test_only_promotable_with_custom_id_and_meta(self):
        self.assert_raises_cmdline(
            ["promotable", "CustomCloneId", "a=b", "c=d"],
            self.msg_promotable_without_meta_err,
        )

    def test_only_promotable_with_custom_id_and_meta_new(self):
        self.assert_produce(
            ["promotable", "CustomCloneId", "meta", "a=b", "c=d"],
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={},
                    meta_attrs={},
                    operations=[],
                ),
                group=None,
                clone=None,
                promotable=parse_args.CloneOptions(
                    clone_id="CustomCloneId", meta_attrs={"a": "b", "c": "d"}
                ),
                bundle_id=None,
            ),
        )

    def test_only_operations(self):
        super().test_only_operations()

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

    def test_raises_when_operation_name_does_not_follow_op_keyword(self):
        super().test_raises_when_operation_name_does_not_follow_op_keyword()

    def test_raises_when_operation_have_no_option(self):
        super().test_raises_when_operation_have_no_option()

    def test_allow_to_repeat_op(self):
        super().test_allow_to_repeat_op()

    def test_deal_with_empty_operations(self):
        super().test_deal_with_empty_operations()

    def test_op_after_clone(self):
        self.assert_raises_cmdline(
            ["clone", "op", "monitor", "i=j", "k=l"],
            self.msg_op_after_clone_err,
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
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={"a": "b", "c": "d"},
                    meta_attrs={},
                    operations=[
                        {"name": "monitor", "i": "j", "k": "l"},
                        {"name": "start", "m": "n"},
                    ],
                ),
                group=None,
                clone=parse_args.CloneOptions(
                    clone_id=None, meta_attrs={"e": "f", "g": "h"}
                ),
                promotable=None,
                bundle_id=None,
            ),
        )
        self.assert_stderr()

    def test_bundle_no_options(self):
        super().test_bundle_no_options()

    def test_bundle(self):
        super().test_bundle()

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
            parse_args.ComplexResourceOptions(
                primitive=parse_args.PrimitiveOptions(
                    instance_attrs={"a": "b", "c": "d"},
                    meta_attrs={"e": "f", "g": "h"},
                    operations=[],
                ),
                group=None,
                clone=parse_args.CloneOptions(
                    clone_id=None, meta_attrs={"m": "n", "o": "p"}
                ),
                promotable=None,
                bundle_id=None,
            ),
        )
        self.assert_stderr()


class ParsePrimitive(TestCase):
    def assert_produce(self, arg_list, result):
        self.assertEqual(parse_args.parse_primitive(arg_list), result)

    def test_without_args(self):
        self.assert_produce(
            [],
            parse_args.PrimitiveOptions(
                instance_attrs={},
                meta_attrs={},
                operations=[],
            ),
        )

    def test_only_instance_attributes(self):
        self.assert_produce(
            ["a=b", "c=d"],
            parse_args.PrimitiveOptions(
                instance_attrs={"a": "b", "c": "d"},
                meta_attrs={},
                operations=[],
            ),
        )

    def test_only_meta(self):
        self.assert_produce(
            ["meta", "a=b", "c=d"],
            parse_args.PrimitiveOptions(
                instance_attrs={},
                meta_attrs={"a": "b", "c": "d"},
                operations=[],
            ),
        )

    def test_only_operations(self):
        self.assert_produce(
            ["op", "monitor", "a=b", "c=d", "start", "e=f"],
            parse_args.PrimitiveOptions(
                instance_attrs={},
                meta_attrs={},
                operations=[
                    {"name": "monitor", "a": "b", "c": "d"},
                    {"name": "start", "e": "f"},
                ],
            ),
        )

    def assert_raises_cmdline(self, args):
        self.assertRaises(
            CmdLineInputError, lambda: parse_args.parse_primitive(args)
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
            parse_args.PrimitiveOptions(
                instance_attrs={},
                meta_attrs={},
                operations=[
                    {"name": "monitor", "a": "b", "c": "d"},
                    {"name": "start", "e": "f"},
                ],
            ),
        )


class ParseBundleCreateAndResetMixin:
    # pylint: disable=too-many-public-methods
    def assert_produce(self, arg_list, result):
        self.assertEqual(result, self.parse_fn(arg_list))

    def assert_raises_cmdline(self, arg_list, msg=""):
        with self.assertRaises(CmdLineInputError) as cm:
            self.parse_fn(arg_list)
        exception = cm.exception
        self.assertEqual(msg, exception.message)

    def test_no_args(self):
        self.assert_produce(
            [],
            parse_args.BundleCreateOptions(
                container_type="",
                container={},
                network={},
                port_map=[],
                storage_map=[],
                meta_attrs={},
            ),
        )

    def test_container_empty(self):
        self.assert_raises_cmdline(
            ["container"], "No container options specified"
        )

    def test_container_type(self):
        self.assert_produce(
            ["container", "docker"],
            parse_args.BundleCreateOptions(
                container_type="docker",
                container={},
                network={},
                port_map=[],
                storage_map=[],
                meta_attrs={},
            ),
        )

    def test_container_options(self):
        self.assert_produce(
            ["container", "a=b", "c=d"],
            parse_args.BundleCreateOptions(
                container_type="",
                container={"a": "b", "c": "d"},
                network={},
                port_map=[],
                storage_map=[],
                meta_attrs={},
            ),
        )

    def test_container_type_and_options(self):
        self.assert_produce(
            ["container", "docker", "a=b", "c=d"],
            parse_args.BundleCreateOptions(
                container_type="docker",
                container={"a": "b", "c": "d"},
                network={},
                port_map=[],
                storage_map=[],
                meta_attrs={},
            ),
        )

    def test_container_type_must_be_first(self):
        self.assert_raises_cmdline(
            ["container", "a=b", "docker", "c=d"],
            "missing value of 'docker' option",
        )

    def test_container_missing_value(self):
        self.assert_raises_cmdline(
            ["container", "docker", "a", "c=d"], "missing value of 'a' option"
        )

    def test_container_missing_key(self):
        self.assert_raises_cmdline(
            ["container", "docker", "=b", "c=d"], "missing key in '=b' option"
        )

    def test_network(self):
        self.assert_produce(
            ["network", "a=b", "c=d"],
            parse_args.BundleCreateOptions(
                container_type="",
                container={},
                network={"a": "b", "c": "d"},
                port_map=[],
                storage_map=[],
                meta_attrs={},
            ),
        )

    def test_network_empty(self):
        self.assert_raises_cmdline(["network"], "No network options specified")

    def test_network_missing_value(self):
        self.assert_raises_cmdline(
            ["network", "a", "c=d"], "missing value of 'a' option"
        )

    def test_network_missing_key(self):
        self.assert_raises_cmdline(
            ["network", "=b", "c=d"], "missing key in '=b' option"
        )

    def test_port_map_empty(self):
        self.assert_raises_cmdline(
            ["port-map"], "No port-map options specified"
        )

    def test_one_of_port_map_empty(self):
        self.assert_raises_cmdline(
            ["port-map", "a=b", "port-map", "network", "c=d"],
            "No port-map options specified",
        )

    def test_port_map_one(self):
        self.assert_produce(
            ["port-map", "a=b", "c=d"],
            parse_args.BundleCreateOptions(
                container_type="",
                container={},
                network={},
                port_map=[{"a": "b", "c": "d"}],
                storage_map=[],
                meta_attrs={},
            ),
        )

    def test_port_map_more(self):
        self.assert_produce(
            ["port-map", "a=b", "c=d", "port-map", "e=f"],
            parse_args.BundleCreateOptions(
                container_type="",
                container={},
                network={},
                port_map=[{"a": "b", "c": "d"}, {"e": "f"}],
                storage_map=[],
                meta_attrs={},
            ),
        )

    def test_port_map_missing_value(self):
        self.assert_raises_cmdline(
            ["port-map", "a", "c=d"], "missing value of 'a' option"
        )

    def test_port_map_missing_key(self):
        self.assert_raises_cmdline(
            ["port-map", "=b", "c=d"], "missing key in '=b' option"
        )

    def test_storage_map_empty(self):
        self.assert_raises_cmdline(
            ["storage-map"], "No storage-map options specified"
        )

    def test_one_of_storage_map_empty(self):
        self.assert_raises_cmdline(
            ["storage-map", "port-map", "a=b", "storage-map", "c=d"],
            "No storage-map options specified",
        )

    def test_storage_map_one(self):
        self.assert_produce(
            ["storage-map", "a=b", "c=d"],
            parse_args.BundleCreateOptions(
                container_type="",
                container={},
                network={},
                port_map=[],
                storage_map=[{"a": "b", "c": "d"}],
                meta_attrs={},
            ),
        )

    def test_storage_map_more(self):
        self.assert_produce(
            ["storage-map", "a=b", "c=d", "storage-map", "e=f"],
            parse_args.BundleCreateOptions(
                container_type="",
                container={},
                network={},
                port_map=[],
                storage_map=[{"a": "b", "c": "d"}, {"e": "f"}],
                meta_attrs={},
            ),
        )

    def test_storage_map_missing_value(self):
        self.assert_raises_cmdline(
            ["storage-map", "a", "c=d"], "missing value of 'a' option"
        )

    def test_storage_map_missing_key(self):
        self.assert_raises_cmdline(
            ["storage-map", "=b", "c=d"], "missing key in '=b' option"
        )

    def test_meta(self):
        self.assert_produce(
            ["meta", "a=b", "c=d"],
            parse_args.BundleCreateOptions(
                container_type="",
                container={},
                network={},
                port_map=[],
                storage_map=[],
                meta_attrs={"a": "b", "c": "d"},
            ),
        )

    def test_meta_empty(self):
        self.assert_raises_cmdline(["meta"], "No meta options specified")

    def test_meta_missing_value(self):
        self.assert_raises_cmdline(
            ["meta", "a", "c=d"], "missing value of 'a' option"
        )

    def test_meta_missing_key(self):
        self.assert_raises_cmdline(
            ["meta", "=b", "c=d"], "missing key in '=b' option"
        )

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
            parse_args.BundleCreateOptions(
                container_type="docker",
                container={"a": "b", "c": "d"},
                network={"e": "f", "g": "h"},
                port_map=[{"i": "j", "k": "l"}, {"m": "n", "o": "p"}],
                storage_map=[{"q": "r", "s": "t"}, {"u": "v", "w": "x"}],
                meta_attrs={"y": "z", "A": "B"},
            ),
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
            parse_args.BundleCreateOptions(
                container_type="docker",
                container={"a": "b", "c": "d"},
                network={"e": "f", "g": "h"},
                port_map=[{"i": "j", "k": "l"}, {"m": "n", "o": "p"}],
                storage_map=[{"q": "r", "s": "t"}, {"u": "v", "w": "x"}],
                meta_attrs={"y": "z", "A": "B"},
            ),
        )


class ParseBundleCreate(ParseBundleCreateAndResetMixin, TestCase):
    parse_fn = staticmethod(parse_args.parse_bundle_create_options)


class ParseBundleReset(ParseBundleCreateAndResetMixin, TestCase):
    parse_fn = staticmethod(parse_args.parse_bundle_reset_options)

    def test_container_type(self):
        self.assert_raises_cmdline(
            ["container", "docker"],
            "missing value of 'docker' option",
        )

    def test_container_type_and_options(self):
        self.assert_raises_cmdline(
            ["container", "docker", "a=b", "c=d"],
            "missing value of 'docker' option",
        )

    def test_container_missing_value(self):
        self.assert_raises_cmdline(
            ["container", "a", "c=d"], "missing value of 'a' option"
        )

    def test_container_missing_key(self):
        self.assert_raises_cmdline(
            ["container", "=b", "c=d"], "missing key in '=b' option"
        )

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
            parse_args.BundleCreateOptions(
                container_type="",
                container={"a": "b", "c": "d"},
                network={"e": "f", "g": "h"},
                port_map=[{"i": "j", "k": "l"}, {"m": "n", "o": "p"}],
                storage_map=[{"q": "r", "s": "t"}, {"u": "v", "w": "x"}],
                meta_attrs={"y": "z", "A": "B"},
            ),
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
            parse_args.BundleCreateOptions(
                container_type="",
                container={"a": "b", "c": "d"},
                network={"e": "f", "g": "h"},
                port_map=[{"i": "j", "k": "l"}, {"m": "n", "o": "p"}],
                storage_map=[{"q": "r", "s": "t"}, {"u": "v", "w": "x"}],
                meta_attrs={"y": "z", "A": "B"},
            ),
        )


class ParseBundleUpdateOptions(TestCase):
    # pylint: disable=too-many-public-methods
    def assert_produce(self, arg_list, result):
        self.assertEqual(
            result, parse_args.parse_bundle_update_options(arg_list)
        )

    def assert_raises_cmdline(self, arg_list, msg=""):
        with self.assertRaises(CmdLineInputError) as cm:
            parse_args.parse_bundle_update_options(arg_list)
        exception = cm.exception
        self.assertEqual(msg, exception.message)

    def test_no_args(self):
        self.assert_produce(
            [],
            parse_args.BundleUpdateOptions(
                container={},
                network={},
                port_map_add=[],
                port_map_remove=[],
                storage_map_add=[],
                storage_map_remove=[],
                meta_attrs={},
            ),
        )

    def test_container_options(self):
        self.assert_produce(
            ["container", "a=b", "c=d"],
            parse_args.BundleUpdateOptions(
                container={"a": "b", "c": "d"},
                network={},
                port_map_add=[],
                port_map_remove=[],
                storage_map_add=[],
                storage_map_remove=[],
                meta_attrs={},
            ),
        )

    def test_container_empty(self):
        self.assert_raises_cmdline(
            ["container"], "No container options specified"
        )

    def test_container_missing_value(self):
        self.assert_raises_cmdline(
            ["container", "a", "c=d"], "missing value of 'a' option"
        )

    def test_container_missing_key(self):
        self.assert_raises_cmdline(
            ["container", "=b", "c=d"], "missing key in '=b' option"
        )

    def test_network(self):
        self.assert_produce(
            ["network", "a=b", "c=d"],
            parse_args.BundleUpdateOptions(
                container={},
                network={"a": "b", "c": "d"},
                port_map_add=[],
                port_map_remove=[],
                storage_map_add=[],
                storage_map_remove=[],
                meta_attrs={},
            ),
        )

    def test_network_empty(self):
        self.assert_raises_cmdline(["network"], "No network options specified")

    def test_network_missing_value(self):
        self.assert_raises_cmdline(
            ["network", "a", "c=d"], "missing value of 'a' option"
        )

    def test_network_missing_key(self):
        self.assert_raises_cmdline(
            ["network", "=b", "c=d"], "missing key in '=b' option"
        )

    def test_port_map_empty(self):
        self.assert_raises_cmdline(
            ["port-map"], "No port-map options specified"
        )

    def test_one_of_port_map_empty(self):
        self.assert_raises_cmdline(
            ["port-map", "a=b", "port-map", "network", "c=d"],
            "No port-map options specified",
        )

    def test_port_map_missing_params(self):
        self.assert_raises_cmdline(
            ["port-map"], "No port-map options specified"
        )
        self.assert_raises_cmdline(["port-map add"], None)
        self.assert_raises_cmdline(["port-map remove"], None)

    def test_port_map_wrong_keyword(self):
        self.assert_raises_cmdline(
            ["port-map", "wrong", "a=b"],
            (
                "When using 'port-map' you must specify either 'add' and "
                "options or either of 'delete' or 'remove' and id(s)"
            ),
        )

    def test_port_map_missing_value(self):
        self.assert_raises_cmdline(
            ["port-map", "add", "a", "c=d"], "missing value of 'a' option"
        )

    def test_port_map_missing_key(self):
        self.assert_raises_cmdline(
            ["port-map", "add", "=b", "c=d"], "missing key in '=b' option"
        )

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
            parse_args.BundleUpdateOptions(
                container={},
                network={},
                port_map_add=[{"a": "b"}, {"e": "f", "g": "h"}],
                port_map_remove=["c", "d", "i"],
                storage_map_add=[],
                storage_map_remove=[],
                meta_attrs={},
            ),
        )

    def test_storage_map_empty(self):
        self.assert_raises_cmdline(
            ["storage-map"], "No storage-map options specified"
        )

    def test_one_of_storage_map_empty(self):
        self.assert_raises_cmdline(
            ["storage-map", "port-map", "a=b", "storage-map", "c=d"],
            "No storage-map options specified",
        )

    def test_storage_map_missing_params(self):
        self.assert_raises_cmdline(
            ["storage-map"], "No storage-map options specified"
        )
        self.assert_raises_cmdline(["storage-map add"], None)
        self.assert_raises_cmdline(["storage-map remove"], None)

    def test_storage_map_wrong_keyword(self):
        self.assert_raises_cmdline(
            ["storage-map", "wrong", "a=b"],
            (
                "When using 'storage-map' you must specify either 'add' and "
                "options or either of 'delete' or 'remove' and id(s)"
            ),
        )

    def test_storage_map_missing_value(self):
        self.assert_raises_cmdline(
            ["storage-map", "add", "a", "c=d"], "missing value of 'a' option"
        )

    def test_storage_map_missing_key(self):
        self.assert_raises_cmdline(
            ["storage-map", "add", "=b", "c=d"], "missing key in '=b' option"
        )

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
            parse_args.BundleUpdateOptions(
                container={},
                network={},
                port_map_add=[],
                port_map_remove=[],
                storage_map_add=[{"a": "b"}, {"e": "f", "g": "h"}],
                storage_map_remove=["c", "d", "i"],
                meta_attrs={},
            ),
        )

    def test_meta(self):
        self.assert_produce(
            ["meta", "a=b", "c=d"],
            parse_args.BundleUpdateOptions(
                container={},
                network={},
                port_map_add=[],
                port_map_remove=[],
                storage_map_add=[],
                storage_map_remove=[],
                meta_attrs={"a": "b", "c": "d"},
            ),
        )

    def test_meta_empty(self):
        self.assert_raises_cmdline(["meta"], "No meta options specified")

    def test_meta_missing_value(self):
        self.assert_raises_cmdline(
            ["meta", "a", "c=d"], "missing value of 'a' option"
        )

    def test_meta_missing_key(self):
        self.assert_raises_cmdline(
            ["meta", "=b", "c=d"], "missing key in '=b' option"
        )

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
            parse_args.BundleUpdateOptions(
                container={"a": "b", "c": "d"},
                network={"e": "f", "g": "h"},
                port_map_add=[{"i": "j", "k": "l"}, {"m": "n"}],
                port_map_remove=["o", "p", "q"],
                storage_map_add=[{"r": "s", "t": "u"}, {"v": "w"}],
                storage_map_remove=["x", "y", "z"],
                meta_attrs={"A": "B", "C": "D"},
            ),
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
            parse_args.BundleUpdateOptions(
                container={"a": "b", "c": "d"},
                network={"e": "f", "g": "h"},
                port_map_add=[{"i": "j", "k": "l"}, {"m": "n"}],
                port_map_remove=["o", "p", "q"],
                storage_map_add=[{"r": "s", "t": "u"}, {"v": "w"}],
                storage_map_remove=["x", "y", "z"],
                meta_attrs={"A": "B", "C": "D"},
            ),
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
