from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.command_env.config_runner_cib import CibShortcuts
from pcs.test.tools.command_env.config_runner_pcmk import PcmkShortcuts
from pcs.test.tools.integration_lib import Call


class RunnerConfig(object):
    def __init__(self, call_collection):
        self.__calls = call_collection

        self.cib = self.__wrap_helper(CibShortcuts(self.__calls))
        self.pcmk = self.__wrap_helper(PcmkShortcuts(self.__calls))

    def place(
        self, command,
        name="", stdout="", stderr="", returncode=0, check_stdin=None,
        before=None, instead=None
    ):
        """
        Place new call to a config.

        string command -- cmdline call (e.g. "crm_mon --one-shot --as-xml")
        string name -- name of the call; it is possible to get it by the method
            "get"
        string stdout -- stdout of the call
        string stderr -- stderr of the call
        int returncode -- returncode of the call
        callable check_stdin -- callable that can check if stdin is as expected
        string before -- name of another call to insert this call before it
        string instead -- name of another call to replace it by this call
        """
        call = Call(command, stdout, stderr, returncode, check_stdin)
        self.__calls.place(name, call, before, instead)
        return self

    def remove(self, name):
        """
        Remove call with specified name from list.
        """
        self.__calls.remove(name)
        return self

    def get(self, name):
        """
        Get first call with name.
        """
        return self.__calls.get(name)

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
