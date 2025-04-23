from pcs.common.pacemaker.node import CibNodeDto, CibNodeListDto
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
    CibNvsetDto,
)
from pcs.common.pacemaker.rule import CibRuleExpressionDto
from pcs.common.types import CibRuleExpressionType, CibRuleInEffectStatus
from pcs.lib.cib.rule.in_effect import RuleInEffectEval

FIXTURE_NODES_CONFIG_XML = """
    <nodes>
        <node id="1" uname="node1" description="node1 desc" score="100"
            type="member"
        >
            <instance_attributes id="nodes-1" score="50">
                <nvpair id="nodes-1-a" name="a" value="1"/>
                <nvpair id="nodes-1-b" name="b" value="2"/>
                <rule id="nodes-1-rule" score="INFINITY">
                    <date_expression id="nodes-1-rule-de" operation="lt"
                        end="2000-01-01"
                    />
                </rule>
            </instance_attributes>
            <instance_attributes id="nodes-1-2">
                <nvpair id="nodes-1-2-c" name="c" value="3"/>
                <rule id="nodes-1-2-rule" boolean-op="and" score="INFINITY">
                    <date_expression id="nodes-1-2-rule-de" operation="gt"
                        start="2000-01-01"
                    />
                </rule>
            </instance_attributes>
            <utilization id="nodes-1-utilization" score="50">
                <nvpair id="nodes-1-utilization-cpu" name="cpu" value="4"/>
                <nvpair id="nodes-1-utilization-ram" name="ram" value="32"/>
            </utilization>
        </node>
        <node id="2" uname="node2" score="200" type="remote">
            <instance_attributes id="nodes-2">
                <nvpair id="nodes-2-a" name="a" value="1"/>
                <nvpair id="nodes-2-b" name="b" value="2"/>
            </instance_attributes>
            <utilization id="nodes-2-utilization">
                <nvpair id="nodes-2-utilization-cpu" name="cpu" value="8"/>
                <nvpair id="nodes-2-utilization-ram" name="ram" value="64"/>
                <rule id="nodes-2-utilization-rule" boolean-op="and"
                    score="INFINITY"
                >
                    <date_expression id="nodes-2-utilization-rule-de"
                        operation="gt" start="2000-01-01"/>
                </rule>
            </utilization>
        </node>
        <node id="3" uname="node3"/>
    </nodes>
"""


def get_nodes_dto(rule_eval: RuleInEffectEval) -> CibNodeListDto:
    return CibNodeListDto(
        nodes=[
            CibNodeDto(
                id="1",
                uname="node1",
                description="node1 desc",
                score="100",
                type="member",
                instance_attributes=[
                    CibNvsetDto(
                        id="nodes-1",
                        options={"score": "50"},
                        rule=CibRuleExpressionDto(
                            id="nodes-1-rule",
                            type=CibRuleExpressionType.RULE,
                            in_effect=rule_eval.get_rule_status("nodes-1-rule"),
                            options={"score": "INFINITY"},
                            date_spec=None,
                            duration=None,
                            expressions=[
                                CibRuleExpressionDto(
                                    id="nodes-1-rule-de",
                                    type=CibRuleExpressionType.DATE_EXPRESSION,
                                    in_effect=CibRuleInEffectStatus.UNKNOWN,
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
                        ),
                        nvpairs=[
                            CibNvpairDto(id="nodes-1-a", name="a", value="1"),
                            CibNvpairDto(id="nodes-1-b", name="b", value="2"),
                        ],
                    ),
                    CibNvsetDto(
                        id="nodes-1-2",
                        options={},
                        rule=CibRuleExpressionDto(
                            id="nodes-1-2-rule",
                            type=CibRuleExpressionType.RULE,
                            in_effect=rule_eval.get_rule_status(
                                "nodes-1-2-rule"
                            ),
                            options={"boolean-op": "and", "score": "INFINITY"},
                            date_spec=None,
                            duration=None,
                            expressions=[
                                CibRuleExpressionDto(
                                    id="nodes-1-2-rule-de",
                                    type=CibRuleExpressionType.DATE_EXPRESSION,
                                    in_effect=CibRuleInEffectStatus.UNKNOWN,
                                    options={
                                        "operation": "gt",
                                        "start": "2000-01-01",
                                    },
                                    date_spec=None,
                                    duration=None,
                                    expressions=[],
                                    as_string="date gt 2000-01-01",
                                )
                            ],
                            as_string="date gt 2000-01-01",
                        ),
                        nvpairs=[
                            CibNvpairDto(id="nodes-1-2-c", name="c", value="3"),
                        ],
                    ),
                ],
                utilization=[
                    CibNvsetDto(
                        id="nodes-1-utilization",
                        options={"score": "50"},
                        rule=None,
                        nvpairs=[
                            CibNvpairDto(
                                id="nodes-1-utilization-cpu",
                                name="cpu",
                                value="4",
                            ),
                            CibNvpairDto(
                                id="nodes-1-utilization-ram",
                                name="ram",
                                value="32",
                            ),
                        ],
                    )
                ],
            ),
            CibNodeDto(
                id="2",
                uname="node2",
                description=None,
                score="200",
                type="remote",
                instance_attributes=[
                    CibNvsetDto(
                        id="nodes-2",
                        options={},
                        rule=None,
                        nvpairs=[
                            CibNvpairDto(id="nodes-2-a", name="a", value="1"),
                            CibNvpairDto(id="nodes-2-b", name="b", value="2"),
                        ],
                    )
                ],
                utilization=[
                    CibNvsetDto(
                        id="nodes-2-utilization",
                        options={},
                        rule=CibRuleExpressionDto(
                            id="nodes-2-utilization-rule",
                            type=CibRuleExpressionType.RULE,
                            in_effect=rule_eval.get_rule_status(
                                "nodes-2-utilization-rule"
                            ),
                            options={"boolean-op": "and", "score": "INFINITY"},
                            date_spec=None,
                            duration=None,
                            expressions=[
                                CibRuleExpressionDto(
                                    id="nodes-2-utilization-rule-de",
                                    type=CibRuleExpressionType.DATE_EXPRESSION,
                                    in_effect=CibRuleInEffectStatus.UNKNOWN,
                                    options={
                                        "operation": "gt",
                                        "start": "2000-01-01",
                                    },
                                    date_spec=None,
                                    duration=None,
                                    expressions=[],
                                    as_string="date gt 2000-01-01",
                                )
                            ],
                            as_string="date gt 2000-01-01",
                        ),
                        nvpairs=[
                            CibNvpairDto(
                                id="nodes-2-utilization-cpu",
                                name="cpu",
                                value="8",
                            ),
                            CibNvpairDto(
                                id="nodes-2-utilization-ram",
                                name="ram",
                                value="64",
                            ),
                        ],
                    )
                ],
            ),
            CibNodeDto(
                id="3",
                uname="node3",
                description=None,
                score=None,
                type=None,
                instance_attributes=[],
                utilization=[],
            ),
        ]
    )
