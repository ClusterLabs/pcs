from collections import Counter
from collections.abc import Set
from functools import partial
from typing import (
    Mapping,
    Union,
    cast,
)

from pcs.cli.common.errors import (
    SEE_MAN_CHANGES,
    CmdLineInputError,
)
from pcs.common.str_tools import (
    format_list,
    format_plural,
)
from pcs.common.tools import timeout_to_seconds
from pcs.common.types import (
    StringIterable,
    StringSequence,
)

ModifierValueType = Union[None, bool, str]

_OUTPUT_FORMAT_OPTION_STR = "output-format"
_OUTPUT_FORMAT_OPTION = f"--{_OUTPUT_FORMAT_OPTION_STR}"
OUTPUT_FORMAT_VALUE_TEXT = "text"
_OUTPUT_FORMAT_VALUES = frozenset((OUTPUT_FORMAT_VALUE_TEXT, "cmd", "json"))

ARG_TYPE_DELIMITER = "%"

# h = help, f = file,
# p = password (cluster auth), u = user (cluster auth),
PCS_SHORT_OPTIONS = "hf:p:u:"
PCS_LONG_OPTIONS = [
    "debug",
    "version",
    "help",
    "fullhelp",
    "force",
    "skip-offline",
    "autodelete",
    "simulate",
    "all",
    "full",
    "local",
    "wait",
    "config",
    "start",
    "enable",
    "disabled",
    "off",
    "request-timeout=",
    "brief",
    # resource (safe-)disable
    "safe",
    "no-strict",
    # resource cleanup | refresh
    "strict",
    "pacemaker",
    "corosync",
    "no-default-ops",
    "defaults",
    "nodesc",
    "master",  # deprecated, replaced by --promoted
    "promoted",
    "name=",
    "group=",
    "node=",
    "from=",
    "to=",
    "after=",
    "before=",
    "corosync_conf=",
    "booth-conf=",
    "booth-key=",
    "no-watchdog-validation",
    # pcs cluster setup
    "no-cluster-uuid",
    "no-keys-sync",
    # in pcs status - do not display resource status on inactive node
    "hide-inactive",
    # pcs resource (un)manage - enable or disable monitor operations
    "monitor",
    # TODO remove
    # used only in deprecated 'pcs resource|stonith show'
    "groups",
    # "pcs resource clear --expired" - only clear expired moves and bans
    "expired",
    # disable evaluating whether rules are expired
    "no-expire-check",
    # allow overwriting existing files, currently meant for / used in CLI only
    "overwrite",
    # output format of commands, e.g: json, cmd, text, ...
    f"{_OUTPUT_FORMAT_OPTION_STR}=",
    # auth token
    "token=",
    # enable agent self validation
    "agent-validation",
]


def split_list(arg_list, separator):
    """return list of list of arg_list using separator as delimiter"""
    separator_indexes = [i for i, x in enumerate(arg_list) if x == separator]
    bounds = zip(
        [0] + [i + 1 for i in separator_indexes], separator_indexes + [None]
    )
    return [arg_list[i:j] for i, j in bounds]


def split_list_by_any_keywords(arg_list, keyword_label):
    """
    Return a list of lists of args using any arg not containing = as a delimiter

    iterable arg_list -- (part of) argv
    string keyword_label -- description of all keywords
    """
    if "=" in arg_list[0]:
        raise CmdLineInputError(
            "Invalid character '=' in {} '{}'".format(
                keyword_label,
                arg_list[0],
            )
        )
    current_keyword = None
    groups = {}
    for arg in arg_list:
        if "=" in arg:
            groups[current_keyword].append(arg)
        else:
            current_keyword = arg
            if current_keyword in groups:
                raise CmdLineInputError(
                    "{} '{}' defined multiple times".format(
                        keyword_label.capitalize(), current_keyword
                    )
                )
            groups[current_keyword] = []
    return groups


