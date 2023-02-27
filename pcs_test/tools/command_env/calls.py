def format_call(call):
    if hasattr(call, "format"):
        return call.format()
    return call


def show_calls(name_list, call_list):
    return "\n".join(
        [
            "  {0}. '{1}': {2}".format(i, x[0], format_call(x[1]))
            for i, x in enumerate(zip(name_list, call_list))
        ]
    )


class Queue:
    def __init__(self, call_list_builder=None):
        if not call_list_builder:
            call_list_builder = CallListBuilder()

        self.__call_list = call_list_builder.calls
        self.__name_list = call_list_builder.names

        self.__index = 0

    def take(self, type_of_call, real_call_info=None):
        if self.__index >= len(self.__call_list):
            raise self.__extra_call(type_of_call, real_call_info)

        call = self.__call_list[self.__index]

        if call.type != type_of_call:
            raise self.__unexpected_type(call, type_of_call, real_call_info)

        self.__index += 1
        return self.__index, call

    def has_type(self, call_type):
        return any(call.type == call_type for call in self.__call_list)

    @property
    def remaining(self):
        return self.__call_list[self.__index :]

    @property
    def taken(self):
        return self.__call_list[: self.__index]

    def error_with_context(self, message):
        return AssertionError(
            "{0}\nAll calls in queue (current index={1}):\n{2}".format(
                message,
                self.__index,
                show_calls(self.__name_list, self.__call_list),
            )
        )

    def __unexpected_type(self, call, real_type, real_call_info):
        return self.error_with_context(
            (
                "{0}. call was expected as '{1}' type but was '{2}' type"
                "\n  expected call: {3}{4}"
                "\nHint: check call compatibility: for example if you use"
                " env.push_cib() then runner.cib.push() will be never launched"
            ).format(
                self.__index + 1,
                call.type,
                real_type,
                call,
                "\n  real call: {0}".format(real_call_info)
                if real_call_info
                else "",
            )
        )

    def __extra_call(self, type_of_call, real_call_info):
        return self.error_with_context(
            "No next call expected, but was ({0}):\n    '{1}'".format(
                type_of_call, real_call_info
            )
        )


class CallListBuilder:
    def __init__(self):
        self.__call_list = []
        self.__name_list = []

    @property
    def calls(self):
        return list(self.__call_list)

    @property
    def names(self):
        return list(self.__name_list)

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
                # yes we change the name as well
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
        Remove a call with the specified name
        """
        try:
            index = self.__name_list.index(name)
            del self.__call_list[index]
            del self.__name_list[index]
        except ValueError as e:
            raise self.__name_not_exists(name) from e

    def trim_before(self, name):
        """
        Remove a call with the specified name and all calls after it from the list
        """
        try:
            index = self.__name_list.index(name)
            self.__call_list = self.__call_list[:index]
            self.__name_list = self.__name_list[:index]
        except ValueError as e:
            raise self.__name_not_exists(name) from e

    def get(self, name):
        """
        Get first call with name.

        string name -- key of the call
        """
        try:
            return self.__call_list[self.__name_list.index(name)]
        except ValueError as e:
            raise self.__name_not_exists(name) from e

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
            raise self.__cannot_use_before_and_instead(
                name,
                call,
                before,
                instead,
            )

        if not hasattr(call, "type") or not call.type:
            raise self.__type_of_call_is_not_specified(call)

        if before:
            self.__insert(before, name, call)
        elif instead:
            self.__set(instead, name, call)
        else:
            self.__append(name, call)

    def __error_with_context(self, message):
        return AssertionError(
            "{0}\nCalls in the configuration call collection are:\n{1}".format(
                message,
                show_calls(self.__name_list, self.__call_list),
            )
        )

    @staticmethod
    def __type_of_call_is_not_specified(call):
        return AssertionError(
            (
                "Class {0}.{1} must have the attribute 'type' with no-falsy "
                "value."
            ).format(call.__module__, call.__class__.__name__)
        )

    def __name_not_exists(self, name):
        return self.__error_with_context(
            "Call named '{0}' does not exist.".format(name)
        )

    def __name_exists_already(self, name):
        return self.__error_with_context(
            "Name '{0}' is in this configuration already.".format(name)
        )

    def __cannot_use_before_and_instead(self, name, call, before, instead):
        return self.__error_with_context(
            (
                "Args 'before' ({0}) and 'instead' ({1}) cannot be used"
                " together\n  '{2}': {3}"
            ).format(before, instead, name, call)
        )

    def __cannot_put(self, where_type, where_name, name, call):
        return self.__error_with_context(
            (
                "Cannot put call named '{0}' ({1}) {2} '{3}'"
                " because '{3}' does not exist."
            ).format(
                name,
                call,
                where_type,
                where_name,
            )
        )
