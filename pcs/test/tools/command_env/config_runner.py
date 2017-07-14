from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.command_env.config_runner_cib import CibShortcuts
from pcs.test.tools.command_env.config_runner_pcmk import PcmkShortcuts
from pcs.test.tools.integration_lib import Call


def show_calls(names, calls):
    return "\n".join([
        "  '{0}': {1}".format(pair[0], pair[1].command)
        for pair in zip(names, calls)
    ])

class CallCollection(object):
    def __init__(self):
        self.__call_list = []
        self.__name_list = []

    @property
    def calls(self):
        return list(self.__call_list)

    def __set(self, instead_name, name, call):
        """
        Replace call that has key instead_name with new call that has key name

        string name -- key of the call
        Call call
        string instead_name -- key of call instead of which this new call is to
            be placed
        """
        if instead_name not in self.__name_list:
            raise self.__cannot_put("instead of", instead_name, name, call)

        for i, current_name in enumerate(self.__name_list):
            if current_name == instead_name:
                self.__call_list[i] = call
                #yes we change the name as well
                self.__name_list[i] = name
                return

    def __append(self, name, call):
        """
        Append call.

        string name -- key of the call
        Call call
        """
        self.__name_list.append(name)
        self.__call_list.append(call)

    def __insert(self, before_name, name, call):
        """
        Insert call before call with before_name.

        string before_name -- key of call before which this new call is to be
            placed
        string name -- key of the call
        Call call
        """
        if before_name not in self.__name_list:
            raise self.__cannot_put("before", before_name, name, call)

        index = self.__name_list.index(before_name)
        self.__name_list.insert(index, name)
        self.__call_list.insert(index, call)

    def remove(self, name):
        """
        Remove call under key name.
        """
        try:
            index = self.__name_list.index(name)
            del self.__call_list[index]
            del self.__name_list[index]
        except ValueError:
            raise self.__name_not_exists(name)

    def get(self, name):
        """
        Get first call with name.

        string name -- key of the call
        """
        try:
            return self.__call_list[self.__name_list.index(name)]
        except ValueError:
            raise self.__name_not_exists(name)

    def place(self, name, call, before=None, instead=None):
        """
        Place call into calllist.

        string name -- key of the call
        Call call
        string before -- key of call before which this new call is to be placed
        string instead -- key of call instead of which this new call is to be
            placed
        """
        if name and name in self.__name_list and instead != name:
            raise self.__name_exists_already(name)

        if before and instead:
            raise self.__cannot_use_before_and_instead(name, call)

        if before:
            self.__insert(before, name, call)
        elif instead:
            self.__set(instead, name, call)
        else:
            self.__append(name, call)

    def __name_not_exists(self, name):
        return AssertionError(
            "Call named '{0}' does not exist. There are calls:\n{1}"
            .format(name, show_calls(self.__name_list, self.__call_list))
        )


    def __name_exists_already(self, name):
        return AssertionError(
            (
                "Name '{0}' is in this runner configuration already."
                " There are calls:\n{1}"
            )
            .format(name, show_calls(self.__name_list, self.__call_list))
        )

    def __cannot_use_before_and_instead(self, name, call):
        return AssertionError(
            "Args 'before' and 'instead' cannot be used together,"
            " call: '{0}' ({1})".format(name, call.command)
        )

    def __cannot_put(self, where_type, where_name, name, call):
        return AssertionError(
            (
                "Cannot put call named '{0}' ({1}) {2} '{3}'"
                " because '{3}' does not exist."
                " There are calls:\n{4}"
            ).format(
                name,
                call,
                where_type,
                where_name,
                show_calls(self.__name_list, self.__call_list)
            )
        )


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
