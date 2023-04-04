from textwrap import dedent
from unittest import (
    TestCase,
    mock,
)

from pcs import resource
from pcs.cli.common.errors import CmdLineInputError
from pcs.common.pacemaker.defaults import CibDefaultsDto
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
    CibNvsetDto,
)
from pcs.common.pacemaker.rule import CibRuleExpressionDto
from pcs.common.reports import codes as report_codes
from pcs.common.types import (
    CibRuleExpressionType,
    CibRuleInEffectStatus,
)

from pcs_test.tools.misc import dict_to_modifiers


class DefaultsBaseMixin:
    cli_command_name = ""
    lib_command_name = ""

    def setUp(self):
        # pylint: disable=invalid-name
        self.lib = mock.Mock(spec_set=["cib_options"])
        self.cib_options = mock.Mock(spec_set=[self.lib_command_name])
        self.lib.cib_options = self.cib_options
        self.lib_command = getattr(self.cib_options, self.lib_command_name)
        self.cli_command = getattr(resource, self.cli_command_name)

    def _call_cmd(self, argv, modifiers=None):
        modifiers = modifiers or {}
        self.cli_command(self.lib, argv, dict_to_modifiers(modifiers))


@mock.patch("pcs.resource.print")
class DefaultsConfigMixin(DefaultsBaseMixin):
    empty_dto = CibDefaultsDto(instance_attributes=[], meta_attributes=[])
    dto_list = CibDefaultsDto(
        meta_attributes=[
            CibNvsetDto(
                "my-meta_attributes",
                {},
                CibRuleExpressionDto(
                    "my-meta-rule",
                    CibRuleExpressionType.RULE,
                    CibRuleInEffectStatus.EXPIRED,
                    {"boolean-op": "and", "score": "INFINITY"},
                    None,
                    None,
                    [
                        CibRuleExpressionDto(
                            "my-meta-rule-rsc",
                            CibRuleExpressionType.RSC_EXPRESSION,
                            CibRuleInEffectStatus.UNKNOWN,
                            {
                                "class": "ocf",
                                "provider": "pacemaker",
                                "type": "Dummy",
                            },
                            None,
                            None,
                            [],
                            "resource ocf:pacemaker:Dummy",
                        ),
                    ],
                    "resource ocf:pacemaker:Dummy",
                ),
                [
                    CibNvpairDto("my-id-pair1", "name1", "value1"),
                    CibNvpairDto("my-id-pair2", "name2", "value2"),
                ],
            ),
            CibNvsetDto(
                "meta-plain",
                {"score": "123"},
                None,
                [CibNvpairDto("my-id-pair3", "name 1", "value 1")],
            ),
        ],
        instance_attributes=[
            CibNvsetDto(
                "instance",
                {},
                None,
                [CibNvpairDto("instance-pair", "inst", "ance")],
            ),
        ],
    )

    def test_no_args(self, mock_print):
        self.lib_command.return_value = self.empty_dto
        self._call_cmd([])
        self.lib_command.assert_called_once_with(True)
        mock_print.assert_not_called()

    def test_usage(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["arg"])
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_full(self, mock_print):
        self.lib_command.return_value = self.empty_dto
        self._call_cmd([], {"full": True})
        self.lib_command.assert_called_once_with(True)
        mock_print.assert_not_called()

    def test_no_expire_check(self, mock_print):
        self.lib_command.return_value = self.empty_dto
        self._call_cmd([], {"no-expire-check": True})
        self.lib_command.assert_called_once_with(False)
        mock_print.assert_not_called()

    def test_print(self, mock_print):
        self.lib_command.return_value = self.dto_list
        self._call_cmd([], {"all": True})
        self.lib_command.assert_called_once_with(True)
        mock_print.assert_called_once_with(
            dedent(
                '''\
                Meta Attrs (expired): my-meta_attributes
                  name1=value1
                  name2=value2
                  Rule (expired): boolean-op=and score=INFINITY
                    Expression: resource ocf:pacemaker:Dummy
                Meta Attrs: meta-plain score=123
                  "name 1"="value 1"'''
            )
        )

    def test_print_exclude_expired(self, mock_print):
        self.lib_command.return_value = self.dto_list
        self._call_cmd([], {"all": False})
        self.lib_command.assert_called_once_with(True)
        mock_print.assert_called_once_with(
            dedent(
                '''\
                Meta Attrs: meta-plain score=123
                  "name 1"="value 1"'''
            )
        )

    def test_print_full(self, mock_print):
        self.lib_command.return_value = self.dto_list
        self._call_cmd([], {"all": True, "full": True})
        self.lib_command.assert_called_once_with(True)
        mock_print.assert_called_once_with(
            dedent(
                '''\
                Meta Attrs (expired): my-meta_attributes
                  name1=value1
                  name2=value2
                  Rule (expired): boolean-op=and score=INFINITY (id: my-meta-rule)
                    Expression: resource ocf:pacemaker:Dummy (id: my-meta-rule-rsc)
                Meta Attrs: meta-plain score=123
                  "name 1"="value 1"'''
            )
        )


class RscDefaultsConfig(DefaultsConfigMixin, TestCase):
    cli_command_name = "resource_defaults_config_cmd"
    lib_command_name = "resource_defaults_config"


