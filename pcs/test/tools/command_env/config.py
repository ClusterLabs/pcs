from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.command_env.calls import CallListBuilder
from pcs.test.tools.command_env.config_env import EnvConfig
from pcs.test.tools.command_env.config_corosync_conf import CorosyncConf
from pcs.test.tools.command_env.config_runner import RunnerConfig
from pcs.test.tools.command_env.config_http import HttpConfig
from pcs.test.tools.command_env.config_fs import FsConfig

class Spy(object):
    def __init__(self, auth_tokens, ports=None):
        self.auth_tokens = auth_tokens
        self.ports = ports

class Config(object):
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
        self.fs = self.__wrap_helper(FsConfig(self.__calls))

        self.spy = None

    def add_extension(self, name, Extension):
        if hasattr(self, name):
            raise AssertionError(
                "Config (integration tests) has the extension '{0}' already."
                .format(name)
            )
        setattr(self, name, self.__wrap_helper(
            Extension(self.__calls, self.__wrap_helper, self)
        ))


    def set_spy(self, auth_tokens, ports=None):
        self.spy = Spy(auth_tokens, ports)
        return self

    @property
    def calls(self):
        return self.__calls

    def remove(self, name):
        """
        Remove call with specified name from list.
        """
        self.__calls.remove(name)
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
        for name, attr in helper.__class__.__dict__.items():
            if not name.startswith("_") and hasattr(attr, "__call__"):
                self.__wrap_method(helper, name, attr)
        return helper
