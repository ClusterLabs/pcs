from typing import (
    Any,
    NamedTuple,
    Optional,
)

from pcs.common.services.interfaces.manager import ServiceManagerInterface

CALL_TYPE_SERVICE_MANAGER = "CALL_TYPE_SERVICE_MANAGER"


def opt_str(val):
    return f"'{val}'" if isinstance(val, str) else f"{val}"


class Call(NamedTuple):
    method: str
    service: str
    instance: Optional[str] = None
    return_value: Any = None
    exception: Optional[Exception] = None

    @property
    def type(self):
        return CALL_TYPE_SERVICE_MANAGER

    def __repr__(self):
        return (
            f"<ServiceManager.{self.method}() "
            f"service={opt_str(self.service)} "
            f"instance={opt_str(self.instance)} "
            f"return_value={opt_str(self.return_value)} "
            f"exception={self.exception}>"
        )


class ServiceManagerMock(ServiceManagerInterface):
    def __init__(self, call_queue=None):
        self.__call_queue = call_queue

    def _assert_call(self, method, service=None, instance=None):
        _, call = self.__call_queue.take(CALL_TYPE_SERVICE_MANAGER)
        actual_call = Call(
            method, service, instance, call.return_value, call.exception
        )
        if call != actual_call:
            raise AssertionError(
                f"Expected call:\n  {call}\nActual call:\n  {actual_call}"
            )
        if call.exception:
            raise call.exception
        return call.return_value

    def start(self, service, instance=None):
        return self._assert_call("start", service, instance)

    def stop(self, service, instance=None):
        return self._assert_call("stop", service, instance)

    def enable(self, service, instance=None):
        return self._assert_call("enable", service, instance)

    def disable(self, service, instance=None):
        return self._assert_call("disable", service, instance)

    def is_enabled(self, service, instance=None):
        return self._assert_call("is_enabled", service, instance)

    def is_running(self, service, instance=None):
        return self._assert_call("is_running", service, instance)

    def is_installed(self, service):
        return self._assert_call("is_installed", service)

    def get_available_services(self):
        return self._assert_call("get_available_services")

    def is_current_system_supported(self):
        return self._assert_call("is_current_system_supported")
