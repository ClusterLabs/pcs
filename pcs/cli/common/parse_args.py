from collections import Counter
from functools import partial
from typing import (
    Final,
    Mapping,
    Optional,
    Union,
)

from pcs.cli.common.errors import (
    SEE_MAN_CHANGES,
    CmdLineInputError,
)
from pcs.cli.reports.output import deprecation_warning
from pcs.common.const import INFINITY
from pcs.common.str_tools import (
    format_list,
    format_list_custom_last_separator,
    format_plural,
)
from pcs.common.tools import timeout_to_seconds
from pcs.common.types import (
    StringCollection,
    StringIterable,
    StringSequence,
)

# sys.argv always returns a list, we don't need StringSequence in here
Argv = list[str]
ModifierValueType = Union[None, bool, str]

_FUTURE_OPTION_STR: Final = "future"
FUTURE_OPTION: Final = f"--{_FUTURE_OPTION_STR}"
_OUTPUT_FORMAT_OPTION_STR: Final = "output-format"
OUTPUT_FORMAT_OPTION: Final = f"--{_OUTPUT_FORMAT_OPTION_STR}"
OUTPUT_FORMAT_VALUE_CMD: Final = "cmd"
OUTPUT_FORMAT_VALUE_JSON: Final = "json"
OUTPUT_FORMAT_VALUE_TEXT: Final = "text"
OUTPUT_FORMAT_VALUES: Final = frozenset(
    (
        OUTPUT_FORMAT_VALUE_CMD,
        OUTPUT_FORMAT_VALUE_JSON,
        OUTPUT_FORMAT_VALUE_TEXT,
    )
)

ARG_TYPE_DELIMITER: Final = "%"

# h = help, f = file,
# p = password (cluster auth), u = user (cluster auth),
PCS_SHORT_OPTIONS: Final = "hf:p:u:"
PCS_LONG_OPTIONS: Final = [
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
    _FUTURE_OPTION_STR,
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
    # do not stop resources in resource delete command
    "no-stop",
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
    # disable text output in query commands
    "quiet",
    # proceed with dangerous actions, meant for / used in CLI only
    "yes",
]


def split_list(arg_list: Argv, separator: str) -> list[Argv]:
    """
    split a list of arguments to several lists using separator as a delimiter

    arg_list -- list of command line arguments to split
    separator -- delimiter
    """
    separator_indexes = [i for i, x in enumerate(arg_list) if x == separator]
    bounds = zip(
        [0] + [i + 1 for i in separator_indexes],
        separator_indexes + [None],
        strict=False,
    )
    return [arg_list[i:j] for i, j in bounds]


def split_list_by_any_keywords(
    arg_list: Argv, keyword_label: str
) -> dict[str, Argv]:
    """
    split a list of arguments using any argument not containing = as a delimiter

    arg_list -- list of command line arguments to split
    keyword_label -- description of all keywords
    """
    groups: dict[str, Argv] = {}
    if not arg_list:
        return groups

    if "=" in arg_list[0]:
        raise CmdLineInputError(
            f"Invalid character '=' in {keyword_label} '{arg_list[0]}'"
        )

    current_keyword = arg_list[0]
    groups[current_keyword] = []
    for arg in arg_list[1:]:
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


def split_option(arg: str, allow_empty_value: bool = True) -> tuple[str, str]:
    """
    Get (key, value) from a key=value commandline argument.

    Split the argument by the first = and return resulting parts. Raise
    CmdLineInputError if the argument cannot be split.

    arg -- commandline argument to split
    allow_empty_value -- if False, raise CmdLineInputError on empty value
    """
    if "=" not in arg:
        raise CmdLineInputError(f"missing value of '{arg}' option")
    if arg.startswith("="):
        raise CmdLineInputError(f"missing key in '{arg}' option")
    key, value = arg.split("=", 1)
    if not (value or allow_empty_value):
        raise CmdLineInputError(f"value of '{key}' option is empty")
    return key, value


def ensure_unique_args(cmdline_args: Argv) -> None:
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


class KeyValueParser:
    """
    Parse and check key=value options
    """

    def __init__(self, arg_list: Argv, repeatable: StringCollection = ()):
        """
        arg_list -- commandline arguments to be parsed
        repeatable -- keys that are allowed to be specified several times
        """
        self._repeatable_keys = repeatable
        self._key_value_map: dict[str, list[str]] = {}
        for arg in arg_list:
            name, value = split_option(arg)
            if name not in self._key_value_map:
                self._key_value_map[name] = [value]
            else:
                self._key_value_map[name].append(value)

    def check_allowed_keys(self, allowed_keys: StringCollection) -> None:
        """
        Check that only allowed keys were specified

        allowed_keys -- list of allowed keys
        """
        unknown_options = set(self._key_value_map.keys()) - set(allowed_keys)
        if unknown_options:
            raise CmdLineInputError(
                "Unknown option{s} '{options}'".format(
                    s=("s" if len(unknown_options) > 1 else ""),
                    options="', '".join(sorted(unknown_options)),
                )
            )

    def get_unique(self) -> dict[str, str]:
        """
        Get all non-repeatable keys and their values; raise if a key has more values
        """
        result: dict[str, str] = {}
        for key, values in self._key_value_map.items():
            if key in self._repeatable_keys:
                continue
            values_uniq = set(values)
            if len(values_uniq) > 1:
                raise CmdLineInputError(
                    f"duplicate option '{key}' with different values "
                    f"{format_list_custom_last_separator(values_uniq, ' and ')}"
                )
            result[key] = values[0]
        return result

    def get_repeatable(self) -> dict[str, list[str]]:
        """
        Get all repeatable keys and their values
        """
        return {
            key: self._key_value_map[key]
            for key in self._repeatable_keys
            if key in self._key_value_map
        }


