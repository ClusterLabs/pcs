from unittest import TestCase, mock

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.constraint.location import command as location_command
from pcs.common import const, reports

from pcs_test.tools.misc import dict_to_modifiers


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

    def test_rule_multiple_args_not_supported(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd("R1 rule #uname eq node1".split())
        self.assertEqual(
            cm.exception.message, "missing value of '#uname' option"
        )
        self.lib_module.create_plain_with_rule.assert_not_called()
        self.report_processor.set_report_item_preprocessor.assert_not_called()

    def test_rule_unknown_options_routed_to_constraint(self):
        self._call_cmd(["R1", "rule", "something=anything", "#uname eq node1"])
        self.lib_module.create_plain_with_rule.assert_called_once_with(
            const.RESOURCE_ID_TYPE_PLAIN,
            "R1",
            "#uname eq node1",
            {},
            {"something": "anything"},
            set(),
        )
        self.report_processor.set_report_item_preprocessor.assert_called_once()

    def test_rule_looks_like_option(self):
        # The last argument is always taken as the rule expression, even when it
        # looks like an option ("name=value"). It is passed to the library as
        # the rule, which then validates it.
        self._call_cmd(["R1", "rule", "score=100"])
        self.lib_module.create_plain_with_rule.assert_called_once_with(
            const.RESOURCE_ID_TYPE_PLAIN,
            "R1",
            "score=100",
            {},
            {},
            set(),
        )
        self.report_processor.set_report_item_preprocessor.assert_called_once()

    def test_duplicate_option_different_values(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(
                ["R1", "rule", "score=1", "score=2", "#uname eq node1"]
            )
        self.assertEqual(
            cm.exception.message,
            "duplicate option 'score' with different values '1' and '2'",
        )
        self.lib_module.create_plain_with_rule.assert_not_called()
        self.report_processor.set_report_item_preprocessor.assert_not_called()

    def test_option_key_and_value_with_space(self):
        # Both the key and the value of an option may contain spaces; only the
        # last argument is treated as the rule.
        self._call_cmd(
            [
                "R1",
                "rule",
                "score=100",
                "desc ription=some text",
                "#uname eq node1",
            ]
        )
        self.lib_module.create_plain_with_rule.assert_called_once_with(
            const.RESOURCE_ID_TYPE_PLAIN,
            "R1",
            "#uname eq node1",
            {"score": "100"},
            {"desc ription": "some text"},
            set(),
        )
        self.report_processor.set_report_item_preprocessor.assert_called_once()

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

    def test_all_options(self):
        self._call_cmd(
            [
                "R1",
                "rule",
                "id=id1",
                "constraint-id=id2",
                "score=7",
                "score-attribute=attr",
                "resource-discovery=rd",
                "role=r",
                "#uname eq node1",
            ],
            {"force": True},
        )
        self.lib_module.create_plain_with_rule.assert_called_once_with(
            const.RESOURCE_ID_TYPE_PLAIN,
            "R1",
            "#uname eq node1",
            {"id": "id1", "score": "7", "score-attribute": "attr", "role": "r"},
            {"resource-discovery": "rd", "id": "id2"},
            {reports.codes.FORCE},
        )
        self.report_processor.set_report_item_preprocessor.assert_called_once()
