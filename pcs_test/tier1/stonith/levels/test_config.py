import json
import shlex
from unittest import TestCase

from pcs.common.interface import dto
from pcs.common.pacemaker.fencing_topology import (
    CibFencingLevelAttributeDto,
    CibFencingLevelNodeDto,
    CibFencingLevelRegexDto,
    CibFencingTopologyDto,
)

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


class LevelsConfigJson(TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_empty(self):
        pcs_runner = PcsRunner(cib_file=get_test_resource("cib-empty.xml"))
        stdout, stderr, retval = pcs_runner.run(
            ["stonith", "level", "config", "--output-format=json"]
        )
        expected = CibFencingTopologyDto(
            target_node=[], target_regex=[], target_attribute=[]
        )
        self.assertEqual(
            json.loads(stdout), json.loads(json.dumps(dto.to_dict(expected)))
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_success(self):
        pcs_runner = PcsRunner(
            cib_file=get_test_resource("cib-fencing-levels.xml")
        )

        stdout, stderr, retval = pcs_runner.run(
            ["stonith", "level", "config", "--output-format=json"]
        )
        expected = CibFencingTopologyDto(
            [
                CibFencingLevelNodeDto(
                    id="fl-rh-1-1", target="rh-1", index=1, devices=["S1"]
                ),
                CibFencingLevelNodeDto(
                    id="fl-rh-1-2", target="rh-1", index=2, devices=["S2"]
                ),
                CibFencingLevelNodeDto(
                    id="fl-rh-2-1", target="rh-2", index=1, devices=["S3", "S4"]
                ),
            ],
            [
                CibFencingLevelRegexDto(
                    id="fl-rh-.-3",
                    target_pattern="rh-.*",
                    index=3,
                    devices=["S4"],
                )
            ],
            [
                CibFencingLevelAttributeDto(
                    id="fl-foo-4",
                    target_attribute="foo",
                    target_value="bar",
                    index=4,
                    devices=["S1", "S2", "S3"],
                )
            ],
        )
        self.assertEqual(
            json.loads(stdout), json.loads(json.dumps(dto.to_dict(expected)))
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)


class LevelsConfigCmd(TestCase):
    def setUp(self):
        self.old_cib = get_tmp_file("tier1_stonith_level_cmd_old")
        write_file_to_tmpfile(
            get_test_resource("cib-fencing-levels.xml"), self.old_cib
        )
        self.new_cib = get_tmp_file("tier1_stonith_level_cmd_new")
        write_file_to_tmpfile(get_test_resource("cib-empty.xml"), self.new_cib)
        self.old_pcs_runner = PcsRunner(self.old_cib.name)
        self.new_pcs_runner = PcsRunner(self.new_cib.name)
        self.maxDiff = None

    def tearDown(self):
        self.old_cib.close()
        self.new_cib.close()

    def _get_as_json(self, runner):
        stdout, stderr, retval = runner.run(
            ["stonith", "level", "config", "--output-format=json"]
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        return json.loads(stdout)

    def test_success(self):
        stdout, stderr, retval = self.old_pcs_runner.run(
            ["stonith", "level", "config", "--output-format=cmd"]
        )
        self.assertEqual(retval, 0)
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
            self._get_as_json(self.new_pcs_runner),
            self._get_as_json(self.old_pcs_runner),
        )


class LevelsConfigText(AssertPcsMixin, TestCase):
    FIXTURE_OUTPUT = (
        "Target (node): rh-1\n"
        "  Level 1: S1\n"
        "  Level 2: S2\n"
        "Target (node): rh-2\n"
        "  Level 1: S3 S4\n"
        "Target (regexp): rh-.*\n"
        "  Level 3: S4\n"
        "Target (attribute): foo=bar\n"
        "  Level 4: S1 S2 S3\n"
    )

    def setUp(self):
        self.maxDiff = None
        self.pcs_runner = PcsRunner(
            cib_file=get_test_resource("cib-fencing-levels.xml")
        )

    def test_empty(self):
        pcs_runner = PcsRunner(cib_file=get_test_resource("cib-empty.xml"))
        stdout, stderr, retval = pcs_runner.run(
            ["stonith", "level", "config", "--output-format=text"]
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_success(self):
        self.assert_pcs_success(
            ["stonith", "level", "config", "--output-format=text"],
            stdout_full=self.FIXTURE_OUTPUT,
        )

    def test_success_no_option(self):
        self.assert_pcs_success(
            ["stonith", "level", "config"], stdout_full=self.FIXTURE_OUTPUT
        )

    def test_success_no_config(self):
        self.assert_pcs_success(
            ["stonith", "level"], stdout_full=self.FIXTURE_OUTPUT
        )