def split_option(arg, allow_empty_value=True):
    """
    Get (key, value) from a key=value commandline argument.

    Split the argument by the first = and return resulting parts. Raise
    CmdLineInputError if the argument cannot be split.

    string arg -- commandline argument
    allow_empty_value -- if True, empty value is allowed. Otherwise,
        CmdLineInputError exception is raised

    Commandline options: no options
    """
    if "=" not in arg:
        raise CmdLineInputError("missing value of '{0}' option".format(arg))
    if arg.startswith("="):
        raise CmdLineInputError("missing key in '{0}' option".format(arg))
    key, value = arg.split("=", 1)
    if not (value or allow_empty_value):
        raise CmdLineInputError("value of '{0}' option is empty".format(key))
    return key, value


def ensure_unique_args(cmdline_args: StringSequence) -> None:
    """
    Raises in case there are duplicate args
    """
    duplicities = [
        item for item, count in Counter(cmdline_args).items() if count > 1
    ]
    if duplicities:
        argument_pl = format_plural(duplicities, "argument")
        duplicities_list = format_list(duplicities)
        raise CmdLineInputError(f"duplicate {argument_pl}: {duplicities_list}")


def prepare_options(cmdline_args, allowed_repeatable_options=()):
    """
    Get a dict of options from cmdline key=value args

    iterable cmdline_args -- command line arguments
    iterable allowed_repeatable_options -- options that can be set several times

    Commandline options: no options
    """
    options = {}
    for arg in cmdline_args:
        name, value = split_option(arg)
        if name not in options:
            if name in allowed_repeatable_options:
                options[name] = [value]
            else:
                options[name] = value
        elif name in allowed_repeatable_options:
            options[name].append(value)
        elif options[name] != value:
            raise CmdLineInputError(
                (
                    "duplicate option '{0}' with different values '{1}' and "
                    "'{2}'"
                ).format(name, options[name], value)
            )
    return options


def prepare_options_allowed(
    cmdline_args, allowed_options, allowed_repeatable_options=()
):
    """
    Get a dict of options from cmdline key=value args, raise on unallowed key

    iterable cmdline_args -- command line arguments
    iterable allowed_options -- list of allowed options
    iterable allowed_repeatable_options -- options that can be set several times

    Commandline options: no options
    """
    parsed_options = prepare_options(
        cmdline_args, allowed_repeatable_options=allowed_repeatable_options
    )
    unknown_options = frozenset(parsed_options.keys()) - frozenset(
        allowed_options
    )
    if unknown_options:
        raise CmdLineInputError(
            "Unknown option{s} '{options}'".format(
                s=("s" if len(unknown_options) > 1 else ""),
                options="', '".join(sorted(unknown_options)),
            )
        )
    return parsed_options


