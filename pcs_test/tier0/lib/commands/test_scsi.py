from unittest import TestCase

from pcs.common.reports import codes as report_codes
from pcs.lib.commands import scsi

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


class TestUnfenceNodeBase:
    plug = None
    fence_agent = None

    def call_function(self, *args, **kwargs):
        raise NotImplementedError()

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.old_devices = ["device1", "device3"]
        self.new_devices = ["device3", "device0", "device2"]
        self.added_devices = set(self.new_devices) - set(self.old_devices)
        self.check_devices = sorted(
            set(self.old_devices) & set(self.new_devices)
        )

    def test_success_devices_to_unfence(self):
        for old_dev in self.check_devices:
            self.config.runner.scsi.get_status(
                self.plug,
                old_dev,
                self.fence_agent,
                name=f"runner.scsi.is_fenced.{old_dev}",
            )
        self.config.runner.scsi.unfence_node(
            self.plug, self.added_devices, self.fence_agent
        )
        self.call_function(
            self.env_assist.get_env(),
            self.plug,
            self.old_devices,
            self.new_devices,
        )
        self.env_assist.assert_reports([])

    def test_success_no_devices_to_unfence(self):
        self.call_function(
            self.env_assist.get_env(),
            self.plug,
            {"device1", "device2", "device3"},
            {"device3"},
        )
        self.env_assist.assert_reports([])

    def test_success_replace_unavailable_device(self):
        self.config.runner.scsi.unfence_node(
            self.plug, {"device2"}, self.fence_agent
        )
        self.call_function(
            self.env_assist.get_env(),
            self.plug,
            {"device1"},
            {"device2"},
        )
        self.env_assist.assert_reports([])

    def test_unfencing_failure(self):
        err_msg = "stderr"
        for old_dev in self.check_devices:
            self.config.runner.scsi.get_status(
                self.plug,
                old_dev,
                self.fence_agent,
                name=f"runner.scsi.is_fenced.{old_dev}",
            )
        self.config.runner.scsi.unfence_node(
            self.plug,
            self.added_devices,
            self.fence_agent,
            stderr=err_msg,
            return_code=1,
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.call_function(
                self.env_assist.get_env(),
                self.plug,
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
                self.plug,
                dev,
                self.fence_agent,
                name=f"runner.scsi.is_fenced.{dev}",
            )
        self.config.runner.scsi.get_status(
            self.plug,
            err_device,
            self.fence_agent,
            name=f"runner.scsi.is_fenced.{err_device}",
            stderr=err_msg,
            return_code=1,
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.call_function(
                self.env_assist.get_env(),
                self.plug,
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
        for old_dev in self.check_devices:
            self.config.runner.scsi.get_status(
                self.plug,
                old_dev,
                self.fence_agent,
                name=f"runner.scsi.is_fenced.{old_dev}",
                stdout=stdout_off,
                return_code=2,
            )
        self.call_function(
            self.env_assist.get_env(),
            self.plug,
            self.old_devices,
            self.new_devices,
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.STONITH_UNFENCING_SKIPPED_DEVICES_FENCED,
                    devices=sorted(self.check_devices),
                )
            ]
        )


class TestUnfenceNodeScsi(TestUnfenceNodeBase, TestCase):
    plug = "node1"
    fence_agent = "fence_scsi"

    def call_function(self, *args, **kwargs):
        scsi.unfence_node(*args, **kwargs)


class TestUnfenceNodeMpath(TestUnfenceNodeBase, TestCase):
    plug = "1"
    fence_agent = "fence_mpath"

    def call_function(self, *args, **kwargs):
        scsi.unfence_node_mpath(*args, **kwargs)
