import json
from shlex import split
from unittest import TestCase

from pcs.common.interface.dto import to_dict
from pcs.common.pacemaker.resource.list import CibResourcesDto

from pcs_test.tools import resources_dto
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


class ResourceConfigJson(TestCase):
    def setUp(self):
        self.pcs_runner = PcsRunner(
            cib_file=get_test_resource("cib-resources.xml"),
        )

    def test_all(self):
        stdout, stderr, retval = self.pcs_runner.run(
            ["resource", "config", "--output-format=json"]
        )
        expected = CibResourcesDto(
            primitives=[
                resources_dto.PRIMITIVE_R1,
                resources_dto.PRIMITIVE_R7,
                resources_dto.PRIMITIVE_R5,
                resources_dto.STONITH_S1,
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
    def setUp(self):
        self.new_cib_file = get_tmp_file(self._get_tmp_file_name())
        self.pcs_runner_orig = PcsRunner(
            cib_file=get_test_resource("cib-resources.xml")
        )
        self.pcs_runner_new = PcsRunner(cib_file=self.new_cib_file.name)
        write_file_to_tmpfile(
            get_test_resource("cib-empty.xml"), self.new_cib_file
        )
        self.maxDiff = None

    def tearDown(self):
        self.new_cib_file.close()

    def _get_as_json(self, runner):
        stdout, stderr, retval = runner.run(
            ["resource", "config", "--output-format=json"]
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        return json.loads(stdout)

    def test_all(self):
        stdout, stderr, retval = self.pcs_runner_orig.run(
            ["resource", "config", "--output-format=cmd"]
        )
        self.assertEqual(retval, 0)
        self.assertEqual(
            stderr,
            (
                "Warning: Group 'G2' contains stonith resource: 'S1'. Group "
                "with stonith resource is unsupported, therefore pcs is unable "
                "to create it. The group will be omitted.\n"
            ),
        )
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
        expected_dict = self._get_as_json(self.pcs_runner_orig)
        expected_dict["groups"] = [
            group for group in expected_dict["groups"] if group["id"] != "G2"
        ]
        expected_dict["primitives"] = [
            primitive
            for primitive in expected_dict["primitives"]
            if primitive["id"] != "S1"
        ]
        self.assertEqual(
            self._get_as_json(self.pcs_runner_new),
            expected_dict,
        )


class ResourceConfigCmd(ResourceConfigCmdMixin, TestCase):
    @staticmethod
    def _get_tmp_file_name():
        return "tier1_resource_test_config_cib.xml"
