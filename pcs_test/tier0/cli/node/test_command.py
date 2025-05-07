import json
from textwrap import dedent
from typing import Optional
from unittest import TestCase, mock

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.node.command import (
    node_attribute_output_cmd,
    node_utilization_output_cmd,
)
from pcs.common.interface import dto
from pcs.common.pacemaker.cluster_property import ClusterPropertyMetadataDto
from pcs.common.pacemaker.node import CibNodeListDto
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
    CibNvsetDto,
    ListCibNvsetDto,
)

from pcs_test.tools.custom_mock import RuleInEffectEvalMock
from pcs_test.tools.misc import dict_to_modifiers
from pcs_test.tools.nodes_dto import get_nodes_dto

FIXTURE_NODE_CONFIG = get_nodes_dto(RuleInEffectEvalMock({}))

UTILIZATION_WARNING = (
    "Utilization attributes configuration has no effect until cluster property "
    "option 'placement-strategy' is set to one of the values: 'balanced', "
    "'minimal', 'utilization'"
)

FIXTURE_PLACEMENT_STRATEGY_SET = ListCibNvsetDto(
    nvsets=[
        CibNvsetDto(
            id="cib-bootstrap-options",
            options={},
            rule=None,
            nvpairs=[
                CibNvpairDto(
                    id="id-ps-b", name="placement-strategy", value="balanced"
                )
            ],
        )
    ]
)


FIXTURE_TEXT_OUTPUT = {
    "utilization": {
        "cmd": (
            "pcs -- node utilization node1 cpu=4 ram=32;\n"
            "pcs -- node utilization node2 cpu=8 ram=64"
        ),
        "text": dedent(
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
                      Expression: date gt 2000-01-01"""
        ),
        "node": dedent(
            """\
                Node: node2
                  Utilization: nodes-2-utilization
                    cpu=8
                    ram=64
                    Rule: boolean-op=and score=INFINITY
                      Expression: date gt 2000-01-01"""
        ),
        "name": dedent(
            """\
                Node: node1
                  Description: node1 desc
                  Utilization: nodes-1-utilization score=50
                    cpu=4
                Node: node2
                  Utilization: nodes-2-utilization
                    cpu=8
                    Rule: boolean-op=and score=INFINITY
                      Expression: date gt 2000-01-01"""
        ),
        "node_and_name": dedent(
            """\
                Node: node2
                  Utilization: nodes-2-utilization
                    ram=64
                    Rule: boolean-op=and score=INFINITY
                      Expression: date gt 2000-01-01"""
        ),
    },
    "attribute": {
        "cmd": (
            "pcs -- node attribute node1 a=1 b=2;\n"
            "pcs -- node attribute node2 a=1 b=2"
        ),
        "text": dedent(
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
                    b=2"""
        ),
        "node": dedent(
            """\
                Node: node2
                  Attributes: nodes-2
                    a=1
                    b=2"""
        ),
        "name": dedent(
            """\
                Node: node1
                  Description: node1 desc
                  Attributes: nodes-1 score=50
                    a=1
                    Rule: score=INFINITY
                      Expression: date lt 2000-01-01
                Node: node2
                  Attributes: nodes-2
                    a=1"""
        ),
        "node_and_name": dedent(
            """\
                Node: node2
                  Attributes: nodes-2
                    b=2"""
        ),
    },
}


class NodeOutputCmdBaseMixin:
    def _assert_lib_mocks(self, utilization_warning=False):
        self.node.get_config_dto.assert_called_once_with()
        if self.command == "utilization":
            if utilization_warning:
                self.cluster_property.get_properties.assert_called_once_with()
                self.cluster_property.get_properties_metadata.assert_called_once_with()
            else:
                self.cluster_property.get_properties.assert_not_called()
                self.cluster_property.get_properties_metadata.assert_not_called()

    def test_no_text_output_format_and_node_arg(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["node"], {"output-format": "json"})
        self.assertEqual(
            cm.exception.message,
            "filtering is not supported with --output-format=cmd|json",
        )
        mock_print.assert_not_called()

    def test_no_text_output_format_and_name_option(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"name": "attr-name", "output-format": "cmd"})
        self.assertEqual(
            cm.exception.message,
            "filtering is not supported with --output-format=cmd|json",
        )
        mock_print.assert_not_called()

    def test_unknown_option(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"all": True})
        self.assertEqual(
            cm.exception.message,
            "Specified option '--all' is not supported in this command",
        )
        mock_print.assert_not_called()

    def test_more_than_one_arg(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["node1", "node2"])
        self.assertIsNone(cm.exception.message)
        mock_print.assert_not_called()

    def test_unsupported_output_format(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"output-format": "unsupported"})
        self.assertEqual(
            cm.exception.message,
            (
                "Unknown value 'unsupported' for '--output-format' option. "
                "Supported values are: 'cmd', 'json', 'text'"
            ),
        )
        self.node.get_config_dto.assert_not_called()
        mock_print.assert_not_called()

    def test_empty_config_default_output_format(self, mock_print):
        self._set_empty_config()
        self._call_cmd([])
        self._assert_lib_mocks(utilization_warning=True)
        mock_print.assert_not_called()

    def test_empty_config_json_output_format(self, mock_print):
        self._set_empty_config()
        self._call_cmd([], {"output-format": "json"})
        self._assert_lib_mocks()
        mock_print.assert_called_once_with('{"nodes": []}')

    def test_empty_config_cmd_output_format(self, mock_print):
        self._set_empty_config()
        self._call_cmd([], {"output-format": "cmd"})
        self._assert_lib_mocks()
        mock_print.assert_not_called()

    def test_output_format_json(self, mock_print):
        self._call_cmd([], {"output-format": "json"})
        self._assert_lib_mocks()
        mock_print.assert_called_once_with(
            json.dumps(dto.to_dict(FIXTURE_NODE_CONFIG))
        )

    def test_output_format_cmd(self, mock_print):
        self._call_cmd([], {"output-format": "cmd"})
        self._assert_lib_mocks()
        mock_print.assert_called_once_with(
            FIXTURE_TEXT_OUTPUT[self.command]["cmd"]
        )

    def test_output_format_text(self, mock_print):
        self._call_cmd([], {"output-format": "text"})
        self._assert_lib_mocks(utilization_warning=True)
        mock_print.assert_called_once_with(
            FIXTURE_TEXT_OUTPUT[self.command]["text"]
        )

    def test_output_format_text_filter_node(self, mock_print):
        self._call_cmd(["node2"])
        self._assert_lib_mocks(utilization_warning=True)
        mock_print.assert_called_once_with(
            FIXTURE_TEXT_OUTPUT[self.command]["node"]
        )

    def test_output_format_text_filter_node_does_not_exist(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["nodeX"])
        self.assertEqual(cm.exception.message, "Unable to find a node: nodeX")
        self._assert_lib_mocks()
        mock_print.assert_not_called()

    def test_output_format_text_filter_name(self, mock_print):
        self._call_cmd([], {"name": self.filter_name})
        self._assert_lib_mocks(utilization_warning=True)
        mock_print.assert_called_once_with(
            FIXTURE_TEXT_OUTPUT[self.command]["name"]
        )

    def test_output_format_text_filter_node_and_name(self, mock_print):
        self._call_cmd(["node2"], {"name": self.filter_node_and_name})
        self._assert_lib_mocks(utilization_warning=True)
        mock_print.assert_called_once_with(
            FIXTURE_TEXT_OUTPUT[self.command]["node_and_name"]
        )