def group_by_keywords(
    arg_list,
    keyword_set,
    implicit_first_group_key=None,
    keyword_repeat_allowed=True,
    group_repeated_keywords=None,
    only_found_keywords=False,
):
    """
    Return dictionary with keywords as keys and following arguments as value.
    For example when keywords are "first" and "seconds" then for arg_list
    ["first", 1, 2, "second", 3] it returns {"first": [1, 2], "second": [3]}

    list arg_list is commandline arguments containing keywords
    set keyword_set contain all expected keywords
    string implicit_first_group_key is the key for capturing of arguments before
        the occurrence of the first keyword. implicit_first_group_key is not
        a keyword => its occurrence in args is considered as ordinary argument.
    bool keyword_repeat_allowed is the flag to turn on/off checking the
        uniqueness of each keyword in arg_list.
    list group_repeated_keywords contains keywords for which each occurrence is
        packed separately. For example when keywords are "first" and "seconds"
        and group_repeated_keywords is ["first"] then for arg_list
        ["first", 1, 2, "second", 3, "first", 4] it returns
        {"first": [[1, 2], [4]], "second": [3]}.
        For these keywords is allowed repeating.
    bool only_found_keywords is flag for deciding to (not)contain keywords
        that do not appeared in arg_list.
    """

    def get_keywords_for_grouping():
        if not group_repeated_keywords:
            return []
        # implicit_first_group_key is not keyword: when it is in
        # group_repeated_keywords but not in keyword_set is considered as
        # unknown.
        unknown_keywords = set(group_repeated_keywords) - set(keyword_set)
        if unknown_keywords:
            # to avoid developer mistake
            raise AssertionError(
                "Keywords in grouping not in keyword set: {0}".format(
                    ", ".join(unknown_keywords)
                )
            )
        return group_repeated_keywords

    def get_completed_groups():
        completed_groups = groups.copy()
        if not only_found_keywords:
            for keyword in keyword_set:
                if keyword not in completed_groups:
                    completed_groups[keyword] = []
            if (
                implicit_first_group_key
                and implicit_first_group_key not in completed_groups
            ):
                completed_groups[implicit_first_group_key] = []
        return completed_groups

    def is_acceptable_keyword_occurrence(keyword):
        return (
            keyword not in groups
            or keyword_repeat_allowed
            or keyword in keywords_for_grouping
        )

    def process_keyword(keyword):
        if not is_acceptable_keyword_occurrence(keyword):
            raise CmdLineInputError(
                "'{0}' cannot be used more than once".format(keyword)
            )
        groups.setdefault(keyword, [])
        if keyword in keywords_for_grouping:
            groups[keyword].append([])

    def process_non_keyword(keyword, arg):
        place = groups[keyword]
        if keyword in keywords_for_grouping:
            place = place[-1]
        place.append(arg)

    groups = {}
    keywords_for_grouping = get_keywords_for_grouping()

    if arg_list:
        current_keyword = None
        if arg_list[0] not in keyword_set:
            if not implicit_first_group_key:
                raise CmdLineInputError()
            process_keyword(implicit_first_group_key)
            current_keyword = implicit_first_group_key

        for arg in arg_list:
            if arg in keyword_set:
                process_keyword(arg)
                current_keyword = arg
            else:
                process_non_keyword(current_keyword, arg)

    return get_completed_groups()


def parse_typed_arg(arg, allowed_types, default_type):
    """
    Get (type, value) from a typed commandline argument.

    Split the argument by the type separator and return the type and the value.
    Raise CmdLineInputError in the argument format or type is not valid.
    string arg -- commandline argument
    Iterable allowed_types -- list of allowed argument types
    string default_type -- type to return if the argument doesn't specify a type
    """
    if ARG_TYPE_DELIMITER not in arg:
        return default_type, arg
    arg_type, arg_value = arg.split(ARG_TYPE_DELIMITER, 1)
    if not arg_type:
        return default_type, arg_value
    if arg_type not in allowed_types:
        raise CmdLineInputError(
            (
                "'{arg_type}' is not an allowed type for '{arg_full}', use "
                "{hint}"
            ).format(
                arg_type=arg_type,
                arg_full=arg,
                hint=", ".join(sorted(allowed_types)),
            )
        )
    return arg_type, arg_value


def _is_num(arg):
    return arg.isdigit() or arg.lower() == "infinity"


def _is_float(arg: str) -> bool:
    try:
        float(arg)
        return True
    except ValueError:
        return False


def _is_negative_num(arg: str) -> bool:
    return arg.startswith("-") and (_is_num(arg[1:]) or _is_float(arg))


def is_short_option_expecting_value(arg):
    return (
        len(arg) == 2
        and arg[0] == "-"
        and "{0}:".format(arg[1]) in PCS_SHORT_OPTIONS
    )


def is_long_option_expecting_value(arg):
    return (
        len(arg) > 2
        and arg[0:2] == "--"
        and "{0}=".format(arg[2:]) in PCS_LONG_OPTIONS
    )


def is_option_expecting_value(arg):
    return is_short_option_expecting_value(
        arg
    ) or is_long_option_expecting_value(arg)


