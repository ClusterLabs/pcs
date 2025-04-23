import json
import shlex
from unittest import TestCase

from lxml import etree

from pcs.common.interface import dto
from pcs.common.pacemaker.node import CibNodeDto, CibNodeListDto
from pcs.common.pacemaker.nvset import CibNvpairDto, CibNvsetDto

from pcs_test.tier1.legacy.common import (
    FIXTURE_UTILIZATION_WARNING,
)
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner

FIXTURE_EMPTY_NODES_DTO = CibNodeListDto(
    nodes=[
        CibNodeDto(
            id="1",
            uname="rh7-1",
            description=None,
            score=None,
            type=None,
            instance_attributes=[],
            utilization=[],
        ),
        CibNodeDto(
            id="2",
            uname="rh7-2",
            description=None,
            score=None,
            type=None,
            instance_attributes=[],
            utilization=[],
        ),
    ]
)

FIXTURE_NODES_DTO = CibNodeListDto(
    nodes=[
        CibNodeDto(
            id="1",
            uname="rh7-1",
            description=None,
            score=None,
            type=None,
            instance_attributes=[
                CibNvsetDto(
                    id="nodes-1",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(id="nodes-1-a", name="a", value="1"),
                        CibNvpairDto(id="nodes-1-b", name="b", value="2"),
                    ],
                )
            ],
            utilization=[
                CibNvsetDto(
                    id="nodes-1-utilization",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(
                            id="nodes-1-utilization-cpu", name="cpu", value="4"
                        ),
                        CibNvpairDto(
                            id="nodes-1-utilization-ram", name="ram", value="32"
                        ),
                    ],
                )
            ],
        ),
        CibNodeDto(
            id="2",
            uname="rh7-2",
            description=None,
            score=None,
            type=None,
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
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(
                            id="nodes-2-utilization-cpu", name="cpu", value="8"
                        ),
                        CibNvpairDto(
                            id="nodes-2-utilization-ram", name="ram", value="64"
                        ),
                    ],
                )
            ],
        ),
    ]
)

FIXTURE_ATTRIBUTES_TEXT = """\
Node: rh7-1
  Attributes: nodes-1
    a=1
    b=2
Node: rh7-2
  Attributes: nodes-2
    a=1
    b=2
"""

FIXTURE_UTILIZATION_TEXT = """\
Node: rh7-1
  Utilization: nodes-1-utilization
    cpu=4
    ram=32
Node: rh7-2
  Utilization: nodes-2-utilization
    cpu=8
    ram=64
"""


class NodeOutputFormatJsonMixin:
    def setUp(self):
        self.maxDiff = None

    def test_empty_nodes(self):
        pcs_runner = PcsRunner(
            cib_file=get_test_resource("cib-empty-withnodes.xml")
        )
        stdout, stderr, retval = pcs_runner.run(
            ["node", self.command, "--output-format=json"]
        )
        self.assertEqual(
            json.loads(stdout), dto.to_dict(FIXTURE_EMPTY_NODES_DTO)
        )
        self.assertEqual(stderr, self.expected_stderr)
        self.assertEqual(retval, 0)

    def test_success(self):
        temp_cib = get_tmp_file("tier1_nodes_json")
        write_file_to_tmpfile(get_test_resource("cib-all.xml"), temp_cib)
        pcs_runner = PcsRunner(cib_file=temp_cib.name)
        stdout, stderr, retval = pcs_runner.run(
            ["node", self.command, "--output-format=json"]
        )
        self.assertEqual(json.loads(stdout), dto.to_dict(FIXTURE_NODES_DTO))
        self.assertEqual(stderr, self.expected_stderr)
        self.assertEqual(retval, 0)
        temp_cib.close()


class NodeAttributeOutputFormatJson(NodeOutputFormatJsonMixin, TestCase):
    command = "attribute"
    expected_stderr = ""


class NodeUtilizationOutputFormatJson(NodeOutputFormatJsonMixin, TestCase):
    command = "utilization"
    expected_stderr = FIXTURE_UTILIZATION_WARNING


