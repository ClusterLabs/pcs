from unittest import (
    TestCase,
    mock,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.constraint import command as constraint_command

from pcs_test.tools.constraints_dto import get_all_constraints
from pcs_test.tools.custom_mock import RuleInEffectEvalMock
from pcs_test.tools.misc import dict_to_modifiers


class TestRemoveConstraint(TestCase):
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
        constraint_command.remove(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

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
            self._call_cmd(["id1", "id2", "id1", "id2"], {"force": True})
        self.assertEqual(
            cm.exception.message,
            "Specified option '--force' is not supported in this command",
        )
        self.constraint.get_config.assert_not_called()
        self.cib.remove_elements.assert_not_called()

    def test_not_constraint_or_rule_ids(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["id1", "id2", "location-R7-localhost-INFINITY"])
        self.assertEqual(
            cm.exception.message,
            "Unable to find constraint or rule ids: 'id1', 'id2'",
        )
        self.constraint.get_config.assert_called_once_with(evaluate_rules=False)
        self.cib.remove_elements.assert_not_called()

    def test_constraint_or_rule_ids(self):
        constraint_or_rule_ids = [
            "location-R7-localhost-INFINITY",
            "loc_constr_with_expired_rule-rule",
            "loc_constr_with_not_expired_rule-rule-1",
            "colocation-G1-clone-R6-clone--100",
            "order_set_B2R6-cloneSe",
            "ticket_set_R7B2G2",
        ]
        self._call_cmd(constraint_or_rule_ids)
        self.constraint.get_config.assert_called_once_with(evaluate_rules=False)
        self.cib.remove_elements.assert_called_once_with(constraint_or_rule_ids)
