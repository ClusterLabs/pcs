from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.command_env.config_runner import  RunnerConfig

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


class Config(object):
    def __init__(self, runner=None):
        self.__runner_calls = CallCollection()
        self.runner = runner if runner else RunnerConfig(self.__runner_calls)

    @property
    def runner_calls(self):
        return self.__runner_calls.calls
