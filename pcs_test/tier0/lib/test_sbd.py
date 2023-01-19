from unittest import (
    TestCase,
    mock,
)

import pcs.lib.sbd as lib_sbd
from pcs import settings
from pcs.common import reports
from pcs.common.reports import ReportItemSeverity as Severities
from pcs.common.reports import codes as report_codes
from pcs.lib.corosync.config_facade import ConfigFacade as CorosyncConfigFacade
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner

from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs_test.tools.custom_mock import MockLibraryReportProcessor
from pcs_test.tools.misc import outdent


class TestException(Exception):
    pass


class EvenNumberOfNodesAndNoQdevice(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.mock_corosync_conf = mock.MagicMock(spec_set=CorosyncConfigFacade)

    def _set_ret_vals(self, nodes, qdevice):
        self.mock_corosync_conf.get_nodes.return_value = nodes
        self.mock_corosync_conf.get_quorum_device_model.return_value = (
            "net" if qdevice else None
        )

    def test_even_num_no_qdevice(self):
        self._set_ret_vals([1, 2], False)
        self.assertTrue(
            lib_sbd._even_number_of_nodes_and_no_qdevice(
                self.mock_corosync_conf
            )
        )

    def test_even_num_qdevice(self):
        self._set_ret_vals([1, 2], True)
        self.assertFalse(
            lib_sbd._even_number_of_nodes_and_no_qdevice(
                self.mock_corosync_conf
            )
        )

    def test_odd_num_no_qdevice(self):
        self._set_ret_vals([1, 2, 3], False)
        self.assertFalse(
            lib_sbd._even_number_of_nodes_and_no_qdevice(
                self.mock_corosync_conf
            )
        )

    def test_odd_num_qdevice(self):
        self._set_ret_vals([1, 2, 3], True)
        self.assertFalse(
            lib_sbd._even_number_of_nodes_and_no_qdevice(
                self.mock_corosync_conf
            )
        )

    def test_even_num_no_qdevice_plus_one(self):
        self._set_ret_vals([1, 2], False)
        self.assertFalse(
            lib_sbd._even_number_of_nodes_and_no_qdevice(
                self.mock_corosync_conf, 1
            )
        )

    def test_even_num_qdevice_plus_one(self):
        self._set_ret_vals([1, 2], True)
        self.assertFalse(
            lib_sbd._even_number_of_nodes_and_no_qdevice(
                self.mock_corosync_conf, 1
            )
        )

    def test_odd_num_no_qdevice_plus_one(self):
        self._set_ret_vals([1, 2, 3], False)
        self.assertTrue(
            lib_sbd._even_number_of_nodes_and_no_qdevice(
                self.mock_corosync_conf, 1
            )
        )

    def test_odd_num_qdevice_plus_one(self):
        self._set_ret_vals([1, 2, 3], True)
        self.assertFalse(
            lib_sbd._even_number_of_nodes_and_no_qdevice(
                self.mock_corosync_conf, 1
            )
        )


@mock.patch("pcs.lib.sbd._is_device_set_local")
@mock.patch("pcs.lib.sbd.is_sbd_enabled")
@mock.patch("pcs.lib.sbd.is_sbd_installed")
@mock.patch("pcs.lib.sbd._even_number_of_nodes_and_no_qdevice")
class IsAutoTieBreakerNeededTest(TestCase):
    def setUp(self):
        self.runner = "runner"
        self.corosync_conf_facade = "facade"
        self.node_num_modifier = 1
        self.mock_nodes_and_qdevice = None
        self.mock_sbd_installed = None
        self.mock_sbd_enabled = None
        self.mock_device_set = None

    def set_mocks(
        self,
        mock_nodes_and_qdevice,
        mock_sbd_installed,
        mock_sbd_enabled,
        mock_device_set,
    ):
        self.mock_nodes_and_qdevice = mock_nodes_and_qdevice
        self.mock_sbd_installed = mock_sbd_installed
        self.mock_sbd_enabled = mock_sbd_enabled
        self.mock_device_set = mock_device_set

    def common_test(
        self, nodes_and_qdevice, sbd_installed, sbd_enabled, device_set, result
    ):
        self.mock_nodes_and_qdevice.return_value = nodes_and_qdevice
        self.mock_sbd_installed.return_value = sbd_installed
        self.mock_sbd_enabled.return_value = sbd_enabled
        self.mock_device_set.return_value = device_set
        self.assertEqual(
            lib_sbd.is_auto_tie_breaker_needed(
                self.runner, self.corosync_conf_facade, self.node_num_modifier
            ),
            result,
        )
        self.mock_nodes_and_qdevice.assert_called_once_with(
            self.corosync_conf_facade, self.node_num_modifier
        )

    def test_device_set(
        self,
        mock_nodes_and_qdevice,
        mock_sbd_installed,
        mock_sbd_enabled,
        mock_device_set,
    ):
        self.set_mocks(
            mock_nodes_and_qdevice,
            mock_sbd_installed,
            mock_sbd_enabled,
            mock_device_set,
        )
        self.common_test(True, True, True, True, False)

    def test_no_device(
        self,
        mock_nodes_and_qdevice,
        mock_sbd_installed,
        mock_sbd_enabled,
        mock_device_set,
    ):
        self.set_mocks(
            mock_nodes_and_qdevice,
            mock_sbd_installed,
            mock_sbd_enabled,
            mock_device_set,
        )
        self.common_test(True, True, True, False, True)

    def test_no_device_with_qdevice(
        self,
        mock_nodes_and_qdevice,
        mock_sbd_installed,
        mock_sbd_enabled,
        mock_device_set,
    ):
        self.set_mocks(
            mock_nodes_and_qdevice,
            mock_sbd_installed,
            mock_sbd_enabled,
            mock_device_set,
        )
        self.common_test(False, True, True, False, False)

    def test_sbd_disabled(
        self,
        mock_nodes_and_qdevice,
        mock_sbd_installed,
        mock_sbd_enabled,
        mock_device_set,
    ):
        self.set_mocks(
            mock_nodes_and_qdevice,
            mock_sbd_installed,
            mock_sbd_enabled,
            mock_device_set,
        )
        self.common_test(True, True, False, False, False)


@mock.patch("pcs.lib.sbd.is_auto_tie_breaker_needed")
class AtbHasToBeEnabledTest(TestCase):
    def setUp(self):
        self.mock_service_manager = "service manager mock"
        self.mock_conf = mock.MagicMock(spec_set=CorosyncConfigFacade)

    def test_atb_needed_is_enabled(self, mock_is_needed):
        mock_is_needed.return_value = True
        self.mock_conf.is_enabled_auto_tie_breaker.return_value = True
        self.assertFalse(
            lib_sbd.atb_has_to_be_enabled(
                self.mock_service_manager, self.mock_conf, 1
            )
        )
        self.mock_conf.is_enabled_auto_tie_breaker.assert_called_once_with()
        mock_is_needed.assert_not_called()

    def test_atb_needed_is_disabled(self, mock_is_needed):
        mock_is_needed.return_value = True
        self.mock_conf.is_enabled_auto_tie_breaker.return_value = False
        self.assertTrue(
            lib_sbd.atb_has_to_be_enabled(
                self.mock_service_manager, self.mock_conf, -1
            )
        )
        self.mock_conf.is_enabled_auto_tie_breaker.assert_called_once_with()
        mock_is_needed.assert_called_once_with(
            self.mock_service_manager, self.mock_conf, -1
        )

    def test_atb_not_needed_is_enabled(self, mock_is_needed):
        mock_is_needed.return_value = False
        self.mock_conf.is_enabled_auto_tie_breaker.return_value = True
        self.assertFalse(
            lib_sbd.atb_has_to_be_enabled(
                self.mock_service_manager, self.mock_conf, 2
            )
        )
        self.mock_conf.is_enabled_auto_tie_breaker.assert_called_once_with()
        mock_is_needed.assert_not_called()

    def test_atb_not_needed_is_disabled(self, mock_is_needed):
        mock_is_needed.return_value = False
        self.mock_conf.is_enabled_auto_tie_breaker.return_value = False
        self.assertFalse(
            lib_sbd.atb_has_to_be_enabled(
                self.mock_service_manager, self.mock_conf, -2
            )
        )
        self.mock_conf.is_enabled_auto_tie_breaker.assert_called_once_with()
        mock_is_needed.assert_called_once_with(
            self.mock_service_manager, self.mock_conf, -2
        )


@mock.patch("pcs.lib.sbd.is_systemd")
class GetSbdServiceNameTest(TestCase):
    def setUp(self):
        self.service_manager = mock.MagicMock()

    def test_systemctl(self, mock_is_systemd):
        mock_is_systemd.return_value = True
        self.assertEqual(
            "sbd", lib_sbd.get_sbd_service_name(self.service_manager)
        )
        mock_is_systemd.assert_called_once_with(self.service_manager)

    def test_not_systemctl(self, mock_is_systemd):
        mock_is_systemd.return_value = False
        self.assertEqual(
            "sbd_helper", lib_sbd.get_sbd_service_name(self.service_manager)
        )
        mock_is_systemd.assert_called_once_with(self.service_manager)


@mock.patch("pcs.lib.sbd.get_sbd_service_name")
class IsSbdEnabledTest(TestCase):
    def test_success(self, mock_sbd_name):
        mock_obj = mock.MagicMock()
        mock_obj.is_enabled.return_value = True
        service = "sbd"
        mock_sbd_name.return_value = service
        self.assertTrue(lib_sbd.is_sbd_enabled(mock_obj))
        mock_obj.is_enabled.assert_called_once_with(service)
        mock_sbd_name.assert_called_once_with(mock_obj)


@mock.patch("pcs.lib.sbd.get_sbd_service_name")
class IsSbdInstalledTest(TestCase):
    def setUp(self):
        self.service = "sbd"

    def test_installed(self, mock_sbd_name):
        mock_obj = mock.MagicMock()
        mock_obj.is_installed.return_value = True
        mock_sbd_name.return_value = self.service
        self.assertTrue(lib_sbd.is_sbd_installed(mock_obj))
        mock_obj.is_installed.assert_called_once_with(self.service)
        mock_sbd_name.assert_called_once_with(mock_obj)

    def test_not_installed(self, mock_sbd_name):
        mock_obj = mock.MagicMock()
        mock_obj.is_installed.return_value = False
        mock_sbd_name.return_value = self.service
        self.assertFalse(lib_sbd.is_sbd_installed(mock_obj))
        mock_obj.is_installed.assert_called_once_with(self.service)
        mock_sbd_name.assert_called_once_with(mock_obj)


class InitializeBlockDeviceTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock()
        self.mock_rep = MockLibraryReportProcessor()

    def test_success(self):
        device_list = ["/dev/sdb", "/dev/vda"]
        option_dict = {
            "watchdog-timeout": "10",  # -1
            "loop-timeout": "1",  # -3
        }
        self.mock_runner.run.return_value = "", "", 0
        lib_sbd.initialize_block_devices(
            self.mock_rep, self.mock_runner, device_list, option_dict
        )
        cmd = [
            settings.sbd_binary,
            "-d",
            "/dev/sdb",
            "-d",
            "/dev/vda",
            "-3",
            "1",
            "-1",
            "10",
            "create",
        ]
        self.mock_runner.run.assert_called_once_with(cmd)
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [
                (
                    Severities.INFO,
                    report_codes.SBD_DEVICE_INITIALIZATION_STARTED,
                    {"device_list": device_list},
                ),
                (
                    Severities.INFO,
                    report_codes.SBD_DEVICE_INITIALIZATION_SUCCESS,
                    {"device_list": device_list},
                ),
            ],
        )

    def test_failed(self):
        device_list = ["/dev/sdb", "/dev/vda"]
        option_dict = {
            "watchdog-timeout": "10",  # -1
            "loop-timeout": "1",  # -3
        }
        error_msg = "error"
        self.mock_runner.run.return_value = "", error_msg, 1
        assert_raise_library_error(
            lambda: lib_sbd.initialize_block_devices(
                self.mock_rep, self.mock_runner, device_list, option_dict
            ),
            (
                Severities.ERROR,
                report_codes.SBD_DEVICE_INITIALIZATION_ERROR,
                {
                    "device_list": device_list,
                    "reason": error_msg,
                },
            ),
        )
        cmd = [
            settings.sbd_binary,
            "-d",
            "/dev/sdb",
            "-d",
            "/dev/vda",
            "-3",
            "1",
            "-1",
            "10",
            "create",
        ]
        self.mock_runner.run.assert_called_once_with(cmd)
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [
                (
                    Severities.INFO,
                    report_codes.SBD_DEVICE_INITIALIZATION_STARTED,
                    {"device_list": device_list},
                )
            ],
        )


