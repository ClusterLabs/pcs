from unittest import TestCase

from pcs.cli.constraint.output import filter_constraints_by_rule_expired_status

from pcs_test.tools.constraints_dto import get_all_constraints
from pcs_test.tools.custom_mock import RuleInEffectEvalMock


class FilterConstraintsByRuleExpiredStatus(TestCase):
    def setUp(self):
        self.constraint_dtos_with_expired = get_all_constraints(
            RuleInEffectEvalMock({}), include_expired=True
        )
        self.constraint_dtos_without_expired = get_all_constraints(
            RuleInEffectEvalMock({}), include_expired=False
        )

    def test_include_expired(self):
        self.assertEqual(
            filter_constraints_by_rule_expired_status(
                self.constraint_dtos_with_expired, include_expired=True
            ),
            self.constraint_dtos_with_expired,
        )

    def test_do_not_include_expired(self):
        self.assertEqual(
            filter_constraints_by_rule_expired_status(
                self.constraint_dtos_with_expired, include_expired=False
            ),
            self.constraint_dtos_without_expired,
        )