# DEPRECATED
# TODO remove
# This function is called only by deprecated code for parsing argv containing
# negative numbers without -- prepending them.
def filter_out_non_option_negative_numbers(arg_list):
    """
    Return arg_list without non-option negative numbers.
    Negative numbers following the option expecting value are kept.

    There is the problematic legacy:
    Argument "--" has special meaning: it can be used to signal that no more
    options will follow. This would solve the problem with negative numbers in
    a standard way: there would be no special approach to negative numbers,
    everything would be left in the hands of users.

    We cannot use "--" as it would be a backward incompatible change:
    * "pcs ... -infinity" would not work any more, users would have to switch
      to "pcs ... -- ... -infinity"
    * previously, position of some --options mattered, for example
      "--clone <clone options>", this syntax would not be possible with the "--"
      in place

    Currently used --options, which may be problematic when switching to "--":
    * --group <group name>, --before | --after <resource id>
      * pcs resource | stonith create, pcs resource group add, pcs tag update
      * They have a single argument, so they would work even with --. But the
        command may look weird:
        pcs resource create --group G --after R2 -- R3 ocf:pacemaker:Dummy
        vs. current command
        pcs resource create R3 ocf:pacemaker:Dummy --group G --after R2

    list arg_list contains command line arguments
    """
    args_without_negative_nums = []
    args_filtered_out = []
    for i, arg in enumerate(arg_list):
        prev_arg = arg_list[i - 1] if i > 0 else ""
        if not _is_negative_num(arg) or is_option_expecting_value(prev_arg):
            args_without_negative_nums.append(arg)
        else:
            args_filtered_out.append(arg)

    return args_without_negative_nums, args_filtered_out


# DEPRECATED
# TODO remove
# This function is called only by deprecated code for parsing argv containing
# negative numbers without -- prepending them.
def filter_out_options(arg_list):
    """
    Return arg_list without options and its negative numbers.

    See a comment in filter_out_non_option_negative_numbers.

    list arg_list contains command line arguments
    """
    args_without_options = []
    for i, arg in enumerate(arg_list):
        prev_arg = arg_list[i - 1] if i > 0 else ""
        if not is_option_expecting_value(prev_arg) and (
            not arg.startswith("-") or arg == "-" or _is_negative_num(arg)
        ):
            args_without_options.append(arg)
    return args_without_options


def wait_to_timeout(wait: Union[bool, str, None]) -> int:
    if wait is False:
        return -1
    if wait is None:
        return 0
    timeout = timeout_to_seconds(wait)
    if timeout is None:
        raise CmdLineInputError(f"'{wait}' is not a valid interval value")
    return timeout