@mock.patch("os.path.exists")
@mock.patch("pcs.lib.sbd.get_local_sbd_config")
class GetLocalSbdDeviceListTest(TestCase):
    def test_device_not_defined(self, mock_sbd_config, mock_config_exists):
        mock_config_exists.return_value = True
        mock_sbd_config.return_value = outdent(
            """
            SBD_WATCHDOG=/dev/watchdog
            SBD_WATCHDOG_TIMEOUT=10
        """
        )
        self.assertEqual([], lib_sbd.get_local_sbd_device_list())
        mock_config_exists.assert_called_once_with(settings.sbd_config)
        mock_sbd_config.assert_called_once_with()

    def test_no_device(self, mock_sbd_config, mock_config_exists):
        mock_config_exists.return_value = True
        mock_sbd_config.return_value = outdent(
            """
            SBD_WATCHDOG=/dev/watchdog
            SBD_WATCHDOG_TIMEOUT=10
            SBD_DEVICE=""
        """
        )
        self.assertEqual([], lib_sbd.get_local_sbd_device_list())
        mock_config_exists.assert_called_once_with(settings.sbd_config)
        mock_sbd_config.assert_called_once_with()

    def test_one_device(self, mock_sbd_config, mock_config_exists):
        mock_config_exists.return_value = True
        mock_sbd_config.return_value = outdent(
            """
            SBD_WATCHDOG=/dev/watchdog
            SBD_WATCHDOG_TIMEOUT=10
            SBD_DEVICE="/dev/vda"
        """
        )
        self.assertEqual(["/dev/vda"], lib_sbd.get_local_sbd_device_list())
        mock_config_exists.assert_called_once_with(settings.sbd_config)
        mock_sbd_config.assert_called_once_with()

    def test_multiple_devices(self, mock_sbd_config, mock_config_exists):
        mock_config_exists.return_value = True
        mock_sbd_config.return_value = outdent(
            """
            SBD_WATCHDOG=/dev/watchdog
            SBD_WATCHDOG_TIMEOUT=10
            SBD_DEVICE="/dev/vda;/dev/sda"
        """
        )
        self.assertEqual(
            ["/dev/vda", "/dev/sda"], lib_sbd.get_local_sbd_device_list()
        )
        mock_config_exists.assert_called_once_with(settings.sbd_config)
        mock_sbd_config.assert_called_once_with()

    def test_config_does_not_exist(self, mock_sbd_config, mock_config_exists):
        mock_config_exists.return_value = False
        self.assertEqual([], lib_sbd.get_local_sbd_device_list())
        mock_config_exists.assert_called_once_with(settings.sbd_config)
        self.assertEqual(0, mock_sbd_config.call_count)

    def test_config_read_error(self, mock_sbd_config, mock_config_exists):
        # pylint: disable=no-self-use
        mock_config_exists.return_value = True
        node = "local node"
        error = "error string"
        mock_sbd_config.side_effect = LibraryError(
            reports.item.ReportItem.error(
                reports.messages.UnableToGetSbdConfig(node, error)
            )
        )
        assert_raise_library_error(
            lib_sbd.get_local_sbd_device_list,
            (
                Severities.ERROR,
                report_codes.UNABLE_TO_GET_SBD_CONFIG,
                {
                    "node": node,
                    "reason": error,
                },
            ),
        )
        mock_config_exists.assert_called_once_with(settings.sbd_config)
        mock_sbd_config.assert_called_once_with()


