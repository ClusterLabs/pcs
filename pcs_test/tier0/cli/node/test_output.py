from textwrap import dedent
from unittest import TestCase

from pcs.cli.node import output as node_output
from pcs.common.pacemaker.node import CibNodeDto, CibNodeListDto
from pcs.common.pacemaker.nvset import CibNvpairDto, CibNvsetDto

from pcs_test.tools.custom_mock import RuleInEffectEvalMock
from pcs_test.tools.nodes_dto import get_nodes_dto

FIXTURE_NODE_CONFIG = get_nodes_dto(RuleInEffectEvalMock({}))


class NodeToLinesCmdBaseMixin:
    def assert_lines(self, config, output):
        self.assertEqual(
            "\n".join(self._call_func(config)) + "\n",
            output,
        )

    def test_nodes_without_nvpairs(self):
        config = CibNodeListDto(nodes=FIXTURE_NODE_CONFIG.nodes[2:2])
        output = "\n"
        self.assert_lines(config, output)


class NodeAttributeToLines(NodeToLinesCmdBaseMixin, TestCase):
    def _call_func(self, config):
        return node_output.config_dto_to_attribute_lines(config)

    def test_nodes_attributes_to_lines(self):
        config = FIXTURE_NODE_CONFIG
        output = dedent(
            """\
            Node: node1
              Description: node1 desc
              Attributes: nodes-1 score=50
                a=1
                b=2
                Rule: score=INFINITY
                  Expression: date lt 2000-01-01
            Node: node2
              Attributes: nodes-2
                a=1
                b=2
            """
        )
        self.assert_lines(config, output)


class NodeUtilizationToLines(NodeToLinesCmdBaseMixin, TestCase):
    def _call_func(self, config):
        return node_output.config_dto_to_utilization_lines(config)

    def test_nodes_utilization_to_lines(self):
        config = FIXTURE_NODE_CONFIG
        output = dedent(
            """\
            Node: node1
              Description: node1 desc
              Utilization: nodes-1-utilization score=50
                cpu=4
                ram=32
            Node: node2
              Utilization: nodes-2-utilization
                cpu=8
                ram=64
                Rule: boolean-op=and score=INFINITY
                  Expression: date gt 2000-01-01
            """
        )
        self.assert_lines(config, output)


class ConfigDtoToAttributeCmd(NodeToLinesCmdBaseMixin, TestCase):
    def _call_func(self, config):
        return node_output.config_dto_to_attribute_cmd(config)

    def test_config_dto_to_attribute_cmd(self):
        config = FIXTURE_NODE_CONFIG
        output = dedent(
            """\
            pcs -- node attribute node1 a=1 b=2
            pcs -- node attribute node2 a=1 b=2
            """
        )
        self.assert_lines(config, output)


class ConfigDtoToUtilizationCmd(NodeToLinesCmdBaseMixin, TestCase):
    def _call_func(self, config):
        return node_output.config_dto_to_utilization_cmd(config)

    def test_config_dto_to_utilization_cmd(self):
        config = FIXTURE_NODE_CONFIG
        output = dedent(
            """\
            pcs -- node utilization node1 cpu=4 ram=32
            pcs -- node utilization node2 cpu=8 ram=64
            """
        )
        self.assert_lines(config, output)


class FilterNodesByNodeName(TestCase):
    def test_no_match(self):
        self.assertEqual(
            CibNodeListDto(nodes=[]),
            node_output.filter_nodes_by_node_name(FIXTURE_NODE_CONFIG, "nodeX"),
        )

    def test_match(self):
        self.assertEqual(
            CibNodeListDto(nodes=FIXTURE_NODE_CONFIG.nodes[0:1]),
            node_output.filter_nodes_by_node_name(FIXTURE_NODE_CONFIG, "node1"),
        )


class FilterNodesByNvpairName(TestCase):
    nodes_config = CibNodeListDto(
        nodes=[
            CibNodeDto(
                id="1",
                uname="node1",
                description=None,
                score=None,
                type=None,
                instance_attributes=[
                    CibNvsetDto(
                        id="ia1",
                        options={},
                        rule=None,
                        nvpairs=[
                            CibNvpairDto(id="ia1b", name="b", value="2"),
                        ],
                    ),
                ],
                utilization=[
                    CibNvsetDto(
                        id="ua1",
                        options={},
                        rule=None,
                        nvpairs=[
                            CibNvpairDto(id="ua1a", name="a", value="1"),
                        ],
                    ),
                ],
            ),
            CibNodeDto(
                id="2",
                uname="node2",
                description=None,
                score=None,
                type=None,
                instance_attributes=[
                    CibNvsetDto(
                        id="ia2",
                        options={},
                        rule=None,
                        nvpairs=[
                            CibNvpairDto(id="ia2a", name="a", value="1"),
                        ],
                    ),
                ],
                utilization=[
                    CibNvsetDto(
                        id="ua2",
                        options={},
                        rule=None,
                        nvpairs=[
                            CibNvpairDto(id="ua2b", name="b", value="2"),
                        ],
                    ),
                ],
            ),
        ]
    )

    def test_no_nvpair_name_match(self):
        self.assertEqual(
            CibNodeListDto(
                nodes=[
                    CibNodeDto(
                        id="1",
                        uname="node1",
                        description=None,
                        score=None,
                        type=None,
                        instance_attributes=[
                            CibNvsetDto(
                                id="ia1",
                                options={},
                                rule=None,
                                nvpairs=[],
                            ),
                        ],
                        utilization=[
                            CibNvsetDto(
                                id="ua1",
                                options={},
                                rule=None,
                                nvpairs=[],
                            ),
                        ],
                    ),
                    CibNodeDto(
                        id="2",
                        uname="node2",
                        description=None,
                        score=None,
                        type=None,
                        instance_attributes=[
                            CibNvsetDto(
                                id="ia2",
                                options={},
                                rule=None,
                                nvpairs=[],
                            ),
                        ],
                        utilization=[
                            CibNvsetDto(
                                id="ua2",
                                options={},
                                rule=None,
                                nvpairs=[],
                            ),
                        ],
                    ),
                ]
            ),
            node_output.filter_nodes_nvpairs_by_name(self.nodes_config, "X"),
        )

    def test_match(self):
        self.assertEqual(
            CibNodeListDto(
                nodes=[
                    CibNodeDto(
                        id="1",
                        uname="node1",
                        description=None,
                        score=None,
                        type=None,
                        instance_attributes=[
                            CibNvsetDto(
                                id="ia1",
                                options={},
                                rule=None,
                                nvpairs=[],
                            ),
                        ],
                        utilization=[
                            CibNvsetDto(
                                id="ua1",
                                options={},
                                rule=None,
                                nvpairs=[
                                    CibNvpairDto(
                                        id="ua1a", name="a", value="1"
                                    ),
                                ],
                            ),
                        ],
                    ),
                    CibNodeDto(
                        id="2",
                        uname="node2",
                        description=None,
                        score=None,
                        type=None,
                        instance_attributes=[
                            CibNvsetDto(
                                id="ia2",
                                options={},
                                rule=None,
                                nvpairs=[
                                    CibNvpairDto(
                                        id="ia2a", name="a", value="1"
                                    ),
                                ],
                            ),
                        ],
                        utilization=[
                            CibNvsetDto(
                                id="ua2",
                                options={},
                                rule=None,
                                nvpairs=[],
                            ),
                        ],
                    ),
                ]
            ),
            node_output.filter_nodes_nvpairs_by_name(self.nodes_config, "a"),
        )