class ArgsByKeywords:
    def __init__(self, groups: Mapping[str, list[Argv]]):
        self._groups = groups
        self._flat_cache: dict[str, Argv] = {}

    def allow_repetition_only_for(self, keyword_set: StringCollection) -> None:
        """
        Raise CmdLineInputError if a keyword has been repeated when not allowed

        keyword_set -- repetition is allowed for these keywords
        """
        for keyword, arg_groups in self._groups.items():
            if len(arg_groups) > 1 and keyword not in keyword_set:
                raise CmdLineInputError(
                    f"'{keyword}' cannot be used more than once"
                )

    def ensure_unique_keywords(self) -> None:
        """
        Raise CmdLineInputError if any keyword has been repeated
        """
        return self.allow_repetition_only_for(set())

    def is_empty(self) -> bool:
        """
        Check if any args have been specified
        """
        return not self._groups

    def has_keyword(self, keyword: str) -> bool:
        """
        Check if a keyword has been specified

        keyword -- a keyword to check
        """
        return keyword in self._groups

    def has_empty_keyword(self, keyword: str) -> bool:
        """
        Check if a keyword has been specified without any following args

        keyword -- a keyword to check
        """
        return self.has_keyword(keyword) and not self.get_args_flat(keyword)

    def get_args_flat(self, keyword: str) -> Argv:
        """
        Get arguments of a keyword in one sequence
        """
        if keyword in self._groups:
            if keyword not in self._flat_cache:
                self._flat_cache[keyword] = [
                    arg
                    for one_group in self._groups[keyword]
                    for arg in one_group
                ]
            return self._flat_cache[keyword]
        return []

    def get_args_groups(self, keyword: str) -> list[Argv]:
        """
        Get arguments of a keyword, one group for each keyword occurrence
        """
        if keyword in self._groups:
            return self._groups[keyword]
        return []


def group_by_keywords(
    arg_list: Argv,
    keyword_set: StringCollection,
    implicit_first_keyword: Optional[str] = None,
) -> ArgsByKeywords:
    """
    Separate argv into groups delimited by specified keywords

    arg_list -- commandline arguments containing keywords
    keyword_set -- all expected keywords
    implicit_first_keyword -- key for capturing args before the first keyword
    """
    args_by_keywords: dict[str, list[Argv]] = {}

    def new_keyword(keyword: str) -> None:
        if keyword not in args_by_keywords:
            args_by_keywords[keyword] = []
        args_by_keywords[keyword].append([])

    if arg_list:
        if arg_list[0] not in keyword_set:
            if not implicit_first_keyword:
                raise CmdLineInputError()
            current_keyword = implicit_first_keyword
            new_keyword(current_keyword)

        for arg in arg_list:
            if arg in keyword_set:
                current_keyword = arg
                new_keyword(current_keyword)
            else:
                args_by_keywords[current_keyword][-1].append(arg)

    return ArgsByKeywords(args_by_keywords)


def parse_typed_arg(
    arg: str, allowed_types: StringSequence, default_type: str
) -> tuple[str, str]:
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


def _is_num(arg: str) -> bool:
    if arg.lower() == INFINITY.lower():
        return True
    try:
        int(arg)
        return True
    except ValueError:
        return False


def _is_float(arg: str) -> bool:
    try:
        float(arg)
        return True
    except ValueError:
        return False


def _is_negative_num(arg: str) -> bool:
    return arg.startswith("-") and (_is_num(arg[1:]) or _is_float(arg))


def is_short_option_expecting_value(arg: str) -> bool:
    return len(arg) == 2 and arg[0] == "-" and f"{arg[1]}:" in PCS_SHORT_OPTIONS


def is_long_option_expecting_value(arg: str) -> bool:
    return (
        len(arg) > 2 and arg[0:2] == "--" and f"{arg[2:]}=" in PCS_LONG_OPTIONS
    )


def is_option_expecting_value(arg: str) -> bool:
    return is_short_option_expecting_value(
        arg
    ) or is_long_option_expecting_value(arg)


