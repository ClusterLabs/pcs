from unittest import (
    TestCase,
    mock,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.constraint.rule import command as rule_command

from pcs_test.tools.constraints_dto import get_all_constraints
from pcs_test.tools.custom_mock import RuleInEffectEvalMock
from pcs_test.tools.misc import dict_to_modifiers


class TestRemoveColocationConstraint(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["constraint", "cib"])
        self.cib = mock.Mock(spec_set=["remove_elements"])
        self.constraint = mock.Mock(spec_set=["get_config"])
        self.constraint.get_config.return_value = get_all_constraints(
            RuleInEffectEvalMock({})
        )
        self.lib.cib = self.cib
        self.lib.constraint = self.constraint

    def _call_cmd(self, argv, modifiers=None):
        rule_command.remove(self.lib, argv, dict_to_modifiers(modifiers or {}))

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.constraint.get_config.assert_not_called()
        self.cib.remove_elements.assert_not_called()

    def test_duplicate_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["id1", "id2", "id1", "id2"])
        self.assertEqual(
            cm.exception.message, "duplicate arguments: 'id1', 'id2'"
        )
        self.constraint.get_config.assert_not_called()
        self.cib.remove_elements.assert_not_called()

    def test_unsupported_modifier(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["id1", "id2"], {"force": True})
        self.assertEqual(
            cm.exception.message,
            "Specified option '--force' is not supported in this command",
        )
        self.constraint.get_config.assert_not_called()
        self.cib.remove_elements.assert_not_called()

    def test_rule_ids_not_found(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["id1", "id2"])
        self.assertEqual(
            cm.exception.message,
            "Unable to find rule ids: 'id1', 'id2'",
        )
        self.constraint.get_config.assert_called_once_with(evaluate_rules=False)
        self.cib.remove_elements.assert_not_called()

    def test_rule_ids_found(self):
        location_rule_ids = [
            "loc_constr_with_expired_rule-rule",
            "loc_constr_with_not_expired_rule-rule",
            "loc_constr_with_not_expired_rule-rule-1",
        ]
        self._call_cmd(location_rule_ids)
        self.constraint.get_config.assert_called_once_with(evaluate_rules=False)
        self.cib.remove_elements.assert_called_once_with(location_rule_ids)
