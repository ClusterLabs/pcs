from unittest import (
    TestCase,
    mock,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.constraint.location import command as location_command
from pcs.common import (
    const,
    reports,
)

from pcs_test.tools.constraints_dto import get_all_constraints
from pcs_test.tools.custom_mock import RuleInEffectEvalMock
from pcs_test.tools.misc import dict_to_modifiers


class TestRemoveLocationConstraint(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["constraint", "cib"])
        self.cib = mock.Mock(spec_set=["remove_elements"])
        self.constraint = mock.Mock(spec_set=["get_config"])
        self.constraint.get_config.return_value = get_all_constraints(
            RuleInEffectEvalMock({})
        )
        self.lib.cib = self.cib
        self.lib.constraint = self.constraint
        self.patch_warn = mock.patch(
            "pcs.cli.constraint.location.command.deprecation_warning"
        )
        self.mock_warn = self.patch_warn.start()

    def tearDown(self):
        self.patch_warn.stop()

    def _call_cmd(self, argv, modifiers=None):
        location_command.remove(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )
        self.mock_warn.assert_called_once_with(
            "This command is deprecated and will be removed. "
            "Please use 'pcs constraint delete' or 'pcs constraint remove' "
            "instead."
        )

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.constraint.get_config.assert_not_called()
        self.cib.remove_elements.assert_not_called()

    def test_duplicate_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["id1", "id2", "id1", "id2", "id3"])
        self.assertEqual(
            cm.exception.message, "duplicate arguments: 'id1', 'id2'"
        )
        self.constraint.get_config.assert_not_called()
        self.cib.remove_elements.assert_not_called()

    def test_unsupported_modifier(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["id1", "id2", "id1", "id2"], {"force": True})
        self.assertEqual(
            cm.exception.message,
            "Specified option '--force' is not supported in this command",
        )
        self.constraint.get_config.assert_not_called()
        self.cib.remove_elements.assert_not_called()

    def test_location_constraints_ids_not_found(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(
                [
                    "id1",
                    "order-R7-G2-mandatory",
                    "location-R7-localhost-INFINITY",
                ]
            )
        self.assertEqual(
            cm.exception.message,
            (
                "Unable to find location constraints: 'id1', "
                "'order-R7-G2-mandatory'"
            ),
        )
        self.constraint.get_config.assert_called_once_with(evaluate_rules=False)
        self.cib.remove_elements.assert_not_called()

    def test_location_constraint_ids_found(self):
        location_constraint_ids = [
            "location-R7-non-existing-node--10000",
            "location-R7-another-one--INFINITY",
        ]
        self._call_cmd(location_constraint_ids)
        self.constraint.get_config.assert_called_once_with(evaluate_rules=False)
        self.cib.remove_elements.assert_called_once_with(
            location_constraint_ids
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

    def test_resource_id(self):
        self._call_cmd("resource%R1 rule #uname eq node1".split())
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
        self._call_cmd("regexp%R1 rule #uname eq node1".split())
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
            set([reports.codes.FORCE]),
        )
        self.report_processor.set_report_item_preprocessor.assert_called_once()


class RuleAdd(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["constraint_location", "env"])
        self.lib_module = mock.Mock(spec_set=["add_rule_to_constraint"])
        self.lib.constraint_location = self.lib_module
        env = mock.Mock(spec_set=["report_processor"])
        self.lib.env = env
        self.report_processor = mock.Mock(
            spec_set=["set_report_item_preprocessor"]
        )
        self.lib.env.report_processor = self.report_processor

    def _call_cmd(self, argv, modifiers=None):
        location_command.rule_add(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.lib_module.add_rule_to_constraint.assert_not_called()
        self.report_processor.set_report_item_preprocessor.assert_not_called()

    def test_constraint_only(self):
        self._call_cmd("constraint1".split())
        self.lib_module.add_rule_to_constraint.assert_called_once_with(
            "constraint1",
            "",
            {},
            set(),
        )
        self.report_processor.set_report_item_preprocessor.assert_called_once()

    def test_minimal(self):
        self._call_cmd("constraint1 #uname eq node1".split())
        self.lib_module.add_rule_to_constraint.assert_called_once_with(
            "constraint1",
            "#uname eq node1",
            {},
            set(),
        )
        self.report_processor.set_report_item_preprocessor.assert_called_once()

    def test_all_options(self):
        self._call_cmd(
            (
                "constraint1 id=id1 score=7 score-attribute=attr role=r "
                "resource-discovery=rd something=anything #uname eq node1"
            ).split(),
            {"force": True},
        )
        self.lib_module.add_rule_to_constraint.assert_called_once_with(
            "constraint1",
            "resource-discovery=rd something=anything #uname eq node1",
            {"id": "id1", "score": "7", "score-attribute": "attr", "role": "r"},
            set([reports.codes.FORCE]),
        )
        self.report_processor.set_report_item_preprocessor.assert_called_once()
