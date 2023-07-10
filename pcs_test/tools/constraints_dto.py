from pcs.common.const import (
    PcmkAction,
    PcmkRoleType,
)
from pcs.common.pacemaker.constraint import (
    CibConstraintColocationAttributesDto,
    CibConstraintColocationDto,
    CibConstraintColocationSetDto,
    CibConstraintLocationAttributesDto,
    CibConstraintLocationDto,
    CibConstraintOrderAttributesDto,
    CibConstraintOrderDto,
    CibConstraintOrderSetDto,
    CibConstraintsDto,
    CibConstraintTicketAttributesDto,
    CibConstraintTicketDto,
    CibConstraintTicketSetDto,
    CibResourceSetDto,
)
from pcs.common.pacemaker.rule import CibRuleExpressionDto
from pcs.common.pacemaker.types import (
    CibResourceDiscovery,
    CibResourceSetOrderType,
    CibTicketLossPolicy,
)
from pcs.common.types import (
    CibRuleExpressionType,
    CibRuleInEffectStatus,
)
from pcs.lib.cib.rule.in_effect import RuleInEffectEval


def get_all_constraints(
    rule_eval: RuleInEffectEval,
    include_expired: bool = True,
) -> CibConstraintsDto:
    location = [
        CibConstraintLocationDto(
            resource_id="R7",
            resource_pattern=None,
            role=None,
            attributes=CibConstraintLocationAttributesDto(
                constraint_id="location-R7-non-existing-node--10000",
                score="-10000",
                node="non-existing-node",
                rules=[],
                lifetime=[],
                resource_discovery=None,
            ),
        ),
        CibConstraintLocationDto(
            resource_id="R7",
            resource_pattern=None,
            role=None,
            attributes=CibConstraintLocationAttributesDto(
                constraint_id="location-R7-another-one--INFINITY",
                score="-INFINITY",
                node="another-one",
                rules=[],
                lifetime=[],
                resource_discovery=None,
            ),
        ),
        CibConstraintLocationDto(
            resource_id="R7",
            resource_pattern=None,
            role=None,
            attributes=CibConstraintLocationAttributesDto(
                constraint_id="location-R7-localhost-INFINITY",
                score="INFINITY",
                node="localhost",
                rules=[],
                lifetime=[],
                resource_discovery=CibResourceDiscovery.ALWAYS,
            ),
        ),
        CibConstraintLocationDto(
            resource_id="G2",
            resource_pattern=None,
            role=None,
            attributes=CibConstraintLocationAttributesDto(
                constraint_id="location-G2-localhost-INFINITY",
                score="INFINITY",
                node="localhost",
                rules=[],
                lifetime=[],
                resource_discovery=None,
            ),
        ),
        CibConstraintLocationDto(
            resource_id=None,
            resource_pattern="R*",
            role=None,
            attributes=CibConstraintLocationAttributesDto(
                constraint_id="location-R-localhost-INFINITY",
                score="INFINITY",
                node="localhost",
                rules=[],
                lifetime=[],
                resource_discovery=None,
            ),
        ),
    ]
    for loc_const in [
        CibConstraintLocationDto(
            resource_id="B2",
            resource_pattern=None,
            role=None,
            attributes=CibConstraintLocationAttributesDto(
                constraint_id="loc_constr_with_expired_rule",
                score=None,
                node=None,
                rules=[
                    CibRuleExpressionDto(
                        id="loc_constr_with_expired_rule-rule",
                        type=CibRuleExpressionType.RULE,
                        in_effect=rule_eval.get_rule_status(
                            "loc_constr_with_expired_rule-rule"
                        ),
                        options={"score": "500"},
                        date_spec=None,
                        duration=None,
                        expressions=[
                            CibRuleExpressionDto(
                                id="loc_constr_with_expired_rule-rule-expr",
                                type=CibRuleExpressionType.DATE_EXPRESSION,
                                in_effect=rule_eval.get_rule_status(
                                    "loc_constr_with_expired_rule-rule-expr"
                                ),
                                options={
                                    "operation": "lt",
                                    "end": "2000-01-01",
                                },
                                date_spec=None,
                                duration=None,
                                expressions=[],
                                as_string="date lt 2000-01-01",
                            )
                        ],
                        as_string="date lt 2000-01-01",
                    )
                ],
                lifetime=[],
                resource_discovery=None,
            ),
        ),
        CibConstraintLocationDto(
            resource_id="R6-clone",
            resource_pattern=None,
            role=None,
            attributes=CibConstraintLocationAttributesDto(
                constraint_id="loc_constr_with_not_expired_rule",
                score=None,
                node=None,
                rules=[
                    CibRuleExpressionDto(
                        id="loc_constr_with_not_expired_rule-rule",
                        type=CibRuleExpressionType.RULE,
                        in_effect=rule_eval.get_rule_status(
                            "loc_constr_with_not_expired_rule-rule"
                        ),
                        options={
                            "boolean-op": "and",
                            "role": "Unpromoted",
                            "score": "500",
                        },
                        date_spec=None,
                        duration=None,
                        expressions=[
                            CibRuleExpressionDto(
                                id="loc_constr_with_not_expired_rule-rule-expr",
                                type=CibRuleExpressionType.EXPRESSION,
                                in_effect=rule_eval.get_rule_status(
                                    "loc_constr_with_not_expired_rule-rule-expr"
                                ),
                                options={
                                    "operation": "eq",
                                    "attribute": "#uname",
                                    "value": "node1",
                                },
                                date_spec=None,
                                duration=None,
                                expressions=[],
                                as_string="#uname eq node1",
                            ),
                            CibRuleExpressionDto(
                                id="loc_constr_with_not_expired_rule-rule-expr-1",
                                type=CibRuleExpressionType.DATE_EXPRESSION,
                                in_effect=rule_eval.get_rule_status(
                                    "loc_constr_with_not_expired_rule-rule-expr-1"
                                ),
                                options={
                                    "operation": "gt",
                                    "start": "2000-01-01",
                                },
                                date_spec=None,
                                duration=None,
                                expressions=[],
                                as_string="date gt 2000-01-01",
                            ),
                        ],
                        as_string="#uname eq node1 and date gt 2000-01-01",
                    ),
                    CibRuleExpressionDto(
                        id="loc_constr_with_not_expired_rule-rule-1",
                        type=CibRuleExpressionType.RULE,
                        in_effect=rule_eval.get_rule_status(
                            "loc_constr_with_not_expired_rule-rule-1"
                        ),
                        options={
                            "boolean-op": "and",
                            "role": "Promoted",
                            "score-attribute": "test-attr",
                        },
                        date_spec=None,
                        duration=None,
                        expressions=[
                            CibRuleExpressionDto(
                                id="loc_constr_with_not_expired_rule-rule-1-expr",
                                type=CibRuleExpressionType.DATE_EXPRESSION,
                                in_effect=rule_eval.get_rule_status(
                                    "loc_constr_with_not_expired_rule-rule-1-expr"
                                ),
                                options={
                                    "operation": "gt",
                                    "start": "2010-12-31",
                                },
                                date_spec=None,
                                duration=None,
                                expressions=[],
                                as_string="date gt 2010-12-31",
                            ),
                            CibRuleExpressionDto(
                                id="loc_constr_with_not_expired_rule-rule-1-expr-1",
                                type=CibRuleExpressionType.EXPRESSION,
                                in_effect=rule_eval.get_rule_status(
                                    "loc_constr_with_not_expired_rule-rule-1-expr-1"
                                ),
                                options={
                                    "operation": "eq",
                                    "attribute": "#uname",
                                    "value": "node1",
                                },
                                date_spec=None,
                                duration=None,
                                expressions=[],
                                as_string="#uname eq node1",
                            ),
                        ],
                        as_string="date gt 2010-12-31 and #uname eq node1",
                    ),
                ],
                lifetime=[],
                resource_discovery=None,
            ),
        ),
    ]:
        if include_expired or not any(
            rule.in_effect == CibRuleInEffectStatus.EXPIRED
            for rule in loc_const.attributes.rules
        ):
            location.append(loc_const)

    return CibConstraintsDto(
        location=location,
        location_set=[],
        colocation=[
            CibConstraintColocationDto(
                resource_id="G1-clone",
                with_resource_id="R6-clone",
                node_attribute=None,
                resource_role=PcmkRoleType("Promoted"),
                with_resource_role=PcmkRoleType("Stopped"),
                resource_instance=None,
                with_resource_instance=None,
                attributes=CibConstraintColocationAttributesDto(
                    constraint_id="colocation-G1-clone-R6-clone--100",
                    score="-100",
                    influence=None,
                    lifetime=[],
                ),
            )
        ],
        colocation_set=[
            CibConstraintColocationSetDto(
                resource_sets=[
                    CibResourceSetDto(
                        set_id="colocation_set_R7G2B2_set",
                        sequential=None,
                        require_all=None,
                        ordering=None,
                        action=None,
                        role=PcmkRoleType("Started"),
                        score=None,
                        kind=None,
                        resources_ids=["R7", "G2"],
                    ),
                    CibResourceSetDto(
                        set_id="colocation_set_R7G2B2_set-1",
                        sequential=False,
                        require_all=None,
                        ordering=None,
                        action=None,
                        role=None,
                        score=None,
                        kind=None,
                        resources_ids=["B2", "R6-clone"],
                    ),
                ],
                attributes=CibConstraintColocationAttributesDto(
                    constraint_id="colocation_set_R7G2B2",
                    score="-1",
                    influence=None,
                    lifetime=[],
                ),
            )
        ],
        order=[
            CibConstraintOrderDto(
                first_resource_id="R7",
                then_resource_id="G2",
                first_action=PcmkAction("stop"),
                then_action=PcmkAction("stop"),
                first_resource_instance=None,
                then_resource_instance=None,
                attributes=CibConstraintOrderAttributesDto(
                    constraint_id="order-R7-G2-mandatory",
                    symmetrical=False,
                    require_all=False,
                    score="-123",
                    kind=None,
                ),
            ),
            CibConstraintOrderDto(
                first_resource_id="G2",
                then_resource_id="B2",
                first_action=PcmkAction("start"),
                then_action=PcmkAction("start"),
                first_resource_instance=None,
                then_resource_instance=None,
                attributes=CibConstraintOrderAttributesDto(
                    constraint_id="order-G2-B2-Optional",
                    symmetrical=None,
                    require_all=None,
                    score=None,
                    kind=CibResourceSetOrderType.OPTIONAL,
                ),
            ),
        ],
        order_set=[
            CibConstraintOrderSetDto(
                resource_sets=[
                    CibResourceSetDto(
                        set_id="order_set_B2R6-cloneSe_set",
                        sequential=None,
                        require_all=False,
                        ordering=None,
                        action=PcmkAction("stop"),
                        role=None,
                        score=None,
                        kind=None,
                        resources_ids=["B2", "R6-clone"],
                    ),
                    CibResourceSetDto(
                        set_id="order_set_B2R6-cloneSe_set-1",
                        sequential=False,
                        require_all=None,
                        ordering=None,
                        action=PcmkAction("promote"),
                        role=None,
                        score=None,
                        kind=None,
                        resources_ids=["G1-clone"],
                    ),
                ],
                attributes=CibConstraintOrderAttributesDto(
                    constraint_id="order_set_B2R6-cloneSe",
                    symmetrical=None,
                    require_all=None,
                    score=None,
                    kind=CibResourceSetOrderType.OPTIONAL,
                ),
            )
        ],
        ticket=[
            CibConstraintTicketDto(
                resource_id="G1-clone",
                role=PcmkRoleType("Promoted"),
                attributes=CibConstraintTicketAttributesDto(
                    constraint_id="ticket-custom-ticket1-G1-clone-Promoted",
                    ticket="custom-ticket1",
                    loss_policy=CibTicketLossPolicy.DEMOTE,
                ),
            )
        ],
        ticket_set=[
            CibConstraintTicketSetDto(
                resource_sets=[
                    CibResourceSetDto(
                        set_id="ticket_set_R7B2G2_set",
                        sequential=None,
                        require_all=None,
                        ordering=None,
                        action=None,
                        role=PcmkRoleType("Stopped"),
                        score=None,
                        kind=None,
                        resources_ids=["R7", "B2", "G2"],
                    )
                ],
                attributes=CibConstraintTicketAttributesDto(
                    constraint_id="ticket_set_R7B2G2",
                    ticket="ticket2",
                    loss_policy=None,
                ),
            )
        ],
    )
