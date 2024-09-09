import json
import shlex
from unittest import TestCase

from pcs.common.interface.dto import to_dict
from pcs.common.pacemaker.resource.list import CibResourcesDto

from pcs_test.tier1.resource.test_config import ResourceConfigCmdMixin
from pcs_test.tools import resources_dto
from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner

FIXTURE_JSON_WARNING = (
    "Warning: Fencing levels are not included because this command "
    "could only export stonith configuration previously. This cannot "
    "be changed to avoid breaking existing tooling. To export fencing "
    "levels, run 'pcs stonith level config --output-format=json'\n"
)


class StonithConfigJson(AssertPcsMixin, TestCase):
    def setUp(self):
        self.pcs_runner = PcsRunner(
            cib_file=get_test_resource("cib-resources.xml"),
        )
        self.maxDiff = None

    def test_all(self):
        stdout, stderr, retval = self.pcs_runner.run(
            ["stonith", "config", "--output-format=json"],
        )
        self.assertEqual(stderr, FIXTURE_JSON_WARNING)
        self.assertEqual(retval, 0)
        expected = CibResourcesDto(
            primitives=[
                resources_dto.STONITH_S2,
                resources_dto.STONITH_S1,
            ],
            clones=[],
            groups=[],
            bundles=[],
        )
        self.assertEqual(json.loads(stdout), to_dict(expected))

    def test_get_specified(self):
        stdout, stderr, retval = self.pcs_runner.run(
            ["stonith", "config", "--output-format=json", "S1"],
        )
        self.assertEqual(stderr, FIXTURE_JSON_WARNING)
        self.assertEqual(retval, 0)
        expected = CibResourcesDto(
            primitives=[
                resources_dto.STONITH_S1,
            ],
            clones=[],
            groups=[],
            bundles=[],
        )
        self.assertEqual(json.loads(stdout), to_dict(expected))


class StonithConfigCmd(ResourceConfigCmdMixin, TestCase):
    @staticmethod
    def _get_tmp_file_name():
        return "tier1_stonith_test_config_cib.xml"


class StonithConfigWithLevelsCmd(TestCase):
    def setUp(self):
        self.old_cib = get_tmp_file("tier1_stonith_cmd_old")
        write_file_to_tmpfile(
            get_test_resource("cib-fencing-levels.xml"), self.old_cib
        )
        self.new_cib = get_tmp_file("tier1_stonith_cmd_new")
        write_file_to_tmpfile(get_test_resource("cib-empty.xml"), self.new_cib)
        self.old_pcs_runner = PcsRunner(self.old_cib.name)
        self.new_pcs_runner = PcsRunner(self.new_cib.name)
        self.maxDiff = None

    def tearDown(self):
        self.old_cib.close()
        self.new_cib.close()

    def _get_stonith_resources_json(self, runner):
        stdout, stderr, retval = runner.run(
            ["stonith", "config", "--output-format=json"]
        )
        self.assertEqual(stderr, FIXTURE_JSON_WARNING)
        self.assertEqual(retval, 0)
        return json.loads(stdout)

    def _get_stonith_level_json(self, runner):
        stdout, stderr, retval = runner.run(
            ["stonith", "level", "config", "--output-format=json"]
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        return json.loads(stdout)

    def test_success(self):
        stdout, stderr, retval = self.old_pcs_runner.run(
            ["stonith", "config", "--output-format=cmd"]
        )
        self.assertEqual(retval, 0)
        commands = [
            shlex.split(command)[1:]
            for command in stdout.replace("\\\n", "").strip().split(";\n")
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
            self._get_stonith_resources_json(self.new_pcs_runner),
            self._get_stonith_resources_json(self.old_pcs_runner),
        )
        self.assertEqual(
            self._get_stonith_level_json(self.new_pcs_runner),
            self._get_stonith_level_json(self.old_pcs_runner),
        )


class StonithConfigText(AssertPcsMixin, TestCase):
    FIXTURE_S1 = (
        "Resource: S1 (class=stonith type=fence_pcsmock_minimal)\n"
        "  Operations:\n"
        "    monitor: S1-monitor-interval-60s\n"
        "      interval=60s\n"
    )
    FIXTURE_OTHER_RESOURCES = (
        "Resource: S2 (class=stonith type=fence_pcsmock_minimal)\n"
        "  Operations:\n"
        "    monitor: S2-monitor-interval-60s\n"
        "      interval=60s\n"
        "Resource: S3 (class=stonith type=fence_pcsmock_minimal)\n"
        "  Operations:\n"
        "    monitor: S3-monitor-interval-60s\n"
        "      interval=60s\n"
        "Resource: S4 (class=stonith type=fence_pcsmock_minimal)\n"
        "  Operations:\n"
        "    monitor: S4-monitor-interval-60s\n"
        "      interval=60s\n"
    )
    FIXTURE_FENCING_LEVELS = (
        "\n"
        "Fencing Levels:\n"
        "  Target (node): rh-1\n"
        "    Level 1: S1\n"
        "    Level 2: S2\n"
        "  Target (node): rh-2\n"
        "    Level 1: S3 S4\n"
        "  Target (regexp): rh-.*\n"
        "    Level 3: S4\n"
        "  Target (attribute): foo=bar\n"
        "    Level 4: S1 S2 S3\n"
    )
    FIXTURE_ALL = FIXTURE_S1 + FIXTURE_OTHER_RESOURCES + FIXTURE_FENCING_LEVELS

    def setUp(self):
        self.maxDiff = None
        self.pcs_runner = PcsRunner(
            cib_file=get_test_resource("cib-fencing-levels.xml")
        )

    def test_success(self):
        self.assert_pcs_success(
            ["stonith", "config", "--output-format=text"],
            stdout_full=self.FIXTURE_ALL,
        )

    def test_success_no_option(self):
        self.assert_pcs_success(
            ["stonith", "config"], stdout_full=self.FIXTURE_ALL
        )

    def test_success_filtered(self):
        self.assert_pcs_success(
            ["stonith", "config", "S1", "--output-format=text"],
            stdout_full=self.FIXTURE_S1 + self.FIXTURE_FENCING_LEVELS,
        )
