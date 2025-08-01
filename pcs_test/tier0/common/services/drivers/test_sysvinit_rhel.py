from unittest import (
    TestCase,
    mock,
)

from pcs.common.services import errors
from pcs.common.services.drivers import SysVInitRhelDriver
from pcs.common.services.interfaces import ExecutorInterface
from pcs.common.services.types import ExecutorResult


class Base(TestCase):
    def setUp(self):
        self.mock_executor = mock.MagicMock(spec_set=ExecutorInterface)
        self.service = "service_name"
        self.instance = "instance_name"
        self.service_bin = "service_bin"
        self.chkconfig_bin = "chkconfig_bin"
        self.driver = SysVInitRhelDriver(
            self.mock_executor, self.service_bin, self.chkconfig_bin
        )


class BaseTestMixin:
    subcmd = None
    exception = None
    executable = None
    driver_callback = staticmethod(lambda: None)

    def test_success(self):
        self.mock_executor.run.return_value = ExecutorResult(0, "", "")
        self.driver_callback(self.service)
        self.mock_executor.run.assert_called_once_with(
            [self.executable, self.service, self.subcmd]
        )

    def test_instance_success(self):
        self.mock_executor.run.return_value = ExecutorResult(0, "", "")
        self.driver_callback(self.service, self.instance)
        self.mock_executor.run.assert_called_once_with(
            [self.executable, self.service, self.subcmd]
        )

    def test_failure(self):
        result = ExecutorResult(1, "stdout", "stderr")
        self.mock_executor.run.return_value = result
        with self.assertRaises(self.exception) as cm:
            self.driver_callback(self.service)

        self.assertEqual(cm.exception.service, self.service)
        self.assertEqual(cm.exception.message, result.joined_output)
        self.assertIsNone(cm.exception.instance)
        self.mock_executor.run.assert_called_once_with(
            [self.executable, self.service, self.subcmd]
        )

    def test_instance_failure(self):
        result = ExecutorResult(1, "stdout", "stderr")
        self.mock_executor.run.return_value = result
        with self.assertRaises(self.exception) as cm:
            self.driver_callback(self.service, self.instance)

        self.assertEqual(cm.exception.service, self.service)
        self.assertEqual(cm.exception.message, result.joined_output)
        self.assertIsNone(cm.exception.instance)
        self.mock_executor.run.assert_called_once_with(
            [self.executable, self.service, self.subcmd]
        )


class StartTest(Base, BaseTestMixin):
    subcmd = "start"
    exception = errors.StartServiceError

    def setUp(self):
        super().setUp()
        self.driver_callback = self.driver.start
        self.executable = self.service_bin


class StopTest(Base, BaseTestMixin):
    subcmd = "stop"
    exception = errors.StopServiceError

    def setUp(self):
        super().setUp()
        self.driver_callback = self.driver.stop
        self.executable = self.service_bin


class EnableTest(Base, BaseTestMixin):
    subcmd = "on"
    exception = errors.EnableServiceError

    def setUp(self):
        super().setUp()
        self.driver_callback = self.driver.enable
        self.executable = self.chkconfig_bin


class DisableTest(Base, BaseTestMixin):
    subcmd = "off"
    exception = errors.DisableServiceError

    def setUp(self):
        super().setUp()
        # pylint: disable=protected-access
        self.driver._available_services = [self.service]
        self.driver_callback = self.driver.disable
        self.executable = self.chkconfig_bin

    def test_not_installed(self):
        # pylint: disable=protected-access
        self.driver._available_services = [f"not_{self.service}"]
        self.driver_callback(self.service)
        self.mock_executor.run.assert_not_called()


