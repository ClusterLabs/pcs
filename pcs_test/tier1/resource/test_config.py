import json
from shlex import split
from unittest import TestCase

from pcs.common.interface.dto import to_dict
from pcs.common.pacemaker.resource.clone import CibResourceCloneDto
from pcs.common.pacemaker.resource.group import CibResourceGroupDto
from pcs.common.pacemaker.resource.list import CibResourcesDto

from pcs_test.tools import resources_dto
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


class ResourceConfigJson(TestCase):
    def setUp(self):
        self.pcs_runner = PcsRunner(
            cib_file=get_test_resource("cib-all.xml"),
        )
        self.maxDiff = None

    def test_all(self):
        stdout, stderr, retval = self.pcs_runner.run(
            ["resource", "config", "--output-format=json"]
        )
        expected = CibResourcesDto(
            primitives=[
                resources_dto.PRIMITIVE_R1,
                resources_dto.PRIMITIVE_R7,
                resources_dto.PRIMITIVE_R5,
                resources_dto.PRIMITIVE_R2,
                resources_dto.PRIMITIVE_R3,
                resources_dto.PRIMITIVE_R4,
                resources_dto.PRIMITIVE_R6,
            ],
            clones=[
                resources_dto.CLONE_G1,
                resources_dto.CLONE_R6,
            ],
            groups=[
                resources_dto.GROUP_G2,
                resources_dto.GROUP_G1,
            ],
            bundles=[
                resources_dto.BUNDLE_B1,
                resources_dto.BUNDLE_B2,
            ],
        )
        self.assertEqual(json.loads(stdout), to_dict(expected))
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_get_multiple(self):
        stdout, stderr, retval = self.pcs_runner.run(
            ["resource", "config", "--output-format=json", "G1-clone", "R1"]
        )
        expected = CibResourcesDto(
            primitives=[
                resources_dto.PRIMITIVE_R1,
                resources_dto.PRIMITIVE_R2,
                resources_dto.PRIMITIVE_R3,
                resources_dto.PRIMITIVE_R4,
            ],
            clones=[resources_dto.CLONE_G1],
            groups=[resources_dto.GROUP_G1],
            bundles=[],
        )
        self.assertEqual(json.loads(stdout), to_dict(expected))
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)


class ResourceConfigCmdMixin:
    sub_command = None
    expected_json_config_stderr = ""

    def setUp(self):
        self.new_cib_file = get_tmp_file(self._get_tmp_file_name())
        self.pcs_runner_orig = PcsRunner(
            cib_file=get_test_resource("cib-all.xml")
        )
        self.pcs_runner_orig.mock_settings = get_mock_settings()
        self.pcs_runner_new = PcsRunner(cib_file=self.new_cib_file.name)
        self.pcs_runner_new.mock_settings = get_mock_settings()
        write_file_to_tmpfile(
            get_test_resource("cib-empty.xml"), self.new_cib_file
        )
        self.maxDiff = None

    def tearDown(self):
        self.new_cib_file.close()

    def _run_commands(self, stdout):
        cmds = [
            split(cmd)[1:]
            for cmd in stdout.replace("\\\n", "").strip().split(";\n")
        ]
        for cmd in cmds:
            stdout, stderr, retval = self.pcs_runner_new.run(cmd)
            self.assertEqual(
                retval,
                0,
                (
                    f"Command {cmd} exited with {retval}\nstdout:\n{stdout}\n"
                    f"stderr:\n{stderr}"
                ),
            )

    def _get_as_json(self, runner):
        stdout, stderr, retval = runner.run(
            [self.sub_command, "config", "--output-format=json"]
        )
        self.assertEqual(stderr, self.expected_json_config_stderr)
        self.assertEqual(retval, 0)
        return json.loads(stdout)

    def test_all(self):
        stdout, stderr, retval = self.pcs_runner_orig.run(
            [self.sub_command, "config", "--output-format=cmd"]
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, "")
        self._run_commands(stdout)
        self.assertEqual(
            self._get_as_json(self.pcs_runner_new),
            self._get_as_json(self.pcs_runner_orig),
        )


class ResourceConfigCmd(ResourceConfigCmdMixin, TestCase):
    sub_command = "resource"

    @staticmethod
    def _get_tmp_file_name():
        return "tier1_resource_test_config_cib.xml"

    def test_unsupported_stonith(self):
        self.pcs_runner_orig = PcsRunner(
            cib_file=get_test_resource("cib-unsupported-stonith-config.xml")
        )
        stdout, stderr, retval = self.pcs_runner_orig.run(
            ["resource", "config", "--output-format=cmd"]
        )
        self.assertEqual(retval, 0)
        self.assertEqual(
            stderr,
            (
                "Warning: Bundle resource 'B1' contains stonith resource: 'S1',"
                " which is unsupported. The bundle resource will be omitted.\n"
                "Warning: Group 'G1' contains stonith resource: 'S2', which is "
                "unsupported. The group will be omitted.\n"
                "Warning: Group 'G2' contains stonith resources: 'S4', 'S5', "
                "which is unsupported. The group will be omitted.\n"
                "Warning: Group 'G3' contains stonith resources: 'S6', 'S7', "
                "which is unsupported. The stonith resources will be omitted.\n"
                "Warning: Group 'G4' contains stonith resource: 'S8', which is "
                "unsupported. The stonith resource will be omitted.\n"
                "Warning: Clone 'S3-clone' contains stonith resource: 'S3', "
                "which is unsupported. The clone will be omitted.\n"
                "Warning: Clone 'G2-clone' contains stonith resources: 'S4', "
                "'S5', which is unsupported. The clone will be omitted.\n"
            ),
        )
        self._run_commands(stdout)
        expected_dict = to_dict(
            CibResourcesDto(
                primitives=[
                    resources_dto.PRIMITIVE_R1,
                    resources_dto.PRIMITIVE_R2,
                    resources_dto.PRIMITIVE_R3,
                ],
                clones=[
                    CibResourceCloneDto(
                        id="G4-clone",
                        description=None,
                        member_id="G4",
                        meta_attributes=[],
                        instance_attributes=[],
                    )
                ],
                groups=[
                    CibResourceGroupDto(
                        id="G3",
                        description=None,
                        member_ids=["R2"],
                        meta_attributes=[],
                        instance_attributes=[],
                    ),
                    CibResourceGroupDto(
                        id="G4",
                        description=None,
                        member_ids=["R3"],
                        meta_attributes=[],
                        instance_attributes=[],
                    ),
                ],
                bundles=[],
            )
        )
        self.assertEqual(
            self._get_as_json(self.pcs_runner_new),
            expected_dict,
        )
