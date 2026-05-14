from unittest import TestCase

from pcs.cli.constraint.output.order import set_constraint_to_text
from pcs.common.pacemaker.constraint import (
    CibConstraintOrderAttributesDto,
    CibConstraintOrderSetDto,
)
from pcs.common.pacemaker.constraint.set import CibResourceSetDto


class TestSetConstraintToTextResourceOrder(TestCase):
    def test_resource_order_is_preserved(self):
        result = set_constraint_to_text(
            CibConstraintOrderSetDto(
                resource_sets=[
                    CibResourceSetDto(
                        set_id="set1",
                        sequential=None,
                        require_all=None,
                        ordering=None,
                        action=None,
                        role=None,
                        score=None,
                        kind=None,
                        resources_ids=["c_rsc", "a_rsc", "b_rsc"],
                    ),
                ],
                attributes=CibConstraintOrderAttributesDto(
                    constraint_id="order1",
                    symmetrical=None,
                    require_all=None,
                    score=None,
                    kind=None,
                ),
            ),
            with_id=False,
        )
        self.assertEqual(
            result,
            [
                "Set Constraint:",
                "  Resource Set:",
                "    Resources: 'c_rsc', 'a_rsc', 'b_rsc'",
            ],
        )
