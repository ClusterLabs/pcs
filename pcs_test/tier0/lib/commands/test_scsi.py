from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from pcs.common.reports import codes as report_codes
from pcs.lib.commands import scsi


class TestUnfenceNode(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_success(self):
        self.config.runner.scsi.unfence_node("node1", ["/dev/sda", "/dev/sdb"])
        scsi.unfence_node(
            self.env_assist.get_env(), "node1", ["/dev/sdb", "/dev/sda"]
        )
        self.env_assist.assert_reports([])

    def test_failure(self):
        self.config.runner.scsi.unfence_node(
            "node1", ["/dev/sda", "/dev/sdb"], stderr="stderr", return_code=1
        )
        self.env_assist.assert_raise_library_error(
            lambda: scsi.unfence_node(
                self.env_assist.get_env(), "node1", ["/dev/sdb", "/dev/sda"]
            ),
            [
                fixture.error(
                    report_codes.STONITH_UNFENCING_FAILED, reason="stderr"
                )
            ],
            expected_in_processor=False,
        )
