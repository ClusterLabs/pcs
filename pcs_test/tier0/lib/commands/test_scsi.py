from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from pcs.common.reports import codes as report_codes
from pcs.lib.commands import scsi


class TestUnfenceNode(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.old_devices = ["device1", "device3"]
        self.new_devices = ["device3", "device0", "device2"]
        self.added_devices = set(self.new_devices) - set(self.old_devices)
        self.node = "node1"

    def test_success_devices_to_unfence(self):
        for old_dev in self.old_devices:
            self.config.runner.scsi.get_status(
                self.node, old_dev, name=f"runner.scsi.is_fenced.{old_dev}"
            )
        self.config.runner.scsi.unfence_node(self.node, self.added_devices)
        scsi.unfence_node(
            self.env_assist.get_env(),
            self.node,
            self.old_devices,
            self.new_devices,
        )
        self.env_assist.assert_reports([])

    def test_success_no_devices_to_unfence(self):
        scsi.unfence_node(
            self.env_assist.get_env(),
            self.node,
            {"device1", "device2", "device3"},
            {"device3"},
        )
        self.env_assist.assert_reports([])

    def test_unfencing_failure(self):
        err_msg = "stderr"
        for old_dev in self.old_devices:
            self.config.runner.scsi.get_status(
                self.node, old_dev, name=f"runner.scsi.is_fenced.{old_dev}"
            )
        self.config.runner.scsi.unfence_node(
            self.node, self.added_devices, stderr=err_msg, return_code=1
        )
        self.env_assist.assert_raise_library_error(
            lambda: scsi.unfence_node(
                self.env_assist.get_env(),
                self.node,
                self.old_devices,
                self.new_devices,
            ),
            [
                fixture.error(
                    report_codes.STONITH_UNFENCING_FAILED, reason=err_msg
                )
            ],
            expected_in_processor=False,
        )

    def test_device_status_failed(self):
        err_msg = "stderr"
        new_devices = ["device1", "device2", "device3", "device4"]
        old_devices = new_devices[:-1]
        ok_devices = new_devices[0:2]
        err_device = new_devices[2]
        for dev in ok_devices:
            self.config.runner.scsi.get_status(
                self.node, dev, name=f"runner.scsi.is_fenced.{dev}"
            )
        self.config.runner.scsi.get_status(
            self.node,
            err_device,
            name=f"runner.scsi.is_fenced.{err_device}",
            stderr=err_msg,
            return_code=1,
        )
        self.env_assist.assert_raise_library_error(
            lambda: scsi.unfence_node(
                self.env_assist.get_env(),
                self.node,
                old_devices,
                new_devices,
            ),
            [
                fixture.error(
                    report_codes.STONITH_UNFENCING_DEVICE_STATUS_FAILED,
                    device=err_device,
                    reason=err_msg,
                )
            ],
            expected_in_processor=False,
        )

    def test_unfencing_skipped_devices_are_fenced(self):
        stdout_off = "Status: OFF"
        for old_dev in self.old_devices:
            self.config.runner.scsi.get_status(
                self.node,
                old_dev,
                name=f"runner.scsi.is_fenced.{old_dev}",
                stdout=stdout_off,
                return_code=2,
            )
        scsi.unfence_node(
            self.env_assist.get_env(),
            self.node,
            self.old_devices,
            self.new_devices,
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.STONITH_UNFENCING_SKIPPED_DEVICES_FENCED,
                    devices=sorted(self.old_devices),
                )
            ]
        )