@mock.patch("pcs.cli.node.command.print")
class TestNodeAttributeOutputCmd(NodeOutputCmdBaseMixin, TestCase):
    command = "attribute"
    filter_name = "a"
    filter_node_and_name = "b"
    label = "Attributes"
    set_id = "ia"

    def setUp(self):
        self.lib = mock.Mock(spec_set=["node"])
        self.node = mock.Mock(spec_set=["get_config_dto"])
        self.lib.node = self.node
        self._set_config()

    def _call_cmd(self, argv, modifiers=None):
        node_attribute_output_cmd(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def _set_config(
        self,
        node_config: Optional[CibNodeListDto] = None,
    ):
        self.node.get_config_dto.return_value = FIXTURE_NODE_CONFIG
        if node_config:
            self.node.get_config_dto.return_value = node_config

    def _set_empty_config(self):
        self.node.get_config_dto.return_value = CibNodeListDto(nodes=[])

    def test_force_option_shows_help(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"force": True})
        self.assertIsNone(cm.exception.message)
        mock_print.assert_not_called()


@mock.patch("pcs.cli.node.command.print")
class TestNodeUtilizationOutputCmd(NodeOutputCmdBaseMixin, TestCase):
    command = "utilization"
    filter_name = "cpu"
    filter_node_and_name = "ram"
    label = "Utilization"
    set_id = "-utilization"

    def setUp(self):
        self.lib = mock.Mock(spec_set=["node", "cluster_property"])
        self.node = mock.Mock(spec_set=["get_config_dto"])
        self.lib.node = self.node
        self.cluster_property = mock.Mock(
            spec_set=["get_properties", "get_properties_metadata"]
        )
        self.lib.cluster_property = self.cluster_property
        self._set_config()

    def _call_cmd(self, argv, modifiers=None):
        node_utilization_output_cmd(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def _set_config(
        self,
        node_config: Optional[CibNodeListDto] = None,
        properties_config: Optional[ListCibNvsetDto] = None,
    ):
        self.node.get_config_dto.return_value = FIXTURE_NODE_CONFIG
        self.cluster_property.get_properties.return_value = (
            FIXTURE_PLACEMENT_STRATEGY_SET
        )
        self.cluster_property.get_properties_metadata.return_value = (
            ClusterPropertyMetadataDto(
                properties_metadata=[], readonly_properties=[]
            )
        )
        if node_config:
            self.node.get_config_dto.return_value = node_config
        if properties_config:
            self.cluster_property.get_properties.return_value = (
                properties_config
            )

    def _set_empty_config(self):
        self.node.get_config_dto.return_value = CibNodeListDto(nodes=[])
        self.cluster_property.get_properties.return_value = (
            FIXTURE_PLACEMENT_STRATEGY_SET
        )
        self.cluster_property.get_properties_metadata.return_value = (
            ClusterPropertyMetadataDto(
                properties_metadata=[], readonly_properties=[]
            )
        )

    @mock.patch("pcs.utils.reports_output.warn")
    def test_utilization_warning(self, mock_warn, mock_print):
        self._set_empty_config()
        self.cluster_property.get_properties.return_value = ListCibNvsetDto(
            nvsets=[]
        )
        self._call_cmd([])
        self._assert_lib_mocks(utilization_warning=True)
        mock_print.assert_not_called()
        mock_warn.assert_called_once_with(UTILIZATION_WARNING)

    def test_force_option_not_supported(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"force": True})
        self.assertEqual(
            cm.exception.message,
            "Specified option '--force' is not supported in this command",
        )
        mock_print.assert_not_called()
