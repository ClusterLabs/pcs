from unittest import TestCase, mock

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.constraint.location import command as location_command
from pcs.common import const, reports

from pcs_test.tools.misc import dict_to_modifiers

RULE_ARGV_DEPRECATED = (
    "Specifying a rule as multiple arguments is deprecated and might be removed "
    "in a future release, specify the rule as a single string instead"
)


class CreateWithRule(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["constraint_location", "env"])
        self.lib_module = mock.Mock(spec_set=["create_plain_with_rule"])
        self.lib.constraint_location = self.lib_module
        env = mock.Mock(spec_set=["report_processor"])
        self.lib.env = env
        self.report_processor = mock.Mock(
            spec_set=["set_report_item_preprocessor"]
        )
        self.lib.env.report_processor = self.report_processor

    def _call_cmd(self, argv, modifiers=None):
        location_command.create_with_rule(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.lib_module.create_plain_with_rule.assert_not_called()
        self.report_processor.set_report_item_preprocessor.assert_not_called()

    def test_not_enough_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd("R1 #uname eq node1".split())
        self.assertIsNone(cm.exception.message)
        self.lib_module.create_plain_with_rule.assert_not_called()
        self.report_processor.set_report_item_preprocessor.assert_not_called()

    def test_missing_rule_keyword(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd("R1 score=123 #uname eq node1".split())
        self.assertIsNone(cm.exception.message)
        self.lib_module.create_plain_with_rule.assert_not_called()
        self.report_processor.set_report_item_preprocessor.assert_not_called()

    def test_minimal(self):
        self._call_cmd(["R1", "rule", "#uname eq node1"])
        self.lib_module.create_plain_with_rule.assert_called_once_with(
            const.RESOURCE_ID_TYPE_PLAIN,
            "R1",
            "#uname eq node1",
            {},
            {},
            set(),
        )
        self.report_processor.set_report_item_preprocessor.assert_called_once()

    @mock.patch("pcs.cli.common.parse_args.deprecation_warning")
    def test_minimal_deprecated_form(self, mock_dw):
        self._call_cmd("R1 rule #uname eq node1".split())
        self.lib_module.create_plain_with_rule.assert_called_once_with(
            const.RESOURCE_ID_TYPE_PLAIN,
            "R1",
            "#uname eq node1",
            {},
            {},
            set(),
        )
        self.report_processor.set_report_item_preprocessor.assert_called_once()
        mock_dw.assert_called_once_with(RULE_ARGV_DEPRECATED)

    def test_resource_id(self):
        self._call_cmd(["resource%R1", "rule", "#uname eq node1"])
        self.lib_module.create_plain_with_rule.assert_called_once_with(
            const.RESOURCE_ID_TYPE_PLAIN,
            "R1",
            "#uname eq node1",
            {},
            {},
            set(),
        )
        self.report_processor.set_report_item_preprocessor.assert_called_once()

    def test_resource_pattern(self):
        self._call_cmd(["regexp%R1", "rule", "#uname eq node1"])
        self.lib_module.create_plain_with_rule.assert_called_once_with(
            const.RESOURCE_ID_TYPE_REGEXP,
            "R1",
            "#uname eq node1",
            {},
            {},
            set(),
        )
        self.report_processor.set_report_item_preprocessor.assert_called_once()

    def test_resource_id_type_bad(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd("pattern%R1 rule #uname eq node1".split())
        self.assertEqual(
            cm.exception.message,
            "'pattern' is not an allowed type for 'pattern%R1', use regexp, resource",
        )
        self.lib_module.create_plain_with_rule.assert_not_called()
        self.report_processor.set_report_item_preprocessor.assert_not_called()

    @mock.patch("pcs.cli.common.parse_args.deprecation_warning")
    def test_all_options(self, mock_dw):
        self._call_cmd(
            (
                "R1 rule id=id1 constraint-id=id2 score=7 score-attribute=attr "
                "resource-discovery=rd role=r something=anything #uname eq node1"
            ).split(),
            {"force": True},
        )
        self.lib_module.create_plain_with_rule.assert_called_once_with(
            const.RESOURCE_ID_TYPE_PLAIN,
            "R1",
            "something=anything #uname eq node1",
            {"id": "id1", "score": "7", "score-attribute": "attr", "role": "r"},
            {"resource-discovery": "rd", "id": "id2"},
            {reports.codes.FORCE},
        )
        self.report_processor.set_report_item_preprocessor.assert_called_once()
        mock_dw.assert_called_once_with(RULE_ARGV_DEPRECATED)
