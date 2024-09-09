from unittest import TestCase

from pcs.cli.stonith.levels import output
from pcs.common.pacemaker.fencing_topology import (
    CibFencingLevelAttributeDto,
    CibFencingLevelNodeDto,
    CibFencingLevelRegexDto,
    CibFencingTopologyDto,
)

FIXTURE_TARGET_NODE_DTO_LIST = [
    CibFencingLevelNodeDto("fl1", "node1", 1, ["d1"]),
    CibFencingLevelNodeDto("fl2", "node1", 2, ["d2"]),
    CibFencingLevelNodeDto("fl3", "node2", 3, ["d3", "d4"]),
]
FIXTURE_REGEX_DTO_LIST = [
    CibFencingLevelRegexDto("fl1", "node.*", 1, ["d1"]),
    CibFencingLevelRegexDto("fl2", "node.*", 2, ["d2"]),
    CibFencingLevelRegexDto("fl3", ".*node", 3, ["d3", "d4"]),
]
FIXTURE_ATTRIBUTE_DTO_LIST = [
    CibFencingLevelAttributeDto("fl1", "A", "B", 1, ["d1"]),
    CibFencingLevelAttributeDto("fl2", "A", "B", 2, ["d2"]),
    CibFencingLevelAttributeDto("fl3", "A", "X", 2, ["d2"]),
    CibFencingLevelAttributeDto("fl4", "B", "B", 3, ["d3", "d4"]),
]


class LevelsToOutputMixin:
    def test_empty(self):
        command_output = self._call_command(CibFencingTopologyDto([], [], []))
        self.assertEqual(command_output, [])

    def test_nodes(self):
        command_output = self._call_command(
            CibFencingTopologyDto(FIXTURE_TARGET_NODE_DTO_LIST, [], [])
        )
        self.assertEqual(command_output, self.NODE_OUTPUT)

    def test_regex(self):
        command_output = self._call_command(
            CibFencingTopologyDto([], FIXTURE_REGEX_DTO_LIST, [])
        )
        self.assertEqual(command_output, self.REGEX_OUTPUT)

    def test_attributes(self):
        command_output = self._call_command(
            CibFencingTopologyDto([], [], FIXTURE_ATTRIBUTE_DTO_LIST)
        )
        self.assertEqual(command_output, self.ATTRIBUTE_OUTPUT)

    def test_combination(self):
        command_output = self._call_command(
            CibFencingTopologyDto(
                FIXTURE_TARGET_NODE_DTO_LIST,
                FIXTURE_REGEX_DTO_LIST,
                FIXTURE_ATTRIBUTE_DTO_LIST,
            )
        )
        self.assertEqual(
            command_output,
            self.NODE_OUTPUT + self.REGEX_OUTPUT + self.ATTRIBUTE_OUTPUT,
        )


class LevelsToText(TestCase, LevelsToOutputMixin):
    NODE_OUTPUT = [
        "Target (node): node1",
        "  Level 1: d1",
        "  Level 2: d2",
        "Target (node): node2",
        "  Level 3: d3 d4",
    ]

    REGEX_OUTPUT = [
        "Target (regexp): .*node",
        "  Level 3: d3 d4",
        "Target (regexp): node.*",
        "  Level 1: d1",
        "  Level 2: d2",
    ]

    ATTRIBUTE_OUTPUT = [
        "Target (attribute): A=B",
        "  Level 1: d1",
        "  Level 2: d2",
        "Target (attribute): B=B",
        "  Level 3: d3 d4",
        "Target (attribute): A=X",
        "  Level 2: d2",
    ]

    def _call_command(self, dto):
        # pylint: disable=no-self-use
        return output.stonith_level_config_to_text(dto)


class LevelsToCmd(TestCase, LevelsToOutputMixin):
    NODE_OUTPUT = [
        "pcs stonith level add --force -- 1 node1 d1 id=fl1",
        "pcs stonith level add --force -- 2 node1 d2 id=fl2",
        "pcs stonith level add --force -- 3 node2 d3 d4 id=fl3",
    ]

    REGEX_OUTPUT = [
        "pcs stonith level add --force -- 1 regexp%node.* d1 id=fl1",
        "pcs stonith level add --force -- 2 regexp%node.* d2 id=fl2",
        "pcs stonith level add --force -- 3 regexp%.*node d3 d4 id=fl3",
    ]

    ATTRIBUTE_OUTPUT = [
        "pcs stonith level add --force -- 1 attrib%A=B d1 id=fl1",
        "pcs stonith level add --force -- 2 attrib%A=B d2 id=fl2",
        "pcs stonith level add --force -- 2 attrib%A=X d2 id=fl3",
        "pcs stonith level add --force -- 3 attrib%B=B d3 d4 id=fl4",
    ]

    def _call_command(self, dto):
        # pylint: disable=no-self-use
        return output.stonith_level_config_to_cmd(dto)