class OpDefaultsConfig(DefaultsConfigMixin, TestCase):
    cli_command_name = "resource_op_defaults_config_cmd"
    lib_command_name = "operation_defaults_config"


class DefaultsSetCreateMixin(DefaultsBaseMixin):
    def test_no_args(self):
        self._call_cmd([])
        self.lib_command.assert_called_once_with(
            {}, {}, nvset_rule=None, force_flags=set()
        )

    def test_no_values(self):
        self._call_cmd(["meta", "rule"])
        self.lib_command.assert_called_once_with(
            {}, {}, nvset_rule=None, force_flags=set()
        )

    def test_bad_options_or_keyword(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["aaa"])
        self.assertEqual(
            cm.exception.message,
            "missing value of 'aaa' option",
        )
        self.lib_command.assert_not_called()

    def test_bad_values(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["meta", "aaa"])
        self.assertEqual(
            cm.exception.message,
            "missing value of 'aaa' option",
        )
        self.lib_command.assert_not_called()

    def test_options(self):
        self._call_cmd(["id=custom-id", "score=10"])
        self.lib_command.assert_called_once_with(
            {},
            {"id": "custom-id", "score": "10"},
            nvset_rule=None,
            force_flags=set(),
        )

    def test_nvpairs(self):
        self._call_cmd(["meta", "name1=value1", "name2=value2"])
        self.lib_command.assert_called_once_with(
            {"name1": "value1", "name2": "value2"},
            {},
            nvset_rule=None,
            force_flags=set(),
        )

    def test_rule(self):
        self._call_cmd(["rule", "resource", "dummy", "or", "op", "monitor"])
        self.lib_command.assert_called_once_with(
            {},
            {},
            nvset_rule="resource dummy or op monitor",
            force_flags=set(),
        )

    def test_force(self):
        self._call_cmd([], {"force": True})
        self.lib_command.assert_called_once_with(
            {}, {}, nvset_rule=None, force_flags=set([report_codes.FORCE])
        )

    def test_all(self):
        self._call_cmd(
            [
                "id=custom-id",
                "score=10",
                "meta",
                "name1=value1",
                "name2=value2",
                "rule",
                "resource",
                "dummy",
                "or",
                "op",
                "monitor",
            ],
            {"force": True},
        )
        self.lib_command.assert_called_once_with(
            {"name1": "value1", "name2": "value2"},
            {"id": "custom-id", "score": "10"},
            nvset_rule="resource dummy or op monitor",
            force_flags=set([report_codes.FORCE]),
        )


class RscDefaultsSetCreate(DefaultsSetCreateMixin, TestCase):
    cli_command_name = "resource_defaults_set_create_cmd"
    lib_command_name = "resource_defaults_create"


class OpDefaultsSetCreate(DefaultsSetCreateMixin, TestCase):
    cli_command_name = "resource_op_defaults_set_create_cmd"
    lib_command_name = "operation_defaults_create"


class DefaultsSetRemoveMixin(DefaultsBaseMixin):
    def test_no_args(self):
        self._call_cmd([])
        self.lib_command.assert_called_once_with([])

    def test_some_args(self):
        self._call_cmd(["set1", "set2"])
        self.lib_command.assert_called_once_with(["set1", "set2"])


class RscDefaultsSetRemove(DefaultsSetRemoveMixin, TestCase):
    cli_command_name = "resource_defaults_set_remove_cmd"
    lib_command_name = "resource_defaults_remove"


class OpDefaultsSetRemove(DefaultsSetRemoveMixin, TestCase):
    cli_command_name = "resource_op_defaults_set_remove_cmd"
    lib_command_name = "operation_defaults_remove"


class DefaultsSetUpdateMixin(DefaultsBaseMixin):
    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()

    def test_no_meta(self):
        self._call_cmd(["nvset-id"])
        self.lib_command.assert_called_once_with("nvset-id", {})

    def test_no_meta_values(self):
        self._call_cmd(["nvset-id", "meta"])
        self.lib_command.assert_called_once_with("nvset-id", {})

    def test_meta_values(self):
        self._call_cmd(["nvset-id", "meta", "a=b", "c=d"])
        self.lib_command.assert_called_once_with(
            "nvset-id", {"a": "b", "c": "d"}
        )


class RscDefaultsSetUpdate(DefaultsSetUpdateMixin, TestCase):
    cli_command_name = "resource_defaults_set_update_cmd"
    lib_command_name = "resource_defaults_update"


class OpDefaultsSetUpdate(DefaultsSetUpdateMixin, TestCase):
    cli_command_name = "resource_op_defaults_set_update_cmd"
    lib_command_name = "operation_defaults_update"


class DefaultsUpdateMixin(DefaultsBaseMixin):
    def test_no_args(self):
        self._call_cmd([])
        self.lib_command.assert_called_once_with(None, {})

    def test_args(self):
        self._call_cmd(["a=b", "c="])
        self.lib_command.assert_called_once_with(None, {"a": "b", "c": ""})


class RscDefaultsUpdate(DefaultsUpdateMixin, TestCase):
    cli_command_name = "resource_defaults_legacy_cmd"
    lib_command_name = "resource_defaults_update"


class OpDefaultsUpdate(DefaultsUpdateMixin, TestCase):
    cli_command_name = "resource_op_defaults_legacy_cmd"
    lib_command_name = "operation_defaults_update"
