from unittest import (
    TestCase,
    mock,
)

from pcs.common.services import errors
from pcs.common.services.drivers import SystemdDriver
from pcs.common.services.interfaces import ExecutorInterface
from pcs.common.services.types import ExecutorResult


def service_name(service, instance=None):
    if instance:
        service += f"@{instance}"
    return f"{service}.service"


class Base(TestCase):
    def setUp(self):
        self.mock_executor = mock.MagicMock(spec_set=ExecutorInterface)
        self.service = "service_name"
        self.instance = "instance_name"
        self.binary = "path"
        self.driver = SystemdDriver(self.mock_executor, self.binary, [])


class BaseTestMixin:
    subcmd = None
    exception = None
    driver_callback = staticmethod(lambda: None)

    def test_success(self):
        self.mock_executor.run.return_value = ExecutorResult(0, "", "")
        self.driver_callback(self.service)
        self.mock_executor.run.assert_called_once_with(
            [self.binary, self.subcmd, service_name(self.service)]
        )

    def test_instance_success(self):
        self.mock_executor.run.return_value = ExecutorResult(0, "", "")
        self.driver_callback(self.service, self.instance)
        self.mock_executor.run.assert_called_once_with(
            [
                self.binary,
                self.subcmd,
                service_name(self.service, self.instance),
            ]
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
            [self.binary, self.subcmd, service_name(self.service)]
        )

    def test_instance_failure(self):
        result = ExecutorResult(1, "stdout", "stderr")
        self.mock_executor.run.return_value = result
        with self.assertRaises(self.exception) as cm:
            self.driver_callback(self.service, self.instance)

        self.assertEqual(cm.exception.service, self.service)
        self.assertEqual(cm.exception.message, result.joined_output)
        self.assertEqual(cm.exception.instance, self.instance)
        self.mock_executor.run.assert_called_once_with(
            [
                self.binary,
                self.subcmd,
                service_name(self.service, self.instance),
            ]
        )


class StartTest(Base, BaseTestMixin):
    subcmd = "start"
    exception = errors.StartServiceError

    def setUp(self):
        super().setUp()
        self.driver_callback = self.driver.start


class StopTest(Base, BaseTestMixin):
    subcmd = "stop"
    exception = errors.StopServiceError

    def setUp(self):
        super().setUp()
        self.driver_callback = self.driver.stop


class EnableTest(Base, BaseTestMixin):
    subcmd = "enable"
    exception = errors.EnableServiceError

    def setUp(self):
        super().setUp()
        self.driver_callback = self.driver.enable


class DisableTest(Base, BaseTestMixin):
    subcmd = "disable"
    exception = errors.DisableServiceError

    def setUp(self):
        super().setUp()
        # pylint: disable=protected-access
        self.driver._available_services = [self.service]
        self.driver_callback = self.driver.disable

    def test_not_installed(self):
        # pylint: disable=protected-access
        self.driver._available_services = [f"not_{self.service}"]
        self.driver_callback(self.service)
        self.mock_executor.run.assert_not_called()


class IsEnabledTest(Base):
    def test_enabled(self):
        self.mock_executor.run.return_value = ExecutorResult(0, "enabled", "")
        self.assertTrue(self.driver.is_enabled(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.binary, "is-enabled", service_name(self.service)]
        )

    def test_instance_enabled(self):
        self.mock_executor.run.return_value = ExecutorResult(0, "enabled", "")
        self.assertTrue(self.driver.is_enabled(self.service, self.instance))
        self.mock_executor.run.assert_called_once_with(
            [
                self.binary,
                "is-enabled",
                service_name(self.service, self.instance),
            ]
        )

    def test_disabled(self):
        self.mock_executor.run.return_value = ExecutorResult(1, "disabled", "")
        self.assertFalse(self.driver.is_enabled(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.binary, "is-enabled", service_name(self.service)]
        )

    def test_failure(self):
        self.mock_executor.run.return_value = ExecutorResult(1, "", "error")
        self.assertFalse(self.driver.is_enabled(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.binary, "is-enabled", service_name(self.service)]
        )


class IsRunningTest(Base):
    def test_running(self):
        self.mock_executor.run.return_value = ExecutorResult(0, "active", "")
        self.assertTrue(self.driver.is_running(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.binary, "is-active", service_name(self.service)]
        )

    def test_instance_running(self):
        self.mock_executor.run.return_value = ExecutorResult(0, "active", "")
        self.assertTrue(self.driver.is_running(self.service, self.instance))
        self.mock_executor.run.assert_called_once_with(
            [
                self.binary,
                "is-active",
                service_name(self.service, self.instance),
            ]
        )

    def test_not_running(self):
        self.mock_executor.run.return_value = ExecutorResult(3, "inactive", "")
        self.assertFalse(self.driver.is_running(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.binary, "is-active", service_name(self.service)]
        )

    def test_failure(self):
        self.mock_executor.run.return_value = ExecutorResult(1, "", "error")
        self.assertFalse(self.driver.is_running(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.binary, "is-active", service_name(self.service)]
        )


class IsInstalledTest(Base):
    def test_installed(self):
        output = (
            "service1.service        disabled\n"
            "something.target        enabled\n"
            "abc.service             enabled\n"
            "xyz.service             disabled\n"
            "serviceabcxyz.service   enabled\n"
            f"{self.service}.service disabled\n"
        )
        self.mock_executor.run.return_value = ExecutorResult(0, output, "")
        self.assertTrue(self.driver.is_installed(self.service))
        # Intetionally called twice to make sure that unit files listing is
        # done only once
        self.assertTrue(self.driver.is_installed(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.binary, "list-unit-files", "--full"]
        )

    def test_not_installed(self):
        output = (
            "service1.service        disabled\n"
            "something.target        enabled\n"
            "abc.service             enabled\n"
            "xyz.service             disabled\n"
            "serviceabcxyz.service   enabled\n"
        )
        self.mock_executor.run.return_value = ExecutorResult(0, output, "")
        self.assertFalse(self.driver.is_installed(self.service))
        # Intetionally called twice to make sure that unit files listing is
        # done only once
        self.assertFalse(self.driver.is_installed(self.service))
        self.mock_executor.run.assert_called_once_with(
            [self.binary, "list-unit-files", "--full"]
        )


class GetAvailableServicesTest(Base):
    def test_success(self):
        output = (
            "service1.service        disabled\n"
            "something.target        enabled\n"
            "abc.service             enabled\n"
            "xyz.service             disabled\n"
            "serviceabcxyz.service   enabled\n"
        )
        self.mock_executor.run.return_value = ExecutorResult(0, output, "")
        self.assertEqual(
            self.driver.get_available_services(),
            ["service1", "abc", "xyz", "serviceabcxyz"],
        )
        self.mock_executor.run.assert_called_once_with(
            [self.binary, "list-unit-files", "--full"]
        )

    def test_failure(self):
        self.mock_executor.run.return_value = ExecutorResult(1, "", "error")
        self.assertEqual(self.driver.get_available_services(), [])
        self.mock_executor.run.assert_called_once_with(
            [self.binary, "list-unit-files", "--full"]
        )
