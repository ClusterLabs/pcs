import json
from unittest import TestCase

from pcs.common.interface.dto import to_dict
from pcs.common.pacemaker.resource.list import CibResourcesDto

from pcs_test.tier1.resource.test_config import ResourceConfigCmdMixin
from pcs_test.tools import resources_dto
from pcs_test.tools.misc import get_test_resource
from pcs_test.tools.pcs_runner import PcsRunner


class StonithConfigJson(TestCase):
    def setUp(self):
        self.pcs_runner = PcsRunner(
            cib_file=get_test_resource("cib-resources.xml"),
        )
        self.maxDiff = None

    def test_all(self):
        stdout, stderr, retval = self.pcs_runner.run(
            ["stonith", "config", "--output-format=json"],
        )
        self.assertEqual(
            stderr,
            "Warning: Only 'text' output format is supported for stonith levels\n",
        )
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
        self.assertEqual(
            stderr,
            "Warning: Only 'text' output format is supported for stonith levels\n",
        )
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
