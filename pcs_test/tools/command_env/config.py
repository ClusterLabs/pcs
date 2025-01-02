import inspect

from pcs_test.tools.command_env.calls import CallListBuilder
from pcs_test.tools.command_env.config_corosync_conf import CorosyncConf
from pcs_test.tools.command_env.config_env import EnvConfig
from pcs_test.tools.command_env.config_fs import FsConfig
from pcs_test.tools.command_env.config_http import HttpConfig
from pcs_test.tools.command_env.config_raw_file import RawFileConfig
from pcs_test.tools.command_env.config_runner import RunnerConfig
from pcs_test.tools.command_env.config_services import ServiceManagerConfig


class Spy:
    def __init__(self, known_hosts):
        self.known_hosts = known_hosts


class Config:
    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        self.__calls = CallListBuilder()
        self.runner = self.__wrap_helper(
            RunnerConfig(self.__calls, self.__wrap_helper)
        )
        self.env = self.__wrap_helper(EnvConfig(self.__calls))
        self.http = self.__wrap_helper(
            HttpConfig(self.__calls, self.__wrap_helper)
        )
        self.corosync_conf = self.__wrap_helper(CorosyncConf(self.__calls))
        # pylint: disable=invalid-name
        self.fs = self.__wrap_helper(FsConfig(self.__calls))
        self.raw_file = self.__wrap_helper(RawFileConfig(self.__calls))
        self.services = self.__wrap_helper(ServiceManagerConfig(self.__calls))

        self.spy = None

    def add_extension(self, name, Extension):  # pylint: disable=invalid-name
        if hasattr(self, name):
            raise AssertionError(
                f"Config (integration tests) has the extension '{name}' already."
            )
        setattr(
            self,
            name,
            self.__wrap_helper(
                Extension(self.__calls, self.__wrap_helper, self)
            ),
        )

    def set_spy(self, known_hosts):
        self.spy = Spy(known_hosts)
        return self

    @property
    def calls(self):
        return self.__calls

    def remove(self, name):
        """
        Remove a call with the specified name from the list
        """
        self.__calls.remove(name)
        return self

    def trim_before(self, name):
        """
        Remove a call with the specified name and all calls after it from the list
        """
        self.__calls.trim_before(name)
        return self

    def __wrap_method(self, helper, name, method):
        """
        Wrap method in helper to return self of this object

        object helper -- helper for creatig call configuration
        string name -- name of method in helper
        callable method
        """

        def wrapped_method(*args, **kwargs):
            method(helper, *args, **kwargs)
            return self

        setattr(helper, name, wrapped_method)

    def __wrap_helper(self, helper):
        """
        Wrap every public method in helper to return self of this object

        object helper -- helper for creatig call configuration
        """
        for name, attr in inspect.getmembers(helper.__class__):
            if not name.startswith("_") and callable(attr):
                self.__wrap_method(helper, name, attr)
        return helper
