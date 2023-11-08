from unittest import TestCase

from pcs.common.pacemaker.constraint import (
    CibConstraintsDto,
    get_all_constraints_ids,
    get_all_location_constraints_ids,
    get_all_location_rules_ids,
)

from pcs_test.tools.constraints_dto import get_all_constraints
from pcs_test.tools.custom_mock import RuleInEffectEvalMock


class GetAllConstraintsIds(TestCase):
    def test_constraints_defined(self):
        self.assertEqual(
            get_all_constraints_ids(
                get_all_constraints(RuleInEffectEvalMock({}))
            ),
            {
                "colocation-G1-clone-R6-clone--100",
                "colocation_set_R7G2B2",
                "loc_constr_with_expired_rule",
                "loc_constr_with_not_expired_rule",
                "location-G2-localhost-INFINITY",
                "location-R-localhost-INFINITY",
                "location-R7-another-one--INFINITY",
                "location-R7-localhost-INFINITY",
                "location-R7-non-existing-node--10000",
                "order-G2-B2-Optional",
                "order-R7-G2-mandatory",
                "order_set_B2R6-cloneSe",
                "ticket-custom-ticket1-G1-clone-Promoted",
                "ticket_set_R7B2G2",
            },
        )

    def test_constraints_not_defined(self):
        self.assertEqual(get_all_constraints_ids(CibConstraintsDto()), set())


class GetAllLocationRulesIds(TestCase):
    def test_location_constraints_with_rules(self):
        constraint_dto = get_all_constraints(RuleInEffectEvalMock({}))
        self.assertEqual(
            get_all_location_rules_ids(constraint_dto),
            {
                "loc_constr_with_not_expired_rule-rule-1",
                "loc_constr_with_expired_rule-rule",
                "loc_constr_with_not_expired_rule-rule",
            },
        )

    def test_location_constraints_without_rules(self):
        constraint_dto = get_all_constraints(RuleInEffectEvalMock({}))
        location_constraints_without_rules = CibConstraintsDto(
            location=[
                location_dto
                for location_dto in constraint_dto.location
                if not location_dto.attributes.rules
            ]
        )
        self.assertEqual(
            get_all_location_rules_ids(location_constraints_without_rules),
            set(),
        )


class GetAllLocationIds(TestCase):
    def test_location_constraints_defined(self):
        constraint_dto = get_all_constraints(RuleInEffectEvalMock({}))
        self.assertEqual(
            get_all_location_constraints_ids(constraint_dto),
            {
                "location-G2-localhost-INFINITY",
                "location-R-localhost-INFINITY",
                "location-R7-another-one--INFINITY",
                "location-R7-localhost-INFINITY",
                "location-R7-non-existing-node--10000",
                "loc_constr_with_expired_rule",
                "loc_constr_with_not_expired_rule",
            },
        )

    def test_location_constraints_not_defined(self):
        constraint_dto = get_all_constraints(RuleInEffectEvalMock({}))
        no_location_constraints_dto = CibConstraintsDto(
            colocation=constraint_dto.colocation,
            colocation_set=constraint_dto.colocation_set,
            order=constraint_dto.order,
            order_set=constraint_dto.order_set,
            ticket=constraint_dto.ticket_set,
            ticket_set=constraint_dto.ticket_set,
        )
        self.assertEqual(
            get_all_location_constraints_ids(no_location_constraints_dto),
            set(),
        )