class NodeAttributeUtilizationOutputFormatCmd(TestCase):
    def setUp(self):
        self.old_cib = get_tmp_file("tier1_node_cmd_old")
        write_file_to_tmpfile(get_test_resource("cib-all.xml"), self.old_cib)
        self.new_cib = get_tmp_file("tier1_node_cmd_new")
        write_file_to_tmpfile(
            get_test_resource("cib-empty-withnodes.xml"), self.new_cib
        )
        self.old_pcs_runner = PcsRunner(self.old_cib.name)
        self.new_pcs_runner = PcsRunner(self.new_cib.name)
        self.maxDiff = None

    def tearDown(self):
        self.old_cib.close()
        self.new_cib.close()

    def _get_as_json(self, runner, command):
        stdout, stderr, retval = runner.run(
            ["node", command, "--output-format=json"]
        )
        self.assertEqual(
            stderr,
            "" if command != "utilization" else FIXTURE_UTILIZATION_WARNING,
        )
        self.assertEqual(retval, 0)
        return json.loads(stdout)

    def test_success(self):
        stdout_attribute, stderr, retval = self.old_pcs_runner.run(
            ["node", "attribute", "--output-format=cmd"]
        )
        self.assertEqual(retval, 0)
        stdout_utilization, stderr, retval = self.old_pcs_runner.run(
            ["node", "utilization", "--output-format=cmd"]
        )
        self.assertEqual(retval, 0)
        stdout = ";\n".join([stdout_attribute, stdout_utilization])
        commands = [
            shlex.split(command)[1:]
            for command in stdout.replace("\\n", "").strip().split(";\n")
        ]
        for cmd in commands:
            stdout, stderr, retval = self.new_pcs_runner.run(cmd)
            self.assertEqual(
                retval,
                0,
                (
                    f"Command {cmd} exited with {retval}\nstdout:\n{stdout}\n"
                    f"stderr:\n{stderr}"
                ),
            )
        self.assertEqual(
            self._get_as_json(self.new_pcs_runner, "attribute"),
            self._get_as_json(self.old_pcs_runner, "attribute"),
        )
        self.assertEqual(
            self._get_as_json(self.new_pcs_runner, "utilization"),
            self._get_as_json(self.old_pcs_runner, "utilization"),
        )


class NodeOutputFormatTextMixin:
    def setUp(self):
        self.maxDiff = None

    def test_empty(self):
        pcs_runner = PcsRunner(
            cib_file=get_test_resource("cib-empty-withnodes.xml")
        )
        stdout, stderr, retval = pcs_runner.run(
            ["node", self.command, "--output-format=text"]
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, self.expected_stderr)
        self.assertEqual(retval, 0)

    def test_success(self):
        pcs_runner = PcsRunner(cib_file=get_test_resource("cib-all.xml"))
        stdout, stderr, retval = pcs_runner.run(
            ["node", self.command, "--output-format=text"]
        )
        self.assertEqual(stdout, self.expected_stdout)
        self.assertEqual(stderr, self.expected_stderr)
        self.assertEqual(retval, 0)


class NodeAttributeOutputFormatText(NodeOutputFormatTextMixin, TestCase):
    command = "attribute"
    expected_stdout = FIXTURE_ATTRIBUTES_TEXT
    expected_stderr = ""


class NodeUtilizationOutputFormatText(NodeOutputFormatTextMixin, TestCase):
    command = "utilization"
    expected_stdout = FIXTURE_UTILIZATION_TEXT
    expected_stderr = FIXTURE_UTILIZATION_WARNING


class NodeOutputFormatErrorsMixin(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).findall(".//nodes")[0])
    )
):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_tag")
        write_file_to_tmpfile(
            get_test_resource("cib-empty-withnodes.xml"), self.temp_cib
        )
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def test_name_with_output_format_no_text(self):
        self.assert_pcs_fail(
            f"node {self.command} --output-format=json --name cpu".split(),
            "Error: filtering is not supported with --output-format=cmd|json\n",
        )

    def test_output_format_with_args(self):
        self.assert_pcs_fail(
            f"node {self.command} --output-format=cmd rh7-1 cpu=".split(),
            stderr_start="\nUsage: pcs node <command>",
        )

    def test_multiple_args(self):
        self.assert_pcs_fail(
            f"node {self.command} rh7-1 cpu".split(),
            "{warn}Error: missing value of 'cpu' option\n".format(
                warn=(
                    ""
                    if self.command != "utilization"
                    else FIXTURE_UTILIZATION_WARNING
                )
            ),
        )


class NodeAttributeOutputFormatErrors(NodeOutputFormatErrorsMixin, TestCase):
    command = "attribute"


class NodeUtilizationOutputFormatErrors(NodeOutputFormatErrorsMixin, TestCase):
    command = "utilization"