class IsEnabledTest(Base):
    def test_enabled(self):
        self.mock_executor.run.return_value = ExecutorResult(0, "", "")
        self.assertTrue(self.driver.is_enabled(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.chkconfig_bin, self.service]
        )

    def test_instance_enabled(self):
        self.mock_executor.run.return_value = ExecutorResult(0, "", "")
        self.assertTrue(self.driver.is_enabled(self.service, self.instance))
        self.mock_executor.run.assert_called_once_with(
            [self.chkconfig_bin, self.service]
        )

    def test_disabled(self):
        self.mock_executor.run.return_value = ExecutorResult(3, "", "")
        self.assertFalse(self.driver.is_enabled(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.chkconfig_bin, self.service]
        )

    def test_failure(self):
        self.mock_executor.run.return_value = ExecutorResult(1, "", "")
        self.assertFalse(self.driver.is_enabled(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.chkconfig_bin, self.service]
        )


class IsRunningTest(Base):
    def test_running(self):
        self.mock_executor.run.return_value = ExecutorResult(
            0, "is running", ""
        )
        self.assertTrue(self.driver.is_running(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.service_bin, self.service, "status"]
        )

    def test_instance_running(self):
        self.mock_executor.run.return_value = ExecutorResult(
            0, "is running", ""
        )
        self.assertTrue(self.driver.is_running(self.service, self.instance))
        self.mock_executor.run.assert_called_once_with(
            [self.service_bin, self.service, "status"]
        )

    def test_not_running(self):
        self.mock_executor.run.return_value = ExecutorResult(
            3, "is stopped", ""
        )
        self.assertFalse(self.driver.is_running(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.service_bin, self.service, "status"]
        )

    def test_failure(self):
        self.mock_executor.run.return_value = ExecutorResult(1, "", "error")
        self.assertFalse(self.driver.is_running(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.service_bin, self.service, "status"]
        )


class IsInstalledTest(Base):
    def test_installed(self):
        output = (
            "service1       	0:off	1:off	2:on	3:on	4:on	5:on	6:off\n"
            "abc            	0:off	1:on	2:on	3:on	4:on	5:on	6:off\n"
            "xyz            	0:off	1:off	2:off	3:off	4:off	5:off	6:off\n"
            f"{self.service}        	0:off	1:off	2:on	3:on	4:on	5:on	6:off\n"
        )
        self.mock_executor.run.return_value = ExecutorResult(0, output, "")
        self.assertTrue(self.driver.is_installed(self.service))
        # Intetionally called twice to make sure that unit files listing is
        # done only once
        self.assertTrue(self.driver.is_installed(self.service))
        self.mock_executor.run.assert_called_once_with([self.chkconfig_bin])

    def test_not_installed(self):
        output = (
            "service1       	0:off	1:off	2:on	3:on	4:on	5:on	6:off\n"
            "abc            	0:off	1:on	2:on	3:on	4:on	5:on	6:off\n"
            "xyz            	0:off	1:off	2:off	3:off	4:off	5:off	6:off\n"
        )
        self.mock_executor.run.return_value = ExecutorResult(0, output, "")
        self.assertFalse(self.driver.is_installed(self.service))
        # Intetionally called twice to make sure that unit files listing is
        # done only once
        self.assertFalse(self.driver.is_installed(self.service))
        self.mock_executor.run.assert_called_once_with([self.chkconfig_bin])


class GetAvailableServicesTest(Base):
    def test_success(self):
        output = (
            "service1       	0:off	1:off	2:on	3:on	4:on	5:on	6:off\n"
            "abc            	0:off	1:on	2:on	3:on	4:on	5:on	6:off\n"
            "xyz            	0:off	1:off	2:off	3:off	4:off	5:off	6:off\n"
        )
        self.mock_executor.run.return_value = ExecutorResult(0, output, "")
        self.assertEqual(
            self.driver.get_available_services(),
            ["service1", "abc", "xyz"],
        )
        self.mock_executor.run.assert_called_once_with([self.chkconfig_bin])

    def test_failure(self):
        self.mock_executor.run.return_value = ExecutorResult(1, "", "error")
        self.assertEqual(self.driver.get_available_services(), [])
        self.mock_executor.run.assert_called_once_with([self.chkconfig_bin])
