from unittest import (
    TestCase,
    mock,
)

from pcs.common.services import errors
from pcs.common.services.drivers import OpenRcDriver
from pcs.common.services.interfaces import ExecutorInterface
from pcs.common.services.types import ExecutorResult


class Base(TestCase):
    def setUp(self):
        self.mock_executor = mock.MagicMock(spec_set=ExecutorInterface)
        self.service = "service_name"
        self.instance = "instance_name"
        self.rc_service_bin = "rc_service_bin"
        self.rc_config_bin = "rc_config_bin"
        self.driver = OpenRcDriver(
            self.mock_executor, self.rc_service_bin, self.rc_config_bin
        )


class BaseTestMixin:
    cmd = []
    exception = None
    executable = None
    driver_callback = staticmethod(lambda: None)

    def test_success(self):
        self.mock_executor.run.return_value = ExecutorResult(0, "", "")
        self.driver_callback(self.service)
        self.mock_executor.run.assert_called_once_with(
            [self.executable] + self.cmd
        )

    def test_instance_success(self):
        self.mock_executor.run.return_value = ExecutorResult(0, "", "")
        self.driver_callback(self.service, self.instance)
        self.mock_executor.run.assert_called_once_with(
            [self.executable] + self.cmd
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
            [self.executable] + self.cmd
        )

    def test_instace_failure(self):
        result = ExecutorResult(1, "stdout", "stderr")
        self.mock_executor.run.return_value = result
        with self.assertRaises(self.exception) as cm:
            self.driver_callback(self.service, self.instance)

        self.assertEqual(cm.exception.service, self.service)
        self.assertEqual(cm.exception.message, result.joined_output)
        self.assertIsNone(cm.exception.instance)
        self.mock_executor.run.assert_called_once_with(
            [self.executable] + self.cmd
        )


class StartTest(Base, BaseTestMixin):
    exception = errors.StartServiceError

    def setUp(self):
        super().setUp()
        self.driver_callback = self.driver.start
        self.executable = self.rc_service_bin
        self.cmd = [self.service, "start"]


class StopTest(Base, BaseTestMixin):
    exception = errors.StopServiceError

    def setUp(self):
        super().setUp()
        self.driver_callback = self.driver.stop
        self.executable = self.rc_service_bin
        self.cmd = [self.service, "stop"]


class EnableTest(Base, BaseTestMixin):
    exception = errors.EnableServiceError

    def setUp(self):
        super().setUp()
        self.driver_callback = self.driver.enable
        self.executable = self.rc_config_bin
        self.cmd = ["add", self.service, "default"]


class DisableTest(Base, BaseTestMixin):
    exception = errors.DisableServiceError

    def setUp(self):
        super().setUp()
        # pylint: disable=protected-access
        self.driver._available_services = [self.service]
        self.driver_callback = self.driver.disable
        self.executable = self.rc_config_bin
        self.cmd = ["delete", self.service, "default"]

    def test_not_intalled(self):
        # pylint: disable=protected-access
        self.driver._available_services = [f"not_{self.service}"]
        self.driver_callback(self.service)
        self.mock_executor.run.assert_not_called()


class IsEnabledTest(Base):
    def test_enabled(self):
        output = (
            "\n".join(
                [
                    "This line is ignored",
                    "  service1",
                    "  abc",
                    "  xyz",
                    f"  {self.service}",
                ]
            )
            + "\n"
        )
        self.mock_executor.run.return_value = ExecutorResult(0, output, "")
        self.assertTrue(self.driver.is_enabled(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.rc_config_bin, "list", "default"]
        )

    def test_instance_enabled(self):
        output = (
            "\n".join(
                [
                    "This line is ignored",
                    "  service1",
                    "  abc",
                    "  xyz",
                    f"  {self.service}",
                ]
            )
            + "\n"
        )
        self.mock_executor.run.return_value = ExecutorResult(0, output, "")
        self.assertTrue(self.driver.is_enabled(self.service, self.instance))
        self.mock_executor.run.assert_called_once_with(
            [self.rc_config_bin, "list", "default"]
        )

    def test_disabled(self):
        output = (
            "\n".join(
                [
                    "This line is ignored",
                    "  service1",
                    "  abc",
                    "  xyz",
                ]
            )
            + "\n"
        )
        self.mock_executor.run.return_value = ExecutorResult(0, output, "")
        self.assertFalse(self.driver.is_enabled(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.rc_config_bin, "list", "default"]
        )

    def test_failure(self):
        self.mock_executor.run.return_value = ExecutorResult(1, "", "")
        self.assertFalse(self.driver.is_enabled(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.rc_config_bin, "list", "default"]
        )


class IsRunningTest(Base):
    def test_running(self):
        self.mock_executor.run.return_value = ExecutorResult(
            0, "is running", ""
        )
        self.assertTrue(self.driver.is_running(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.rc_service_bin, self.service, "status"]
        )

    def test_instance_running(self):
        self.mock_executor.run.return_value = ExecutorResult(
            0, "is running", ""
        )
        self.assertTrue(self.driver.is_running(self.service, self.instance))
        self.mock_executor.run.assert_called_once_with(
            [self.rc_service_bin, self.service, "status"]
        )

    def test_not_running(self):
        self.mock_executor.run.return_value = ExecutorResult(
            3, "is stopped", ""
        )
        self.assertFalse(self.driver.is_running(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.rc_service_bin, self.service, "status"]
        )

    def test_failure(self):
        self.mock_executor.run.return_value = ExecutorResult(1, "", "error")
        self.assertFalse(self.driver.is_running(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.rc_service_bin, self.service, "status"]
        )


class IsInstalledTest(Base):
    def test_installed(self):
        output = (
            "This line is ignored\n"
            "  service1 something otherthing\n"
            "  abc something otherthing\n"
            "  xyz something otherthing\n"
            f"  {self.service} something otherthing\n"
        )
        self.mock_executor.run.return_value = ExecutorResult(0, output, "")
        self.assertTrue(self.driver.is_installed(self.service))
        # Intetionally called twice to make sure that unit files listing is
        # done only once
        self.assertTrue(self.driver.is_installed(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.rc_config_bin, "list"]
        )

    def test_not_installed(self):
        output = (
            "This line is ignored\n"
            "  service1 something otherthing\n"
            "  abc something otherthing\n"
            "  xyz something otherthing\n"
        )
        self.mock_executor.run.return_value = ExecutorResult(0, output, "")
        self.assertFalse(self.driver.is_installed(self.service))
        # Intetionally called twice to make sure that unit files listing is
        # done only once
        self.assertFalse(self.driver.is_installed(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.rc_config_bin, "list"]
        )


class GetAvailableServicesTest(Base):
    def test_success(self):
        output = (
            "This line is ignored\n"
            "  service1 something otherthing\n"
            "  abc something otherthing\n"
            "  xyz something otherthing\n"
        )
        self.mock_executor.run.return_value = ExecutorResult(0, output, "")
        self.assertEqual(
            self.driver.get_available_services(),
            ["service1", "abc", "xyz"],
        )
        self.mock_executor.run.assert_called_once_with(
            [self.rc_config_bin, "list"]
        )

    def test_failure(self):
        self.mock_executor.run.return_value = ExecutorResult(1, "", "error")
        self.assertEqual(self.driver.get_available_services(), [])
        self.mock_executor.run.assert_called_once_with(
            [self.rc_config_bin, "list"]
        )