class InputModifiers:
    def __init__(self, options: Mapping[str, ModifierValueType]):
        self._defined_options = set(options.keys())
        self._options = dict(options)
        self._options.update(
            {
                # boolean values
                "--all": "--all" in options,
                "--agent-validation": "--agent-validation" in options,
                "--autodelete": "--autodelete" in options,
                "--brief": "--brief" in options,
                "--config": "--config" in options,
                "--corosync": "--corosync" in options,
                "--debug": "--debug" in options,
                "--defaults": "--defaults" in options,
                "--disabled": "--disabled" in options,
                "--enable": "--enable" in options,
                "--expired": "--expired" in options,
                "--force": "--force" in options,
                "--full": "--full" in options,
                # TODO remove
                # used only in deprecated 'pcs resource|stonith show'
                "--groups": "--groups" in options,
                "--hide-inactive": "--hide-inactive" in options,
                "--local": "--local" in options,
                "--monitor": "--monitor" in options,
                "--no-default-ops": "--no-default-ops" in options,
                "--nodesc": "--nodesc" in options,
                "--no-expire-check": "--no-expire-check" in options,
                "--no-cluster-uuid": "--no-cluster-uuid" in options,
                "--no-keys-sync": "--no-keys-sync" in options,
                "--no-strict": "--no-strict" in options,
                "--no-watchdog-validation": "--no-watchdog-validation"
                in options,
                "--off": "--off" in options,
                "--overwrite": "--overwrite" in options,
                "--pacemaker": "--pacemaker" in options,
                "--promoted": "--promoted" in options,
                "--safe": "--safe" in options,
                "--simulate": "--simulate" in options,
                "--skip-offline": "--skip-offline" in options,
                "--start": "--start" in options,
                "--strict": "--strict" in options,
                # string values
                "--after": options.get("--after", None),
                "--before": options.get("--before", None),
                "--booth-conf": options.get("--booth-conf", None),
                "--booth-key": options.get("--booth-key", None),
                "--corosync_conf": options.get("--corosync_conf", None),
                "--from": options.get("--from", None),
                "--group": options.get("--group", None),
                "--name": options.get("--name", None),
                "--node": options.get("--node", None),
                _OUTPUT_FORMAT_OPTION: options.get(
                    _OUTPUT_FORMAT_OPTION, OUTPUT_FORMAT_VALUE_TEXT
                ),
                "--request-timeout": options.get("--request-timeout", None),
                "--to": options.get("--to", None),
                "--token": options.get("--token", None),
                "--wait": options.get("--wait", False),
                "-f": options.get("-f", None),
                "-p": options.get("-p", None),
                "-u": options.get("-u", None),
            }
        )

    def get_subset(self, *options, **custom_options):
        opt_dict = {
            opt: self.get(opt) for opt in options if self.is_specified(opt)
        }
        opt_dict.update(custom_options)
        return InputModifiers(opt_dict)

    def ensure_only_supported(
        self,
        *supported_options: str,
        hint_syntax_changed: bool = False,
        output_format_supported: bool = False,
    ) -> None:
        # --debug is supported in all commands
        supported_options_set = set(supported_options) | {"--debug"}
        if output_format_supported:
            supported_options_set.add(_OUTPUT_FORMAT_OPTION)
        unsupported_options = self._defined_options - supported_options_set
        if unsupported_options:
            pluralize = partial(format_plural, unsupported_options)
            raise CmdLineInputError(
                "Specified {option} {option_list} {_is} not supported in this "
                "command".format(
                    option=pluralize("option"),
                    option_list=format_list(sorted(unsupported_options)),
                    _is=pluralize("is"),
                ),
                hint="Syntax has changed from previous version. {}".format(
                    SEE_MAN_CHANGES.format("0.11")
                )
                if hint_syntax_changed
                else None,
            )

    def ensure_not_mutually_exclusive(self, *mutually_exclusive):
        options_to_report = self._defined_options & set(mutually_exclusive)
        if len(options_to_report) > 1:
            raise CmdLineInputError(
                "Only one of {} can be used".format(
                    format_list(sorted(options_to_report))
                )
            )

    def ensure_not_incompatible(self, checked, incompatible):
        if not checked in self._defined_options:
            return
        disallowed = self._defined_options & set(incompatible)
        if disallowed:
            raise CmdLineInputError(
                "'{}' cannot be used with {}".format(
                    checked, format_list(sorted(disallowed))
                )
            )

    def ensure_dependency_satisfied(
        self, main_option: str, dependent_options: StringIterable
    ) -> None:
        """
        Raise a `CmdLineInputError` exception if any of `dependent_options` is
        present without `main_option` being present.

        main_option -- option on which `dependent_options` depend
        dependent_options -- none of these options can be specified if
            `main_option` was not
        """
        if main_option in self._defined_options:
            return
        disallowed = self._defined_options & set(dependent_options)
        if disallowed:
            raise CmdLineInputError(
                "{} cannot be used without '{}'".format(
                    format_list(sorted(disallowed)), main_option
                )
            )

    def is_specified(self, option: str) -> bool:
        return option in self._defined_options

    def is_specified_any(self, option_list: StringIterable) -> bool:
        for option in option_list:
            if self.is_specified(option):
                return True
        return False

    def get(
        self, option: str, default: ModifierValueType = None
    ) -> ModifierValueType:
        if option in self._defined_options:
            return self._options[option]
        if default is not None:
            return default
        if option in self._options:
            return self._options[option]
        raise AssertionError(f"Non existing default value for '{option}'")

    def get_output_format(
        self, supported_formats: Set[str] = _OUTPUT_FORMAT_VALUES
    ) -> str:
        output_format = self.get(_OUTPUT_FORMAT_OPTION)
        if output_format in supported_formats:
            return cast(str, output_format)
        raise CmdLineInputError(
            (
                "Unknown value '{value}' for '{option}' option. Supported "
                "{value_pl} {is_pl}: {supported}"
            ).format(
                value=output_format,
                option=_OUTPUT_FORMAT_OPTION,
                value_pl=format_plural(supported_formats, "value"),
                is_pl=format_plural(supported_formats, "is"),
                supported=format_list(list(supported_formats)),
            )
        )