@mock.patch("pcs.lib.sbd.get_local_sbd_device_list")
class IsDeviceSetLocalTest(TestCase):
    # pylint: disable=protected-access
    def test_no_device(self, mock_device_list):
        mock_device_list.return_value = []
        self.assertFalse(lib_sbd._is_device_set_local())
        mock_device_list.assert_called_once_with()

    def test_one_device(self, mock_device_list):
        mock_device_list.return_value = ["device1"]
        self.assertTrue(lib_sbd._is_device_set_local())
        mock_device_list.assert_called_once_with()

    def test_multiple_devices(self, mock_device_list):
        mock_device_list.return_value = ["device1", "device2"]
        self.assertTrue(lib_sbd._is_device_set_local())
        mock_device_list.assert_called_once_with()


class GetDeviceMessagesInfoTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def test_success(self):
        output = "out"
        device = "device"
        self.mock_runner.run.return_value = output, "", 0
        self.assertEqual(
            output, lib_sbd.get_device_messages_info(self.mock_runner, device)
        )
        self.mock_runner.run.assert_called_once_with(
            [settings.sbd_binary, "-d", device, "list"]
        )

    def test_failed(self):
        output = "out"
        device = "device"
        self.mock_runner.run.return_value = output, "", 1
        assert_raise_library_error(
            lambda: lib_sbd.get_device_messages_info(self.mock_runner, device),
            (
                Severities.ERROR,
                report_codes.SBD_DEVICE_LIST_ERROR,
                {
                    "device": device,
                    "reason": output,
                },
            ),
        )
        self.mock_runner.run.assert_called_once_with(
            [settings.sbd_binary, "-d", device, "list"]
        )


class GetDeviceSbdHeaderDumpTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def test_success(self):
        output = "out"
        device = "device"
        self.mock_runner.run.return_value = output, "", 0
        self.assertEqual(
            output, lib_sbd.get_device_sbd_header_dump(self.mock_runner, device)
        )
        self.mock_runner.run.assert_called_once_with(
            [settings.sbd_binary, "-d", device, "dump"]
        )

    def test_failed(self):
        output = "out"
        device = "device"
        self.mock_runner.run.return_value = output, "", 1
        assert_raise_library_error(
            lambda: lib_sbd.get_device_sbd_header_dump(
                self.mock_runner, device
            ),
            (
                Severities.ERROR,
                report_codes.SBD_DEVICE_DUMP_ERROR,
                {
                    "device": device,
                    "reason": output,
                },
            ),
        )
        self.mock_runner.run.assert_called_once_with(
            [settings.sbd_binary, "-d", device, "dump"]
        )


class SetMessageTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def test_success(self):
        self.mock_runner.run.return_value = "", "", 0
        lib_sbd.set_message(self.mock_runner, "device", "node", "test")
        self.mock_runner.run.assert_called_once_with(
            [settings.sbd_binary, "-d", "device", "message", "node", "test"]
        )

    def test_failure(self):
        error = "error"
        self.mock_runner.run.return_value = "", error, 1
        assert_raise_library_error(
            lambda: lib_sbd.set_message(
                self.mock_runner, "device", "node", "test"
            ),
            (
                Severities.ERROR,
                report_codes.SBD_DEVICE_MESSAGE_ERROR,
                {
                    "device": "device",
                    "node": "node",
                    "sbd_message": "test",
                    "reason": error,
                },
            ),
        )
        self.mock_runner.run.assert_called_once_with(
            [settings.sbd_binary, "-d", "device", "message", "node", "test"]
        )