# DEPRECATED
# TODO remove
# This function is called only by deprecated code for parsing argv containing
# negative numbers without -- prepending them.
def filter_out_non_option_negative_numbers(arg_list: Argv) -> tuple[Argv, Argv]:
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
def filter_out_options(arg_list: Argv) -> Argv:
    """
    Return arg_list without options and negative numbers

    See a comment in filter_out_non_option_negative_numbers.

    arg_list -- command line arguments
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
                "--quiet": "--quiet" in options,
                FUTURE_OPTION: FUTURE_OPTION in options,
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
                "--no-stop": "--no-stop" in options,
                "--no-strict": "--no-strict" in options,
                "--no-watchdog-validation": (
                    "--no-watchdog-validation" in options
                ),
                "--off": "--off" in options,
                "--overwrite": "--overwrite" in options,
                "--pacemaker": "--pacemaker" in options,
                "--promoted": "--promoted" in options,
                "--safe": "--safe" in options,
                "--simulate": "--simulate" in options,
                "--skip-offline": "--skip-offline" in options,
                "--start": "--start" in options,
                "--strict": "--strict" in options,
                "--yes": "--yes" in options,
                # string values
                "--after": options.get("--after", None),
                "--before": options.get("--before", None),
                "--booth-conf": options.get("--booth-conf", None),
                "--booth-key": options.get("--booth-key", None),
                "--corosync_conf": options.get("--corosync_conf", None),
                "--from": options.get("--from", None),
                # TODO remove
                # used in resource create and stonith create, deprecated in both
                "--group": options.get("--group", None),
                "--name": options.get("--name", None),
                "--node": options.get("--node", None),
                OUTPUT_FORMAT_OPTION: options.get(
                    OUTPUT_FORMAT_OPTION, OUTPUT_FORMAT_VALUE_TEXT
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

    def get_subset(
        self, *options: str, **custom_options: ModifierValueType
    ) -> "InputModifiers":
        opt_dict = {
            opt: self.get(opt) for opt in options if self.is_specified(opt)
        }
        opt_dict.update(custom_options)
        return InputModifiers(opt_dict)

    def ensure_only_supported(
        self,
        *supported_options: str,
        hint_syntax_changed: Optional[str] = None,
        output_format_supported: bool = False,
    ) -> None:
        # --debug is supported in all commands
        supported_options_set = set(supported_options) | {"--debug"}
        if output_format_supported:
            supported_options_set.add(OUTPUT_FORMAT_OPTION)
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
                hint=(
                    "Syntax has changed from previous version. {}".format(
                        SEE_MAN_CHANGES.format(hint_syntax_changed)
                    )
                    if hint_syntax_changed
                    else None
                ),
            )

    def ensure_not_mutually_exclusive(self, *mutually_exclusive: str) -> None:
        """
        Raise CmdLineInputError if several exclusive options were specified

        mutually_exclusive -- mutually exclusive options
        """
        options_to_report = self._defined_options & set(mutually_exclusive)
        if len(options_to_report) > 1:
            raise CmdLineInputError(
                "Only one of {} can be used".format(
                    format_list(sorted(options_to_report))
                )
            )

    def ensure_not_incompatible(
        self, checked: str, incompatible: StringCollection
    ) -> None:
        """
        Raise CmdLineInputError if both the checked and an incompatible option
        were specified

        checked -- option incompatible with any of incompatible options
        incompatible -- set of options incompatible with checked
        """
        if checked not in self._defined_options:
            return
        disallowed = self._defined_options & set(incompatible)
        if disallowed:
            raise CmdLineInputError(
                "'{}' cannot be used with {}".format(
                    checked, format_list(sorted(disallowed))
                )
            )

    def ensure_dependency_satisfied(
        self, main_option: str, dependent_options: StringCollection
    ) -> None:
        """
        Raise CmdLineInputError if any of dependent_options is present and
        main_option is not present.

        main_option -- option on which dependent_options depend
        dependent_options -- none of these options can be specified if
            main_option is not specified
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
        return any(self.is_specified(option) for option in option_list)

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
        self,
        supported_formats: StringCollection = OUTPUT_FORMAT_VALUES,
    ) -> str:
        output_format = self.get(OUTPUT_FORMAT_OPTION)
        if output_format in supported_formats:
            return str(output_format)
        raise CmdLineInputError(
            (
                "Unknown value '{value}' for '{option}' option. Supported "
                "{value_pl} {is_pl}: {supported}"
            ).format(
                value=output_format,
                option=OUTPUT_FORMAT_OPTION,
                value_pl=format_plural(supported_formats, "value"),
                is_pl=format_plural(supported_formats, "is"),
                supported=format_list(list(supported_formats)),
            )
        )


def get_rule_str(argv: Argv) -> Optional[str]:
    if argv:
        if len(argv) > 1:
            # deprecated after 0.11.7
            deprecation_warning(
                "Specifying a rule as multiple arguments is deprecated and "
                "might be removed in a future release, specify the rule as "
                "a single string instead"
            )
            return " ".join(argv)
        return argv[0]
    return None