class ValidateDeviceDictTest(TestCase):
    def test_all_ok(self):
        device_dict = {
            "node1": ["/dev1", "/dev2"],
            "node2": ["/dev1"],
        }
        self.assertEqual([], lib_sbd.validate_nodes_devices(device_dict))

    def test_some_not_ok(self):
        # pylint: disable=no-self-use
        too_many_devices = [
            "/dev" + str(i) for i in range(settings.sbd_max_device_num)
        ] + ["dev/sda2"]
        device_dict = {
            "node1": [],
            "node2": too_many_devices,
            "node3": ["/dev/vda"],
            "node4": ["/dev/vda1", "../dev/sda2"],
        }
        assert_report_item_list_equal(
            lib_sbd.validate_nodes_devices(device_dict),
            [
                (
                    Severities.ERROR,
                    report_codes.SBD_NO_DEVICE_FOR_NODE,
                    {
                        "node": "node1",
                        "sbd_enabled_in_cluster": False,
                    },
                ),
                (
                    Severities.ERROR,
                    report_codes.SBD_TOO_MANY_DEVICES_FOR_NODE,
                    {
                        "node": "node2",
                        "device_list": too_many_devices,
                        "max_devices": settings.sbd_max_device_num,
                    },
                ),
                (
                    Severities.ERROR,
                    report_codes.SBD_DEVICE_PATH_NOT_ABSOLUTE,
                    {
                        "node": "node2",
                        "device": "dev/sda2",
                    },
                ),
                (
                    Severities.ERROR,
                    report_codes.SBD_DEVICE_PATH_NOT_ABSOLUTE,
                    {
                        "node": "node4",
                        "device": "../dev/sda2",
                    },
                ),
            ],
        )


class GetAvailableWatchdogs(TestCase):
    """
    Tested in pcs_test.tier0.lib.commands.sbd.test_watchdog_list
    """
