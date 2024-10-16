# pylint: disable=too-many-lines
from collections import defaultdict
from dataclasses import (
    dataclass,
    field,
)
from functools import partial
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Tuple,
    Union,
    cast,
)

from pcs.common import file_type_codes
from pcs.common.fencing_topology import TARGET_TYPE_ATTRIBUTE
from pcs.common.file import (
    FileAction,
    RawFileError,
)
from pcs.common.resource_agent.dto import (
    ResourceAgentNameDto,
    get_resource_agent_full_name,
)
from pcs.common.str_tools import (
    format_list,
    format_list_custom_last_separator,
    format_list_dont_sort,
    format_optional,
    format_plural,
    get_plural,
    indent,
    is_iterable_not_str,
)
from pcs.common.types import (
    CibRuleExpressionType,
    StringIterable,
)

from . import (
    codes,
    const,
    types,
)
from .dto import ReportItemMessageDto
from .item import ReportItemMessage

INSTANCE_SUFFIX = "@{0}"
NODE_PREFIX = "{0}: "


def _stdout_stderr_to_string(stdout: str, stderr: str, prefix: str = "") -> str:
    new_lines = [prefix] if prefix else []
    for line in stdout.splitlines() + stderr.splitlines():
        if line.strip():
            new_lines.append(line)
    return "\n".join(new_lines)


def _resource_move_ban_clear_master_resource_not_promotable(
    promotable_id: str,
) -> str:
    return (
        "when specifying promoted you must use the promotable clone id{_id}"
    ).format(
        _id=format_optional(promotable_id, " ({})"),
    )


def _resource_move_ban_pcmk_success(stdout: str, stderr: str) -> str:
    new_lines = []
    for line in stdout.splitlines() + stderr.splitlines():
        if not line.strip():
            continue
        line = line.replace(
            "WARNING: Creating rsc_location constraint",
            "Warning: Creating location constraint",
        )
        line = line.replace(
            " using the clear option or by editing the CIB with an "
            "appropriate tool",
            "",
        )
        new_lines.append(line)
    return "\n".join(new_lines)


def _format_fencing_level_target(
    target_type: Optional[str], target_value: Any
) -> str:
    if target_type == TARGET_TYPE_ATTRIBUTE:
        return f"{target_value[0]}={target_value[1]}"
    return target_value


def _format_booth_default(value: Optional[str], template: str) -> str:
    return "" if value in ("booth", "", None) else template.format(value)


def _key_numeric(item: str) -> Tuple[int, str]:
    return (int(item), item) if item.isdigit() else (-1, item)


_add_remove_container_translation = {
    const.ADD_REMOVE_CONTAINER_TYPE_PROPERTY_SET: "property set",
    const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE: "stonith resource",
}

_add_remove_item_translation = {
    const.ADD_REMOVE_ITEM_TYPE_DEVICE: "device",
    const.ADD_REMOVE_ITEM_TYPE_PROPERTY: "property",
}

_file_role_translation = {
    file_type_codes.BOOTH_CONFIG: "Booth configuration",
    file_type_codes.BOOTH_KEY: "Booth key",
    file_type_codes.COROSYNC_AUTHKEY: "Corosync authkey",
    file_type_codes.COROSYNC_CONF: "Corosync configuration",
    file_type_codes.COROSYNC_QDEVICE_NSSDB: "QDevice certificate database",
    file_type_codes.COROSYNC_QNETD_CA_CERT: "QNetd CA certificate",
    file_type_codes.COROSYNC_QNETD_NSSDB: "QNetd certificate database",
    file_type_codes.PCS_DR_CONFIG: "disaster-recovery configuration",
    file_type_codes.PACEMAKER_AUTHKEY: "Pacemaker authkey",
    file_type_codes.PCSD_ENVIRONMENT_CONFIG: "pcsd configuration",
    file_type_codes.PCSD_SSL_CERT: "pcsd SSL certificate",
    file_type_codes.PCSD_SSL_KEY: "pcsd SSL key",
    file_type_codes.PCS_KNOWN_HOSTS: "known-hosts",
    file_type_codes.PCS_SETTINGS_CONF: "pcs configuration",
}

_type_translation = {
    "acl_group": "ACL group",
    "acl_permission": "ACL permission",
    "acl_role": "ACL role",
    "acl_target": "ACL user",
    "fencing-level": "fencing level",
    # Pacemaker-2.0 deprecated masters. Masters are now called promotable
    # clones. We treat masters as clones. Do not report we were doing something
    # with a master, say we were doing it with a clone instead.
    "master": "clone",
    "primitive": "resource",
    "resource_set": "resource set",
    "rsc_colocation": "colocation constraint",
    "rsc_location": "location constraint",
    "rsc_order": "order constraint",
    "rsc_ticket": "ticket constraint",
}
_type_articles = {
    "ACL group": "an",
    "ACL user": "an",
    "ACL role": "an",
    "ACL permission": "an",
    "options set": "an",
}


def _add_remove_container_str(
    container: types.AddRemoveContainerType,
) -> str:
    return _add_remove_container_translation.get(container, container)


def _add_remove_item_str(item: types.AddRemoveItemType) -> str:
    return _add_remove_item_translation.get(item, item)


def _format_file_role(role: file_type_codes.FileTypeCode) -> str:
    return _file_role_translation.get(role, role)


def _format_file_action(action: FileAction) -> str:
    return _file_operation_translation.get(action, str(action))


_file_operation_translation = {
    RawFileError.ACTION_CHMOD: "change permissions of",
    RawFileError.ACTION_CHOWN: "change ownership of",
    RawFileError.ACTION_READ: "read",
    RawFileError.ACTION_REMOVE: "remove",
    RawFileError.ACTION_UPDATE: "update",
    RawFileError.ACTION_WRITE: "write",
}


def _service_action_str(action: types.ServiceAction, suffix: str = "") -> str:
    base = action.lower()
    if not suffix:
        return base
    base = {
        const.SERVICE_ACTION_STOP: "stopp",
        const.SERVICE_ACTION_ENABLE: "enabl",
        const.SERVICE_ACTION_DISABLE: "disabl",
    }.get(action, base)
    return f"{base}{suffix}"


def _skip_reason_to_string(reason: types.ReasonType) -> str:
    return {
        const.REASON_NOT_LIVE_CIB: "the command does not run on a live cluster",
        const.REASON_UNREACHABLE: "pcs is unable to connect to the node(s)",
    }.get(reason, reason)


def _typelist_to_string(
    type_list: StringIterable, article: bool = False
) -> str:
    if not type_list:
        return ""
    # use set to drop duplicate items:
    # * master is translated to clone
    # * i.e. "clone, master" is translated to "clone, clone"
    # * so we want to drop the second clone
    new_list = sorted(
        {
            # get a translation or make a type_name a string
            _type_translation.get(type_name, f"{type_name}")
            for type_name in type_list
        }
    )
    res_types = "/".join(new_list)
    if not article:
        return res_types
    return "{article} {types}".format(
        article=_type_articles.get(new_list[0], "a"),
        types=res_types,
    )


def _type_to_string(type_name: str, article: bool = False) -> str:
    if not type_name:
        return ""
    # get a translation or make a type_name a string
    translated = _type_translation.get(type_name, f"{type_name}")
    if not article:
        return translated
    return "{article} {type}".format(
        article=_type_articles.get(translated, "a"),
        type=translated,
    )


def _build_node_description(node_types: List[str]) -> str:
    if not node_types:
        return "Node"

    label = "{0} node".format

    if len(node_types) == 1:
        return label(node_types[0])

    return "nor " + " or ".join([label(ntype) for ntype in node_types])


def _stonith_watchdog_timeout_reason_to_str(
    reason: types.StonithWatchdogTimeoutCannotBeSetReason,
) -> str:
    return {
        const.SBD_NOT_SET_UP: "SBD is disabled",
        const.SBD_SET_UP_WITH_DEVICES: "SBD is enabled with devices",
        const.SBD_SET_UP_WITHOUT_DEVICES: "SBD is enabled without devices",
    }.get(reason, reason)


@dataclass(frozen=True)
class LegacyCommonMessage(ReportItemMessage):
    """
    This class is used for legacy report transport protocol from
    'pcs_internal.py' and is used in 'pcs.cluster.RemoteAddNodes'. This method
    should be replaced with transporting DTOs of reports in the future.
    """

    legacy_code: types.MessageCode
    legacy_info: Mapping[str, Any]
    legacy_message: str

    @property
    def message(self) -> str:
        return self.legacy_message

    def to_dto(self) -> ReportItemMessageDto:
        return ReportItemMessageDto(
            code=self.legacy_code,
            message=self.message,
            payload=dict(self.legacy_info),
        )


@dataclass(frozen=True)
class ResourceForConstraintIsMultiinstance(ReportItemMessage):
    """
    When setting up a constraint a resource in a type of a clone was specified

    resource_id -- specified resource
    parent_type -- type of a clone (clone, bundle...)
    parent_id -- clone resource id
    """

    resource_id: str
    parent_type: str
    parent_id: str
    _code = codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE

    @property
    def message(self) -> str:
        parent_type = _type_to_string(self.parent_type)
        return (
            f"{self.resource_id} is a {parent_type} resource, you should "
            f"use the {parent_type} id: {self.parent_id} when adding "
            "constraints"
        )


@dataclass(frozen=True)
class DuplicateConstraintsExist(ReportItemMessage):
    """
    When creating a constraint pcs detected a similar constraint already exists

    constraint_ids -- ids of similar constraints
    """

    constraint_ids: list[str]
    _code = codes.DUPLICATE_CONSTRAINTS_EXIST

    @property
    def message(self) -> str:
        pluralize = partial(format_plural, self.constraint_ids)
        constraint = pluralize("constraint")
        exists = pluralize("exists", "exist")
        return f"Duplicate {constraint} already {exists}"


@dataclass(frozen=True)
class EmptyResourceSetList(ReportItemMessage):
    """
    An empty resource set has been specified, which is not allowed by cib schema
    """

    _code = codes.EMPTY_RESOURCE_SET_LIST

    @property
    def message(self) -> str:
        return "Resource set list is empty"


@dataclass(frozen=True)
class CannotSetOrderConstraintsForResourcesInTheSameGroup(ReportItemMessage):
    """
    Can't set order constraint for resources in one group because the
    start sequence of the resources is determined by their location in the group
    """

    _code = codes.CANNOT_SET_ORDER_CONSTRAINTS_FOR_RESOURCES_IN_THE_SAME_GROUP

    @property
    def message(self) -> str:
        return (
            "Cannot create an order constraint for resources in the same group"
        )


@dataclass(frozen=True)
class RequiredOptionsAreMissing(ReportItemMessage):
    """
    Required option has not been specified, command cannot continue

    option_names -- are required but was not entered
    option_type -- describes the option
    """

    option_names: List[str]
    option_type: Optional[str] = None
    _code = codes.REQUIRED_OPTIONS_ARE_MISSING

    @property
    def message(self) -> str:
        return (
            "required {desc}{_option} {option_names_list} {_is} missing"
        ).format(
            desc=format_optional(self.option_type),
            option_names_list=format_list(self.option_names),
            _option=format_plural(self.option_names, "option"),
            _is=format_plural(self.option_names, "is"),
        )


@dataclass(frozen=True)
class PrerequisiteOptionIsMissing(ReportItemMessage):
    """
    If the option_name is specified, the prerequisite_option must be specified

    option_name -- an option which depends on the prerequisite_option
    prerequisite_name -- the prerequisite option
    option_type -- describes the option
    prerequisite_type -- describes the prerequisite_option
    """

    option_name: str
    prerequisite_name: str
    option_type: Optional[str] = None
    prerequisite_type: Optional[str] = None
    _code = codes.PREREQUISITE_OPTION_IS_MISSING

    @property
    def message(self) -> str:
        return (
            "If {opt_desc}option '{option_name}' is specified, "
            "{pre_desc}option '{prerequisite_name}' must be specified as well"
        ).format(
            opt_desc=format_optional(self.option_type),
            pre_desc=format_optional(self.prerequisite_type),
            option_name=self.option_name,
            prerequisite_name=self.prerequisite_name,
        )


@dataclass(frozen=True)
class PrerequisiteOptionMustBeEnabledAsWell(ReportItemMessage):
    """
    If the option_name is enabled, the prerequisite_option must be also enabled

    option_name -- an option which depends on the prerequisite_option
    prerequisite_name -- the prerequisite option
    option_type -- describes the option
    prerequisite_type -- describes the prerequisite_option
    """

    option_name: str
    prerequisite_name: str
    option_type: str = ""
    prerequisite_type: str = ""
    _code = codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL

    @property
    def message(self) -> str:
        return (
            "If {opt_desc}option '{option_name}' is enabled, "
            "{pre_desc}option '{prerequisite_name}' must be enabled as well"
        ).format(
            opt_desc=format_optional(self.option_type),
            pre_desc=format_optional(self.prerequisite_type),
            option_name=self.option_name,
            prerequisite_name=self.prerequisite_name,
        )


@dataclass(frozen=True)
class PrerequisiteOptionMustBeDisabled(ReportItemMessage):
    """
    If the option_name is enabled, the prerequisite_option must be disabled

    option_name -- an option which depends on the prerequisite_option
    prerequisite_name -- the prerequisite option
    option_type -- describes the option
    prerequisite_type -- describes the prerequisite_option
    """

    option_name: str
    prerequisite_name: str
    option_type: str = ""
    prerequisite_type: str = ""
    _code = codes.PREREQUISITE_OPTION_MUST_BE_DISABLED

    @property
    def message(self) -> str:
        return (
            "If {opt_desc}option '{option_name}' is enabled, "
            "{pre_desc}option '{prerequisite_name}' must be disabled"
        ).format(
            opt_desc=format_optional(self.option_type),
            pre_desc=format_optional(self.prerequisite_type),
            option_name=self.option_name,
            prerequisite_name=self.prerequisite_name,
        )


@dataclass(frozen=True)
class PrerequisiteOptionMustNotBeSet(ReportItemMessage):
    """
    The option_name cannot be set because the prerequisite_name is already set

    option_name -- an option which depends on the prerequisite_option
    prerequisite_name -- the prerequisite option
    option_type -- describes the option
    prerequisite_type -- describes the prerequisite_option
    """

    option_name: str
    prerequisite_name: str
    option_type: str = ""
    prerequisite_type: str = ""
    _code = codes.PREREQUISITE_OPTION_MUST_NOT_BE_SET

    @property
    def message(self) -> str:
        return (
            "Cannot set {opt_desc}option '{option_name}' because "
            "{pre_desc}option '{prerequisite_name}' is already set"
        ).format(
            opt_desc=format_optional(self.option_type),
            pre_desc=format_optional(self.prerequisite_type),
            option_name=self.option_name,
            prerequisite_name=self.prerequisite_name,
        )


@dataclass(frozen=True)
class RequiredOptionOfAlternativesIsMissing(ReportItemMessage):
    """
    At least one option has to be specified

    option_names -- options from which at least one has to be specified
    option_type -- describes the option
    """

    option_names: List[str]
    deprecated_names: List[str] = field(default_factory=list)
    option_type: Optional[str] = None
    _code = codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING

    @property
    def message(self) -> str:
        flag_name_list = [
            (name in self.deprecated_names, name) for name in self.option_names
        ]
        str_list = [
            f"'{item[1]}' (deprecated)" if item[0] else f"'{item[1]}'"
            for item in sorted(flag_name_list)
        ]
        if not str_list:
            options_str = ""
        elif len(str_list) == 1:
            options_str = str_list[0]
        else:
            options_str = "{} or {}".format(
                ", ".join(str_list[:-1]), str_list[-1]
            )
        desc = format_optional(self.option_type)
        return f"{desc}option {options_str} has to be specified"


@dataclass(frozen=True)
class InvalidOptions(ReportItemMessage):
    """
    Specified option names are not valid, usually an error or a warning

    option_names -- specified invalid option names
    allowed -- possible allowed option names
    option_type -- describes the option
    allowed_patterns -- allowed user defined options patterns
    """

    option_names: List[str]
    allowed: List[str]
    option_type: Optional[str] = None
    allowed_patterns: List[str] = field(default_factory=list)
    _code = codes.INVALID_OPTIONS

    @property
    def message(self) -> str:
        template = "invalid {desc}option{plural_options} {option_names_list},"
        if not self.allowed and not self.allowed_patterns:
            template += " there are no options allowed"
        elif not self.allowed_patterns:
            template += " allowed option{plural_allowed} {allowed_values}"
        elif not self.allowed:
            template += (
                " allowed are options matching patterns: "
                "{allowed_patterns_values}"
            )
        else:
            template += (
                " allowed option{plural_allowed} {allowed_values}"
                " and"
                " options matching patterns: {allowed_patterns_values}"
            )
        return template.format(
            desc=format_optional(self.option_type),
            allowed_values=format_list(self.allowed),
            allowed_patterns_values=format_list(self.allowed_patterns),
            option_names_list=format_list(self.option_names),
            plural_options=format_plural(self.option_names, "", "s:"),
            plural_allowed=format_plural(self.allowed, " is", "s are:"),
        )


@dataclass(frozen=True)
class InvalidUserdefinedOptions(ReportItemMessage):
    """
    Specified option names defined by a user are not valid

    This is different than invalid_options. In this case, the options are
    supposed to be defined by a user. This report carries information that the
    option names do not meet requirements, i.e. contain not allowed characters.
    Invalid_options is used when the options are predefined by pcs (or
    underlying tools).

    option_names -- specified invalid option names
    allowed_characters -- which characters are allowed in the names
    option_type -- describes the option
    """

    option_names: List[str]
    allowed_characters: str
    option_type: Optional[str] = None
    _code = codes.INVALID_USERDEFINED_OPTIONS

    @property
    def message(self) -> str:
        return (
            "invalid {desc}option{plural_options} {option_names_list}, "
            "{desc}options may contain {allowed_characters} characters only"
        ).format(
            desc=format_optional(self.option_type),
            option_names_list=format_list(self.option_names),
            plural_options=format_plural(self.option_names, "", "s:"),
            allowed_characters=self.allowed_characters,
        )


@dataclass(frozen=True)
class InvalidOptionType(ReportItemMessage):
    """
    Specified value is not of a valid type for the option

    option_name -- option name whose value is not of a valid type
    allowed_types -- list of allowed types or string description
    """

    option_name: str
    allowed_types: Union[List[str], str]
    _code = codes.INVALID_OPTION_TYPE

    @property
    def message(self) -> str:
        return "specified {option_name} is not valid, use {hint}".format(
            hint=(
                format_list(cast(List[str], self.allowed_types))
                if is_iterable_not_str(self.allowed_types)
                else self.allowed_types
            ),
            option_name=self.option_name,
        )


@dataclass(frozen=True)
class InvalidOptionValue(ReportItemMessage):
    """
    Specified value is not valid for the option, usually an error or a warning

    option_name -- specified option name whose value is not valid
    option_value -- specified value which is not valid
    allowed_values -- a list or description of allowed values, may be undefined
    cannot_be_empty -- the value is empty and that is not allowed
    forbidden_characters -- characters the value cannot contain
    """

    option_name: str
    option_value: str
    allowed_values: Union[List[str], str, None]
    cannot_be_empty: bool = False
    forbidden_characters: Optional[str] = None
    _code = codes.INVALID_OPTION_VALUE

    @property
    def message(self) -> str:
        if self.cannot_be_empty:
            template = "{option_name} cannot be empty"
        elif self.forbidden_characters:
            template = (
                "{option_name} cannot contain {forbidden_characters} characters"
            )
        else:
            template = "'{option_value}' is not a valid {option_name} value"
        if self.allowed_values:
            template += ", use {hint}"
        return template.format(
            hint=(
                format_list(cast(List[str], self.allowed_values))
                if (
                    self.allowed_values
                    and is_iterable_not_str(self.allowed_values)
                )
                else self.allowed_values
            ),
            option_name=self.option_name,
            option_value=self.option_value,
            forbidden_characters=self.forbidden_characters,
        )


@dataclass(frozen=True)
class DeprecatedOption(ReportItemMessage):
    """
    Specified option name is deprecated and has been replaced by other option(s)

    option_name -- the deprecated option
    replaced_by -- new option(s) to be used instead
    option_type -- option description
    """

    option_name: str
    replaced_by: List[str]
    option_type: Optional[str] = None
    _code = codes.DEPRECATED_OPTION

    @property
    def message(self) -> str:
        return (
            "{desc}option '{option_name}' is deprecated and might be removed "
            "in a future release, therefore it should not be used{hint}"
        ).format(
            option_name=self.option_name,
            desc=format_optional(self.option_type),
            hint=format_optional(
                format_list(self.replaced_by), ", use {} instead"
            ),
        )


@dataclass(frozen=True)
class DeprecatedOptionValue(ReportItemMessage):
    """
    Specified option value is deprecated and has been replaced by other value

    option_name -- option which value is deprecated
    deprecated_value -- value which should not be used anymore
    replaced_by -- new value to be used instead
    """

    option_name: str
    deprecated_value: str
    replaced_by: Optional[str] = None
    _code = codes.DEPRECATED_OPTION_VALUE

    @property
    def message(self) -> str:
        return (
            "Value '{deprecated_value}' of option {option_name} is deprecated "
            "and might be removed in a future release, therefore it should not "
            "be used{replaced_by}"
        ).format(
            deprecated_value=self.deprecated_value,
            option_name=self.option_name,
            replaced_by=format_optional(
                self.replaced_by, f", use '{self.replaced_by}' value instead"
            ),
        )


@dataclass(frozen=True)
class MutuallyExclusiveOptions(ReportItemMessage):
    """
    Entered options can not coexist

    option_names -- contain entered mutually exclusive options
    option_type -- describes the option
    """

    option_names: List[str]
    option_type: Optional[str] = None
    _code = codes.MUTUALLY_EXCLUSIVE_OPTIONS

    @property
    def message(self) -> str:
        return "Only one of {desc}options {option_names} can be used".format(
            desc=format_optional(self.option_type),
            option_names=format_list_custom_last_separator(
                self.option_names, " and "
            ),
        )


@dataclass(frozen=True)
class InvalidCibContent(ReportItemMessage):
    """
    Given cib content is not valid

    report -- human readable explanation of a cib invalidity (a stderr of
        `crm_verify`)
    can_be_more_verbose -- can the user ask for a more verbose report
    """

    report: str
    can_be_more_verbose: bool
    _code = codes.INVALID_CIB_CONTENT

    @property
    def message(self) -> str:
        return f"invalid cib:\n{self.report}"


@dataclass(frozen=True)
class InvalidIdIsEmpty(ReportItemMessage):
    """
    Empty string was specified as an id, which is not valid

    id_description -- describe id's role
    """

    id_description: str
    _code = codes.INVALID_ID_IS_EMPTY

    @property
    def message(self) -> str:
        return f"{self.id_description} cannot be empty"


@dataclass(frozen=True)
class InvalidIdBadChar(ReportItemMessage):
    """
    specified id is not valid as it contains a forbidden character

    id -- specified id
    id_description -- describe id's role
    invalid_character -- forbidden character
    is_first_char -- is it the first character which is forbidden?
    """

    id: str  # pylint: disable=invalid-name
    id_description: str
    invalid_character: str
    is_first_char: bool
    _code = codes.INVALID_ID_BAD_CHAR

    @property
    def message(self) -> str:
        desc = "first " if self.is_first_char else ""
        return (
            f"invalid {self.id_description} '{self.id}', "
            f"'{self.invalid_character}' is not a valid {desc}character for a "
            f"{self.id_description}"
        )


@dataclass(frozen=True)
class InvalidIdType(ReportItemMessage):
    """
    Specified type of id (plain, pattern, ...) is not valid

    id_type -- specified type of an id
    allowed_types -- list of allowed types
    """

    id_type: str
    allowed_types: list[str]
    _code = codes.INVALID_ID_TYPE

    @property
    def message(self) -> str:
        hint = format_list(self.allowed_types)
        return (
            f"'{self.id_type}' is not a valid type of ID specification, "
            f"use {hint}"
        )


@dataclass(frozen=True)
class InvalidTimeoutValue(ReportItemMessage):
    """
    Specified timeout is not valid (number or other format e.g. 2min)

    timeout -- specified invalid timeout
    """

    timeout: str
    _code = codes.INVALID_TIMEOUT_VALUE

    @property
    def message(self) -> str:
        return f"'{self.timeout}' is not a valid number of seconds to wait"


@dataclass(frozen=True)
class InvalidScore(ReportItemMessage):
    """
    Specified score value is not valid

    score -- specified score value
    """

    score: str
    _code = codes.INVALID_SCORE

    @property
    def message(self) -> str:
        return (
            f"invalid score '{self.score}', use integer or INFINITY or "
            "-INFINITY"
        )


@dataclass(frozen=True)
class RunExternalProcessStarted(ReportItemMessage):
    """
    Information about running an external process

    command -- the external process command
    stdin -- passed to the external process via its stdin
    environment -- environment variables for the command
    """

    command: str
    stdin: Optional[str]
    environment: Mapping[str, str]
    _code = codes.RUN_EXTERNAL_PROCESS_STARTED

    @property
    def message(self) -> str:
        return (
            "Running: {command}\nEnvironment:{env_part}\n{stdin_part}"
        ).format(
            command=self.command,
            stdin_part=format_optional(
                self.stdin, "--Debug Input Start--\n{}\n--Debug Input End--\n"
            ),
            env_part=(
                ""
                if not self.environment
                else "\n"
                + "\n".join(
                    [
                        f"  {key}={val}"
                        for key, val in sorted(self.environment.items())
                    ]
                )
            ),
        )


@dataclass(frozen=True)
class RunExternalProcessFinished(ReportItemMessage):
    """
    Information about result of running an external process

    command -- the external process command
    return_value -- external process's return (exit) code
    stdout -- external process's stdout
    stderr -- external process's stderr
    """

    command: str
    return_value: int
    stdout: str
    stderr: str
    _code = codes.RUN_EXTERNAL_PROCESS_FINISHED

    @property
    def message(self) -> str:
        return (
            f"Finished running: {self.command}\n"
            f"Return value: {self.return_value}\n"
            "--Debug Stdout Start--\n"
            f"{self.stdout}\n"
            "--Debug Stdout End--\n"
            "--Debug Stderr Start--\n"
            f"{self.stderr}\n"
            "--Debug Stderr End--\n"
        )


@dataclass(frozen=True)
class RunExternalProcessError(ReportItemMessage):
    """
    Attempt to run an external process failed

    command -- the external process command
    reason -- error description
    """

    command: str
    reason: str
    _code = codes.RUN_EXTERNAL_PROCESS_ERROR

    @property
    def message(self) -> str:
        return f"unable to run command {self.command}: {self.reason}"


@dataclass(frozen=True)
class NoActionNecessary(ReportItemMessage):
    """
    Configuration already satisfy change that was requested by the user,
    therefore no action/change of configuration is necessary.
    """

    _code = codes.NO_ACTION_NECESSARY

    @property
    def message(self) -> str:
        return "No action necessary, requested change would have no effect"


@dataclass(frozen=True)
class NodeCommunicationStarted(ReportItemMessage):
    """
    Request is about to be sent to a remote node, debug info

    target -- where the request is about to be sent to
    data -- request's data
    """

    target: str
    data: str
    _code = codes.NODE_COMMUNICATION_STARTED

    @property
    def message(self) -> str:
        data = format_optional(
            self.data, "--Debug Input Start--\n{}\n--Debug Input End--\n"
        )
        return f"Sending HTTP Request to: {self.target}\n{data}"


@dataclass(frozen=True)
class NodeCommunicationFinished(ReportItemMessage):
    """
    Remote node request has been finished, debug info

    target -- where the request was sent to
    response_code -- response return code
    response_data -- response data
    """

    target: str
    response_code: int
    response_data: str
    _code = codes.NODE_COMMUNICATION_FINISHED

    @property
    def message(self) -> str:
        return (
            f"Finished calling: {self.target}\n"
            f"Response Code: {self.response_code}\n"
            "--Debug Response Start--\n"
            f"{self.response_data}\n"
            "--Debug Response End--\n"
        )


@dataclass(frozen=True)
class NodeCommunicationDebugInfo(ReportItemMessage):
    """
    Node communication debug info from pycurl

    target -- request target
    data -- pycurl communication data
    """

    target: str
    data: str
    _code = codes.NODE_COMMUNICATION_DEBUG_INFO

    @property
    def message(self) -> str:
        return (
            f"Communication debug info for calling: {self.target}\n"
            "--Debug Communication Info Start--\n"
            f"{self.data}\n"
            "--Debug Communication Info End--\n"
        )


@dataclass(frozen=True)
class NodeCommunicationNotConnected(ReportItemMessage):
    """
    An error occurred when connecting to a remote node, debug info

    node -- node address / name
    reason -- description of the error
    """

    node: str
    reason: str
    _code = codes.NODE_COMMUNICATION_NOT_CONNECTED

    @property
    def message(self) -> str:
        return f"Unable to connect to {self.node} ({self.reason})"


@dataclass(frozen=True)
class NodeCommunicationNoMoreAddresses(ReportItemMessage):
    """
    Request failed and there are no more addresses to try it again
    """

    node: str
    request: str
    _code = codes.NODE_COMMUNICATION_NO_MORE_ADDRESSES

    @property
    def message(self) -> str:
        return f"Unable to connect to '{self.node}' via any of its addresses"


@dataclass(frozen=True)
class NodeCommunicationErrorNotAuthorized(ReportItemMessage):
    """
    Node rejected a request as we are not authorized

    node -- node address / name
    command -- executed command
    reason -- description of the error
    """

    node: str
    command: str
    reason: str
    _code = codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED

    @property
    def message(self) -> str:
        return f"Unable to authenticate to {self.node} ({self.reason})"


@dataclass(frozen=True)
class NodeCommunicationErrorPermissionDenied(ReportItemMessage):
    """
    Node rejected a request as we do not have permissions to run the request

    node -- node address / name
    command -- executed command
    reason -- description of the error
    """

    node: str
    command: str
    reason: str
    _code = codes.NODE_COMMUNICATION_ERROR_PERMISSION_DENIED

    @property
    def message(self) -> str:
        return f"{self.node}: Permission denied ({self.reason})"


@dataclass(frozen=True)
class NodeCommunicationErrorUnsupportedCommand(ReportItemMessage):
    """
    Node rejected a request as it does not support the request

    node -- node address / name
    command -- executed command
    reason -- description of the error
    """

    node: str
    command: str
    reason: str
    _code = codes.NODE_COMMUNICATION_ERROR_UNSUPPORTED_COMMAND

    @property
    def message(self) -> str:
        return (
            f"{self.node}: Unsupported command ({self.reason}), try upgrading "
            "pcsd"
        )


@dataclass(frozen=True)
class NodeCommunicationCommandUnsuccessful(ReportItemMessage):
    """
    Node rejected a request for another reason with a plain text explanation

    node -- node address / name
    command -- executed command
    reason -- description of the error
    """

    node: str
    command: str
    reason: str
    _code = codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL

    @property
    def message(self) -> str:
        return f"{self.node}: {self.reason}"


@dataclass(frozen=True)
class NodeCommunicationError(ReportItemMessage):
    """
    Node rejected a request for another reason (may be faulty node)

    node -- node address / name
    command -- executed command
    reason -- description of the error
    """

    node: str
    command: str
    reason: str
    _code = codes.NODE_COMMUNICATION_ERROR

    @property
    def message(self) -> str:
        return f"Error connecting to {self.node} ({self.reason})"


@dataclass(frozen=True)
class NodeCommunicationErrorUnableToConnect(ReportItemMessage):
    """
    We were unable to connect to a node

    node -- node address / name
    command -- executed command
    reason -- description of the error
    """

    node: str
    command: str
    reason: str
    _code = codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT

    @property
    def message(self) -> str:
        return f"Unable to connect to {self.node} ({self.reason})"


@dataclass(frozen=True)
class NodeCommunicationErrorTimedOut(ReportItemMessage):
    """
    Communication with node timed out.

    node -- node address / name
    command -- executed command
    reason -- description of the error
    """

    node: str
    command: str
    reason: str
    _code = codes.NODE_COMMUNICATION_ERROR_TIMED_OUT

    @property
    def message(self) -> str:
        return f"{self.node}: Connection timeout ({self.reason})"


@dataclass(frozen=True)
class NodeCommunicationProxyIsSet(ReportItemMessage):
    """
    Warning when connection failed and there is proxy set in environment
    variables
    """

    node: str = ""
    address: str = ""
    _code = codes.NODE_COMMUNICATION_PROXY_IS_SET

    @property
    def message(self) -> str:
        return "Proxy is set in environment variables, try disabling it"


@dataclass(frozen=True)
class NodeCommunicationRetrying(ReportItemMessage):
    """
    Request failed due communication error connecting via specified address,
    therefore trying another address if there is any.
    """

    node: str
    failed_address: str
    failed_port: str
    next_address: str
    next_port: str
    request: str
    _code = codes.NODE_COMMUNICATION_RETRYING

    @property
    def message(self) -> str:
        return (
            f"Unable to connect to '{self.node}' via address "
            f"'{self.failed_address}' and port '{self.failed_port}'. Retrying "
            f"request '{self.request}' via address '{self.next_address}' and "
            f"port '{self.next_port}'"
        )


@dataclass(frozen=True)
class DefaultsCanBeOverridden(ReportItemMessage):
    """
    Warning when settings defaults (op_defaults, rsc_defaults...)
    """

    _code = codes.DEFAULTS_CAN_BE_OVERRIDDEN

    @property
    def message(self) -> str:
        return (
            "Defaults do not apply to resources which override them with their "
            "own defined values"
        )


@dataclass(frozen=True)
class CorosyncAuthkeyWrongLength(ReportItemMessage):
    """
    Wrong corosync authkey length.
    """

    _code = codes.COROSYNC_AUTHKEY_WRONG_LENGTH
    actual_length: int
    min_length: int
    max_length: int

    @property
    def message(self) -> str:
        if self.min_length == self.max_length:
            template = (
                "{max_length} {bytes_allowed} key must be provided for a "
                "corosync authkey, {actual_length} {bytes_provided} key "
                "provided"
            )
        else:
            template = (
                "At least {min_length} and at most {max_length} "
                "{bytes_allowed} key must be provided for a corosync "
                "authkey, {actual_length} {bytes_provided} key provided"
            )
        return template.format(
            min_length=self.min_length,
            max_length=self.max_length,
            actual_length=self.actual_length,
            bytes_allowed=format_plural(self.max_length, "byte"),
            bytes_provided=format_plural(self.actual_length, "byte"),
        )


@dataclass(frozen=True)
class CorosyncConfigDistributionStarted(ReportItemMessage):
    """
    Corosync configuration is about to be sent to nodes
    """

    _code = codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED

    @property
    def message(self) -> str:
        return "Sending updated corosync.conf to nodes..."


@dataclass(frozen=True)
class CorosyncConfigAcceptedByNode(ReportItemMessage):
    """
    corosync configuration has been accepted by a node

    node -- node address / name
    """

    node: str
    _code = codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE

    @property
    def message(self) -> str:
        return f"{self.node}: Succeeded"


@dataclass(frozen=True)
class CorosyncConfigDistributionNodeError(ReportItemMessage):
    """
    Communication error occurred when saving corosync configuration to a node

    node -- faulty node address / name
    """

    node: str
    _code = codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR

    @property
    def message(self) -> str:
        return f"{self.node}: Unable to set corosync config"


@dataclass(frozen=True)
class CorosyncNotRunningCheckStarted(ReportItemMessage):
    """
    We are about to make sure corosync is not running on nodes
    """

    _code = codes.COROSYNC_NOT_RUNNING_CHECK_STARTED

    @property
    def message(self) -> str:
        return "Checking that corosync is not running on nodes..."


@dataclass(frozen=True)
class CorosyncNotRunningCheckNodeError(ReportItemMessage):
    """
    Communication error occurred when checking corosync is not running on a node

    node -- faulty node address / name
    """

    node: str
    _code = codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR

    @property
    def message(self) -> str:
        return (
            f"Unable to check if corosync is not running on node '{self.node}'"
        )


@dataclass(frozen=True)
class CorosyncNotRunningCheckNodeStopped(ReportItemMessage):
    """
    Check that corosync is not running on a node passed, corosync is stopped

    node -- node address / name
    """

    node: str
    _code = codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED

    @property
    def message(self) -> str:
        return f"Corosync is not running on node '{self.node}'"


@dataclass(frozen=True)
class CorosyncNotRunningCheckNodeRunning(ReportItemMessage):
    """
    Check that corosync is not running on a node passed, but corosync is running

    node -- node address / name
    """

    node: str
    _code = codes.COROSYNC_NOT_RUNNING_CHECK_NODE_RUNNING

    @property
    def message(self) -> str:
        return f"Corosync is running on node '{self.node}'"


@dataclass(frozen=True)
class CorosyncNotRunningCheckFinishedRunning(ReportItemMessage):
    """
    Check that corosync is not running revealed corosync is running on nodes
    """

    node_list: list[str]
    _code = codes.COROSYNC_NOT_RUNNING_CHECK_FINISHED_RUNNING

    @property
    def message(self) -> str:
        return (
            "Corosync is running on {node} {node_list}. Requested change can "
            "only be made if the cluster is stopped. In order to proceed, stop "
            "the cluster."
        ).format(
            node=format_plural(self.node_list, "node"),
            node_list=format_list(self.node_list),
        )


@dataclass(frozen=True)
class CorosyncQuorumGetStatusError(ReportItemMessage):
    """
    Unable to get runtime status of quorum

    reason -- an error message
    node -- a node where the error occurred, local node if not specified
    """

    reason: str
    node: str = ""
    _code = codes.COROSYNC_QUORUM_GET_STATUS_ERROR

    @property
    def message(self) -> str:
        node = format_optional(self.node, "{}: ")
        return f"{node}Unable to get quorum status: {self.reason}"


@dataclass(frozen=True)
class CorosyncQuorumHeuristicsEnabledWithNoExec(ReportItemMessage):
    """
    No exec_ is specified, therefore heuristics are effectively disabled
    """

    _code = codes.COROSYNC_QUORUM_HEURISTICS_ENABLED_WITH_NO_EXEC

    @property
    def message(self) -> str:
        return (
            "No exec_NAME options are specified, so heuristics are effectively "
            "disabled"
        )


@dataclass(frozen=True)
class CorosyncQuorumSetExpectedVotesError(ReportItemMessage):
    """
    Unable to set expected votes in a live cluster

    reason -- an error message
    """

    reason: str
    _code = codes.COROSYNC_QUORUM_SET_EXPECTED_VOTES_ERROR

    @property
    def message(self) -> str:
        return f"Unable to set expected votes: {self.reason}"


@dataclass(frozen=True)
class CorosyncConfigReloaded(ReportItemMessage):
    """
    Corosync configuration has been reloaded

    node -- node label on which operation has been executed
    """

    node: str = ""
    _code = codes.COROSYNC_CONFIG_RELOADED

    @property
    def message(self) -> str:
        return "{node}Corosync configuration reloaded".format(
            node=format_optional(self.node, "{}: "),
        )


@dataclass(frozen=True)
class CorosyncConfigReloadError(ReportItemMessage):
    """
    An error occurred when reloading corosync configuration

    reason -- an error message
    node -- node label
    """

    reason: str
    node: str = ""
    _code = codes.COROSYNC_CONFIG_RELOAD_ERROR

    @property
    def message(self) -> str:
        node = format_optional(self.node, "{}: ")
        return f"{node}Unable to reload corosync configuration: {self.reason}"


@dataclass(frozen=True)
class CorosyncConfigReloadNotPossible(ReportItemMessage):
    """
    Corosync configuration cannot be reloaded because corosync is not running
    on the specified node

    node -- node label on which confi
    """

    node: str
    _code = codes.COROSYNC_CONFIG_RELOAD_NOT_POSSIBLE

    @property
    def message(self) -> str:
        return (
            f"{self.node}: Corosync is not running, therefore reload of the "
            "corosync configuration is not possible"
        )


@dataclass(frozen=True)
class CorosyncConfigUnsupportedTransport(ReportItemMessage):
    """
    Transport type defined in corosync.conf is unknown.
    """

    actual_transport: str
    supported_transport_types: List[str]
    _code = codes.COROSYNC_CONFIG_UNSUPPORTED_TRANSPORT

    @property
    def message(self) -> str:
        return (
            "Transport '{actual_transport}' currently configured in "
            "corosync.conf is unsupported. Supported transport types are: "
            "{supported_transport_types}"
        ).format(
            actual_transport=self.actual_transport,
            supported_transport_types=format_list(
                self.supported_transport_types
            ),
        )


@dataclass(frozen=True)
class ParseErrorCorosyncConfMissingClosingBrace(ReportItemMessage):
    """
    Corosync config cannot be parsed due to missing closing brace
    """

    _code = codes.PARSE_ERROR_COROSYNC_CONF_MISSING_CLOSING_BRACE

    @property
    def message(self) -> str:
        return "Unable to parse corosync config: missing closing brace"


@dataclass(frozen=True)
class ParseErrorCorosyncConfUnexpectedClosingBrace(ReportItemMessage):
    """
    Corosync config cannot be parsed due to unexpected closing brace
    """

    _code = codes.PARSE_ERROR_COROSYNC_CONF_UNEXPECTED_CLOSING_BRACE

    @property
    def message(self) -> str:
        return "Unable to parse corosync config: unexpected closing brace"


@dataclass(frozen=True)
class ParseErrorCorosyncConfMissingSectionNameBeforeOpeningBrace(
    ReportItemMessage
):
    """
    Corosync config cannot be parsed due to a section name missing before {
    """

    _code = (
        codes.PARSE_ERROR_COROSYNC_CONF_MISSING_SECTION_NAME_BEFORE_OPENING_BRACE
    )

    @property
    def message(self) -> str:
        return (
            "Unable to parse corosync config: missing a section name before {"
        )


@dataclass(frozen=True)
class ParseErrorCorosyncConfExtraCharactersAfterOpeningBrace(ReportItemMessage):
    """
    Corosync config cannot be parsed due to extra characters after {
    """

    _code = codes.PARSE_ERROR_COROSYNC_CONF_EXTRA_CHARACTERS_AFTER_OPENING_BRACE

    @property
    def message(self) -> str:
        return "Unable to parse corosync config: extra characters after {"


@dataclass(frozen=True)
class ParseErrorCorosyncConfExtraCharactersBeforeOrAfterClosingBrace(
    ReportItemMessage
):
    """
    Corosync config cannot be parsed due to extra characters before or after }
    """

    _code = (
        codes.PARSE_ERROR_COROSYNC_CONF_EXTRA_CHARACTERS_BEFORE_OR_AFTER_CLOSING_BRACE
    )

    @property
    def message(self) -> str:
        return "Unable to parse corosync config: extra characters before or after }"


@dataclass(frozen=True)
class ParseErrorCorosyncConfLineIsNotSectionNorKeyValue(ReportItemMessage):
    """
    Corosync config cannot be parsed due to a line is not a section nor key:val
    """

    _code = codes.PARSE_ERROR_COROSYNC_CONF_LINE_IS_NOT_SECTION_NOR_KEY_VALUE

    @property
    def message(self) -> str:
        return (
            "Unable to parse corosync config: a line is not opening or closing "
            "a section or key: value"
        )


@dataclass(frozen=True)
class ParseErrorCorosyncConf(ReportItemMessage):
    """
    Corosync config cannot be parsed, the cause is not specified. It is better
    to use more specific error if possible.
    """

    _code = codes.PARSE_ERROR_COROSYNC_CONF

    @property
    def message(self) -> str:
        return "Unable to parse corosync config"


@dataclass(frozen=True)
class CorosyncConfigCannotSaveInvalidNamesValues(ReportItemMessage):
    """
    cannot save corosync.conf - it contains forbidden characters which break it

    section_name_list -- bad names of sections
    attribute_name_list -- bad names of attributes
    attribute_value_pairs -- tuples (attribute_name, its_bad_value)
    """

    section_name_list: List[str]
    attribute_name_list: List[str]
    attribute_value_pairs: List[Tuple[str, str]]
    _code = codes.COROSYNC_CONFIG_CANNOT_SAVE_INVALID_NAMES_VALUES

    @property
    def message(self) -> str:
        prefix = "Cannot save corosync.conf containing "
        if (
            not self.section_name_list
            and not self.attribute_name_list
            and not self.attribute_value_pairs
        ):
            return (
                f"{prefix}invalid section names, option names or option values"
            )
        parts = []
        if self.section_name_list:
            parts.append(
                "invalid section name(s): {}".format(
                    format_list(self.section_name_list)
                )
            )
        if self.attribute_name_list:
            parts.append(
                "invalid option name(s): {}".format(
                    format_list(self.attribute_name_list)
                )
            )
        if self.attribute_value_pairs:
            pairs = ", ".join(
                [
                    f"'{value}' (option '{name}')"
                    for name, value in self.attribute_value_pairs
                ]
            )
            parts.append(f"invalid option value(s): {pairs}")
        return "{}{}".format(prefix, "; ".join(parts))


@dataclass(frozen=True)
class CorosyncConfigMissingNamesOfNodes(ReportItemMessage):
    """
    Some nodes in corosync.conf do not have their name set, they will be omitted

    fatal -- if True, pcs cannot continue
    """

    fatal: bool = False
    _code = codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES

    @property
    def message(self) -> str:
        note = (
            "unable to continue" if self.fatal else "those nodes were omitted"
        )
        return (
            f"Some nodes are missing names in corosync.conf, {note}. "
            "Edit corosync.conf and make sure all nodes have their name set."
        )


@dataclass(frozen=True)
class CorosyncConfigMissingIdsOfNodes(ReportItemMessage):
    """
    Some nodes in corosync.conf do not have their id set
    """

    _code = codes.COROSYNC_CONFIG_MISSING_IDS_OF_NODES

    @property
    def message(self) -> str:
        return (
            "Some nodes are missing IDs in corosync.conf. "
            "Edit corosync.conf and make sure all nodes have their nodeid set."
        )


@dataclass(frozen=True)
class CorosyncConfigNoNodesDefined(ReportItemMessage):
    """
    No nodes found in corosync.conf
    """

    _code = codes.COROSYNC_CONFIG_NO_NODES_DEFINED

    @property
    def message(self) -> str:
        return "No nodes found in corosync.conf"


@dataclass(frozen=True)
class CorosyncOptionsIncompatibleWithQdevice(ReportItemMessage):
    """
    Cannot set specified corosync options when qdevice is in use

    options -- incompatible options names
    """

    options: List[str]
    _code = codes.COROSYNC_OPTIONS_INCOMPATIBLE_WITH_QDEVICE

    @property
    def message(self) -> str:
        return (
            "These options cannot be set when the cluster uses a quorum "
            "device: {}"
        ).format(format_list(self.options))


@dataclass(frozen=True)
class CorosyncClusterNameInvalidForGfs2(ReportItemMessage):
    """
    Chosen cluster name will prevent using GFS2 volumes in the cluster

    cluster_name -- the entered cluster name
    max_length -- maximal cluster name length supported by GFS2
    allowed_characters -- allowed cluster name characters supported by GFS2
    """

    cluster_name: str
    max_length: int
    allowed_characters: str
    _code = codes.COROSYNC_CLUSTER_NAME_INVALID_FOR_GFS2

    @property
    def message(self) -> str:
        return (
            f"Chosen cluster name '{self.cluster_name}' will prevent mounting "
            f"GFS2 volumes in the cluster, use at most {self.max_length} "
            f"of {self.allowed_characters} characters; you may safely "
            f"override this if you do not intend to use GFS2"
        )


@dataclass(frozen=True)
class CorosyncBadNodeAddressesCount(ReportItemMessage):
    """
    Wrong number of addresses set for a corosync node.

    actual_count -- how many addresses set for a node
    min_count -- minimal allowed addresses count
    max_count -- maximal allowed addresses count
    node_name -- optionally specify node name
    node_index -- optionally specify node index (helps to identify a node if a
        name is missing)
    """

    actual_count: int
    min_count: int
    max_count: int
    node_name: Optional[str] = None
    node_index: Optional[int] = None
    _code = codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT

    @property
    def message(self) -> str:
        if self.min_count == self.max_count:
            template = (
                "{max_count} {addr_allowed} must be specified for a node, "
                "{actual_count} {addr_specified} specified{node_desc}"
            )
        else:
            template = (
                "At least {min_count} and at most {max_count} {addr_allowed} "
                "must be specified for a node, {actual_count} "
                "{addr_specified} specified{node_desc}"
            )
        node_template = " for node '{}'"
        return template.format(
            node_desc=(
                format_optional(self.node_name, node_template)
                or format_optional(self.node_index, node_template)
            ),
            min_count=self.min_count,
            max_count=self.max_count,
            actual_count=self.actual_count,
            addr_allowed=format_plural(self.max_count, "address"),
            addr_specified=format_plural(self.actual_count, "address"),
        )


@dataclass(frozen=True)
class CorosyncIpVersionMismatchInLinks(ReportItemMessage):
    """
    Mixing IPv4 and IPv6 in one or more links, which is not allowed

    link_numbers -- numbers of links with mismatched IP versions
    """

    link_numbers: List[str] = field(default_factory=list)
    _code = codes.COROSYNC_IP_VERSION_MISMATCH_IN_LINKS

    @property
    def message(self) -> str:
        links = format_optional(
            (format_list(self.link_numbers) if self.link_numbers else ""),
            " on link(s): {}",
        )
        return (
            "Using both IPv4 and IPv6 on one link is not allowed; please, use "
            f"either IPv4 or IPv6{links}"
        )


@dataclass(frozen=True)
class CorosyncAddressIpVersionWrongForLink(ReportItemMessage):
    """
    Cannot use an address in a link as it does not match the link's IP version.

    address -- a provided address
    expected_address_type -- an address type used in a link
    link_number -- number of the link
    """

    address: str
    expected_address_type: str
    # Using Union is a bad practice as it may make deserialization impossible.
    # It works for int and str, though, as they are distinguishable. Code was
    # historically putting either of int and str in here. We need the Union here
    # for backward compatibility reasons.
    link_number: Optional[Union[int, str]] = None
    _code = codes.COROSYNC_ADDRESS_IP_VERSION_WRONG_FOR_LINK

    @property
    def message(self) -> str:
        link = format_optional(self.link_number, "link '{}'", "the link")
        return (
            f"Address '{self.address}' cannot be used in {link} "
            f"because the link uses {self.expected_address_type} addresses"
        )


@dataclass(frozen=True)
class CorosyncLinkNumberDuplication(ReportItemMessage):
    """
    Trying to set one link_number for more links, link numbers must be unique

    link_number_list -- list of nonunique link numbers
    """

    link_number_list: List[str]
    _code = codes.COROSYNC_LINK_NUMBER_DUPLICATION

    @property
    def message(self) -> str:
        nums = format_list(sorted(self.link_number_list, key=_key_numeric))
        return f"Link numbers must be unique, duplicate link numbers: {nums}"


@dataclass(frozen=True)
class CorosyncNodeAddressCountMismatch(ReportItemMessage):
    """
    Nodes do not have the same number of addresses

    dict node_addr_count -- key: node name, value: number of addresses
    """

    node_addr_count: Mapping[str, int]
    _code = codes.COROSYNC_NODE_ADDRESS_COUNT_MISMATCH

    @property
    def message(self) -> str:
        count_node: Dict[int, List[str]] = defaultdict(list)
        for node_name, count in self.node_addr_count.items():
            count_node[count].append(node_name)
        parts = ["All nodes must have the same number of addresses"]
        # List most common number of addresses first.
        for count, nodes in sorted(
            count_node.items(), key=lambda pair: len(pair[1]), reverse=True
        ):
            parts.append(
                "{node} {nodes} {has} {count} {address}".format(
                    node=format_plural(nodes, "node"),
                    nodes=format_list(nodes),
                    has=format_plural(nodes, "has"),
                    count=count,
                    address=format_plural(count, "address"),
                )
            )
        return "; ".join(parts)


@dataclass(frozen=True)
class NodeAddressesAlreadyExist(ReportItemMessage):
    """
    Trying add node(s) with addresses already used by other nodes

    address_list -- list of specified already existing addresses
    """

    address_list: List[str]
    _code = codes.NODE_ADDRESSES_ALREADY_EXIST

    @property
    def message(self) -> str:
        pluralize = partial(format_plural, self.address_list)
        return (
            "Node {address} {addr_list} {_is} already used by existing nodes; "
            "please, use other {address}"
        ).format(
            address=pluralize("address"),
            addr_list=format_list(self.address_list),
            _is=pluralize("is"),
        )


@dataclass(frozen=True)
class NodeAddressesCannotBeEmpty(ReportItemMessage):
    """
    Trying to set an empty node address or remove a node address in an update

    node_name_list -- list of node names with empty addresses
    """

    node_name_list: List[str]
    _code = codes.NODE_ADDRESSES_CANNOT_BE_EMPTY

    @property
    def message(self) -> str:
        return (
            "Empty address set for {node} {node_list}, an address cannot be "
            "empty"
        ).format(
            node=format_plural(self.node_name_list, "node"),
            node_list=format_list(self.node_name_list),
        )


@dataclass(frozen=True)
class NodeAddressesDuplication(ReportItemMessage):
    """
    Trying to set one address for more nodes or links, addresses must be unique

    address_list -- list of nonunique addresses
    """

    address_list: List[str]
    _code = codes.NODE_ADDRESSES_DUPLICATION

    @property
    def message(self) -> str:
        addrs = format_list(self.address_list)
        return f"Node addresses must be unique, duplicate addresses: {addrs}"


@dataclass(frozen=True)
class NodeNamesAlreadyExist(ReportItemMessage):
    """
    Trying add node(s) with name(s) already used by other nodes

    name_list -- list of specified already used node names
    """

    name_list: List[str]
    _code = codes.NODE_NAMES_ALREADY_EXIST

    @property
    def message(self) -> str:
        pluralize = partial(format_plural, self.name_list)
        return (
            "Node {name} {name_list} {_is} already used by existing nodes; "
            "please, use other {name}"
        ).format(
            name=pluralize("name"),
            name_list=format_list(self.name_list),
            _is=pluralize("is"),
        )


@dataclass(frozen=True)
class NodeNamesDuplication(ReportItemMessage):
    """
    Trying to set one node name for more nodes, node names must be unique

    name_list -- list of nonunique node names
    """

    name_list: List[str]
    _code = codes.NODE_NAMES_DUPLICATION

    @property
    def message(self) -> str:
        names = format_list(self.name_list)
        return f"Node names must be unique, duplicate names: {names}"


@dataclass(frozen=True)
class CorosyncNodesMissing(ReportItemMessage):
    """
    No nodes have been specified
    """

    _code = codes.COROSYNC_NODES_MISSING

    @property
    def message(self) -> str:
        return "No nodes have been specified"


@dataclass(frozen=True)
class CorosyncTooManyLinksOptions(ReportItemMessage):
    """
    Options for more links than defined by nodes' addresses have been specified

    links_options_count -- options for how many links have been specified
    links_count -- for how many links is defined
    """

    links_options_count: int
    links_count: int
    _code = codes.COROSYNC_TOO_MANY_LINKS_OPTIONS

    @property
    def message(self) -> str:
        return (
            "Cannot specify options for more links "
            f"({self.links_options_count}) than how many is defined by "
            f"number of addresses per node ({self.links_count})"
        )


@dataclass(frozen=True)
class CorosyncCannotAddRemoveLinksBadTransport(ReportItemMessage):
    """
    Cannot add or remove corosync links, used transport does not allow that

    actual_transport -- transport used in the cluster
    required_transports -- transports allowing links to be added / removed
    add_or_not_remove -- True for add, False for remove
    """

    actual_transport: str
    required_transports: List[str]
    add_or_not_remove: bool
    _code = codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_BAD_TRANSPORT

    @property
    def message(self) -> str:
        action = "adding" if self.add_or_not_remove else "removing"
        return (
            f"Cluster is using {self.actual_transport} transport which does "
            f"not support {action} links"
        )


# TODO: add_or_note_move should be changed to an action
@dataclass(frozen=True)
class CorosyncCannotAddRemoveLinksNoLinksSpecified(ReportItemMessage):
    """
    Cannot add or remove links, no links were specified

    add_or_not_remove -- True for add, False for remove
    """

    add_or_not_remove: bool
    _code = codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_NO_LINKS_SPECIFIED

    @property
    def message(self) -> str:
        return "Cannot {action} links, no links to {action} specified".format(
            action=("add" if self.add_or_not_remove else "remove"),
        )


@dataclass(frozen=True)
class CorosyncCannotAddRemoveLinksTooManyFewLinks(ReportItemMessage):
    """
    Cannot add or remove links, link count would exceed allowed limits

    links_change_count -- how many links to add / remove
    links_new_count -- how many links would be defined after the action
    links_limit_count -- maximal / minimal number of links allowed
    add_or_not_remove -- True for add, False for remove
    """

    links_change_count: int
    links_new_count: int
    links_limit_count: int
    add_or_not_remove: bool
    _code = codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_TOO_MANY_FEW_LINKS

    @property
    def message(self) -> str:
        return (
            "Cannot {action} {links_change_count} {link_change}, there "
            "would be {links_new_count} {link_new} defined which is "
            "{more_less} than allowed number of {links_limit_count} "
            "{link_limit}"
        ).format(
            links_change_count=self.links_change_count,
            links_new_count=self.links_new_count,
            links_limit_count=self.links_limit_count,
            action=("add" if self.add_or_not_remove else "remove"),
            more_less=("more" if self.add_or_not_remove else "less"),
            link_change=format_plural(self.links_change_count, "link"),
            link_new=format_plural(self.links_new_count, "link"),
            link_limit=format_plural(self.links_limit_count, "link"),
        )


@dataclass(frozen=True)
class CorosyncLinkAlreadyExistsCannotAdd(ReportItemMessage):
    """
    Cannot add a link with specified linknumber as it already exists
    """

    link_number: str
    _code = codes.COROSYNC_LINK_ALREADY_EXISTS_CANNOT_ADD

    @property
    def message(self) -> str:
        return f"Cannot add link '{self.link_number}', it already exists"


@dataclass(frozen=True)
class CorosyncLinkDoesNotExistCannotRemove(ReportItemMessage):
    """
    Cannot remove links which don't exist

    link_list -- links to remove which don't exist
    existing_link_list -- linknumbers of existing links
    """

    link_list: List[str]
    existing_link_list: List[str]
    _code = codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_REMOVE

    @property
    def message(self) -> str:
        return (
            "Cannot remove non-existent {link} {to_remove}, existing links: "
            "{existing}"
        ).format(
            link=format_plural(self.link_list, "link"),
            to_remove=format_list(self.link_list),
            existing=format_list(self.existing_link_list),
        )


@dataclass(frozen=True)
class CorosyncLinkDoesNotExistCannotUpdate(ReportItemMessage):
    """
    Cannot set options for the defined link because the link does not exist

    link_number -- number of the link to be updated
    existing_link_list -- linknumbers of existing links
    """

    # Using Union is a bad practice as it may make deserialization impossible.
    # It works for int and str, though, as they are distinguishable. Code was
    # historically putting either of int and str in here. We need the Union here
    # for backward compatibility reasons.
    link_number: Union[int, str]
    existing_link_list: List[str]
    _code = codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_UPDATE

    @property
    def message(self) -> str:
        link_list = format_list(self.existing_link_list)
        return (
            f"Cannot set options for non-existent link '{self.link_number}', "
            f"existing links: {link_list}"
        )


@dataclass(frozen=True)
class CorosyncTransportUnsupportedOptions(ReportItemMessage):
    """
    A type of options is not supported with the given transport
    """

    option_type: str
    actual_transport: str
    required_transports: List[str]
    _code = codes.COROSYNC_TRANSPORT_UNSUPPORTED_OPTIONS

    @property
    def message(self) -> str:
        required_transports = format_list(self.required_transports)
        return (
            f"The {self.actual_transport} transport does not support "
            f"'{self.option_type}' options, use {required_transports} transport"
        )


@dataclass(frozen=True)
class ClusterUuidAlreadySet(ReportItemMessage):
    """
    Cluster UUID has already been set in corosync.conf
    """

    _code = codes.CLUSTER_UUID_ALREADY_SET

    @property
    def message(self) -> str:
        return "Cluster UUID has already been set"


@dataclass(frozen=True)
class QdeviceAlreadyDefined(ReportItemMessage):
    """
    Qdevice is already set up in a cluster, when it was expected not to be
    """

    _code = codes.QDEVICE_ALREADY_DEFINED

    @property
    def message(self) -> str:
        return "quorum device is already defined"


@dataclass(frozen=True)
class QdeviceNotDefined(ReportItemMessage):
    """
    Qdevice is not set up in a cluster, when it was expected to be
    """

    _code = codes.QDEVICE_NOT_DEFINED

    @property
    def message(self) -> str:
        return "no quorum device is defined in this cluster"


@dataclass(frozen=True)
class QdeviceClientReloadStarted(ReportItemMessage):
    """
    Qdevice client configuration is about to be reloaded on nodes
    """

    _code = codes.QDEVICE_CLIENT_RELOAD_STARTED

    @property
    def message(self) -> str:
        return "Reloading qdevice configuration on nodes..."


@dataclass(frozen=True)
class QdeviceAlreadyInitialized(ReportItemMessage):
    """
    Cannot create qdevice on local host, it has been already created

    model -- qdevice model
    """

    model: str
    _code = codes.QDEVICE_ALREADY_INITIALIZED

    @property
    def message(self) -> str:
        return f"Quorum device '{self.model}' has been already initialized"


@dataclass(frozen=True)
class QdeviceNotInitialized(ReportItemMessage):
    """
    Cannot work with qdevice on local host, it has not been created yet

    model -- qdevice model
    """

    model: str
    _code = codes.QDEVICE_NOT_INITIALIZED

    @property
    def message(self) -> str:
        return f"Quorum device '{self.model}' has not been initialized yet"


@dataclass(frozen=True)
class QdeviceInitializationSuccess(ReportItemMessage):
    """
    qdevice was successfully initialized on local host

    model -- qdevice model
    """

    model: str
    _code = codes.QDEVICE_INITIALIZATION_SUCCESS

    @property
    def message(self) -> str:
        return f"Quorum device '{self.model}' initialized"


@dataclass(frozen=True)
class QdeviceInitializationError(ReportItemMessage):
    """
    An error occurred when creating qdevice on local host

    model -- qdevice model
    reason -- an error message
    """

    model: str
    reason: str
    _code = codes.QDEVICE_INITIALIZATION_ERROR

    @property
    def message(self) -> str:
        return (
            f"Unable to initialize quorum device '{self.model}': {self.reason}"
        )


@dataclass(frozen=True)
class QdeviceCertificateDistributionStarted(ReportItemMessage):
    """
    Qdevice certificates are about to be set up on nodes
    """

    _code = codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED

    @property
    def message(self) -> str:
        return "Setting up qdevice certificates on nodes..."


@dataclass(frozen=True)
class QdeviceCertificateAcceptedByNode(ReportItemMessage):
    """
    Qdevice certificates have been saved to a node

    node -- node on which certificates have been saved
    """

    node: str
    _code = codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE

    @property
    def message(self) -> str:
        return f"{self.node}: Succeeded"


@dataclass(frozen=True)
class QdeviceCertificateRemovalStarted(ReportItemMessage):
    """
    Qdevice certificates are about to be removed from nodes
    """

    _code = codes.QDEVICE_CERTIFICATE_REMOVAL_STARTED

    @property
    def message(self) -> str:
        return "Removing qdevice certificates from nodes..."


@dataclass(frozen=True)
class QdeviceCertificateRemovedFromNode(ReportItemMessage):
    """
    Qdevice certificates have been removed from a node

    node -- node on which certificates have been deleted
    """

    node: str
    _code = codes.QDEVICE_CERTIFICATE_REMOVED_FROM_NODE

    @property
    def message(self) -> str:
        return f"{self.node}: Succeeded"


@dataclass(frozen=True)
class QdeviceCertificateImportError(ReportItemMessage):
    """
    An error occurred when importing qdevice certificate to a node

    reason -- an error message
    """

    reason: str
    _code = codes.QDEVICE_CERTIFICATE_IMPORT_ERROR

    @property
    def message(self) -> str:
        return f"Unable to import quorum device certificate: {self.reason}"


@dataclass(frozen=True)
class QdeviceCertificateReadError(ReportItemMessage):
    """
    An error occurred when reading qdevice / qnetd certificate database

    reason -- an error message
    """

    reason: str
    _code = codes.QDEVICE_CERTIFICATE_READ_ERROR

    @property
    def message(self) -> str:
        return f"Unable to read quorum device certificate: {self.reason}"


@dataclass(frozen=True)
class QdeviceCertificateBadFormat(ReportItemMessage):
    """
    Qdevice / qnetd certificate has an unexpected format
    """

    _code = codes.QDEVICE_CERTIFICATE_BAD_FORMAT

    @property
    def message(self) -> str:
        return "Unable to parse quorum device certificate"


@dataclass(frozen=True)
class QdeviceCertificateSignError(ReportItemMessage):
    """
    an error occurred when signing qdevice certificate

    reason -- an error message
    """

    reason: str
    _code = codes.QDEVICE_CERTIFICATE_SIGN_ERROR

    @property
    def message(self) -> str:
        return f"Unable to sign quorum device certificate: {self.reason}"


@dataclass(frozen=True)
class QdeviceDestroySuccess(ReportItemMessage):
    """
    Qdevice configuration successfully removed from local host

    model -- qdevice model
    """

    model: str
    _code = codes.QDEVICE_DESTROY_SUCCESS

    @property
    def message(self) -> str:
        return f"Quorum device '{self.model}' configuration files removed"


@dataclass(frozen=True)
class QdeviceDestroyError(ReportItemMessage):
    """
    An error occurred when removing qdevice configuration from local host

    model -- qdevice model
    reason -- an error message
    """

    model: str
    reason: str
    _code = codes.QDEVICE_DESTROY_ERROR

    @property
    def message(self) -> str:
        return f"Unable to destroy quorum device '{self.model}': {self.reason}"


@dataclass(frozen=True)
class QdeviceNotRunning(ReportItemMessage):
    """
    Qdevice is expected to be running but is not running

    model -- qdevice model
    """

    model: str
    _code = codes.QDEVICE_NOT_RUNNING

    @property
    def message(self) -> str:
        return f"Quorum device '{self.model}' is not running"


@dataclass(frozen=True)
class QdeviceGetStatusError(ReportItemMessage):
    """
    Unable to get runtime status of qdevice

    model -- qdevice model
    reason -- an error message
    """

    model: str
    reason: str
    _code = codes.QDEVICE_GET_STATUS_ERROR

    @property
    def message(self) -> str:
        return (
            f"Unable to get status of quorum device '{self.model}': "
            f"{self.reason}"
        )


@dataclass(frozen=True)
class QdeviceUsedByClusters(ReportItemMessage):
    """
    Qdevice is currently being used by clusters, cannot stop it unless forced
    """

    clusters: List[str]
    _code = codes.QDEVICE_USED_BY_CLUSTERS

    @property
    def message(self) -> str:
        cluster_list = format_list(self.clusters)
        return (
            "Quorum device is currently being used by cluster(s): "
            f"{cluster_list}"
        )


@dataclass(frozen=True)
class IdAlreadyExists(ReportItemMessage):
    """
    Specified id already exists in CIB and cannot be used for a new CIB object

    id -- existing id
    """

    id: str  # pylint: disable=invalid-name
    _code = codes.ID_ALREADY_EXISTS

    @property
    def message(self) -> str:
        return f"'{self.id}' already exists"


@dataclass(frozen=True)
class IdBelongsToUnexpectedType(ReportItemMessage):
    """
    Specified id exists but for another element than expected.
    For example user wants to create resource in group that is specifies by id.
    But id does not belong to group.
    """

    id: str  # pylint: disable=invalid-name
    expected_types: List[str]
    current_type: str
    _code = codes.ID_BELONGS_TO_UNEXPECTED_TYPE

    @property
    def message(self) -> str:
        expected_type = _typelist_to_string(self.expected_types, article=True)
        return f"'{self.id}' is not {expected_type}"


@dataclass(frozen=True)
class ObjectWithIdInUnexpectedContext(ReportItemMessage):
    """
    Object specified by object_type (tag) and object_id exists but not inside
    given context (expected_context_type, expected_context_id).
    """

    object_type: str
    object_id: str
    expected_context_type: str
    expected_context_id: str
    _code = codes.OBJECT_WITH_ID_IN_UNEXPECTED_CONTEXT

    @property
    def message(self) -> str:
        context_type = _type_to_string(self.expected_context_type)
        if self.expected_context_id:
            context = f"{context_type} '{self.expected_context_id}'"
        else:
            context = f"'{context_type}'"
        object_type = _type_to_string(self.object_type)
        return (
            f"{object_type} '{self.object_id}' exists but does not belong to "
            f"{context}"
        )


@dataclass(frozen=True)
class IdNotFound(ReportItemMessage):
    """
    Specified id does not exist in CIB, user referenced a nonexisting id

    id -- specified id
    expected_types -- list of id's roles - expected types with the id
    context_type -- context_id's role / type
    context_id -- specifies the search area
    """

    id: str  # pylint: disable=invalid-name
    expected_types: List[str]
    context_type: str = ""
    context_id: str = ""
    _code = codes.ID_NOT_FOUND

    @property
    def message(self) -> str:
        desc = format_optional(_typelist_to_string(self.expected_types))
        if not self.context_type or not self.context_id:
            return f"{desc}'{self.id}' does not exist"

        return (
            f"there is no {desc}'{self.id}' in the {self.context_type} "
            f"'{self.context_id}'"
        )


@dataclass(frozen=True)
class ResourceBundleAlreadyContainsAResource(ReportItemMessage):
    """
    The bundle already contains a resource, another one caanot be added

    bundle_id -- id of the bundle
    resource_id -- id of the resource already contained in the bundle
    """

    bundle_id: str
    resource_id: str
    _code = codes.RESOURCE_BUNDLE_ALREADY_CONTAINS_A_RESOURCE

    @property
    def message(self) -> str:
        return (
            f"bundle '{self.bundle_id}' already contains resource "
            f"'{self.resource_id}', a bundle may contain at most one resource"
        )


@dataclass(frozen=True)
class CannotGroupResourceWrongType(ReportItemMessage):
    """
    Cannot put a resource into a group as the resource or its parent
    are of an unsupported type

    resource_id -- id of the element which cannot be put into a group
    resource_type -- tag of the element which cannot be put into a group
    parent_id -- id of the parent element which cannot be put into a group
    parent_type -- tag of the parent element which cannot be put into a group
    """

    resource_id: str
    resource_type: str
    parent_id: Optional[str]
    parent_type: Optional[str]
    _code = codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE

    @property
    def message(self) -> str:
        if self.parent_id and self.parent_type:
            return (
                "'{resource_id}' cannot be put into a group because its parent "
                "'{parent_id}' is {_type_article} resource"
            ).format(
                resource_id=self.resource_id,
                parent_id=self.parent_id,
                _type_article=_type_to_string(self.parent_type, article=True),
            )
        return (
            "'{resource_id}' is {_type_article} resource, {_type} "
            "resources cannot be put into a group"
        ).format(
            resource_id=self.resource_id,
            _type_article=_type_to_string(self.resource_type, article=True),
            _type=_type_to_string(self.resource_type, article=False),
        )


@dataclass(frozen=True)
class UnableToGetResourceOperationDigests(ReportItemMessage):
    """
    Unable to get resource digests from pacemaker crm_resource tool.

    output -- stdout and stderr from crm_resource
    """

    output: str
    _code = codes.UNABLE_TO_GET_RESOURCE_OPERATION_DIGESTS

    @property
    def message(self) -> str:
        return f"unable to get resource operation digests:\n{self.output}"


@dataclass(frozen=True)
class CloningStonithResourcesHasNoEffect(ReportItemMessage):
    """
    Reject cloning of stonith resources with an explanation.

    stonith_id_list -- ids of stonith resources
    group_id -- optional id of a group containing stonith resources
    """

    stonith_id_list: List[str]
    group_id: Optional[str] = None
    _code = codes.CLONING_STONITH_RESOURCES_HAS_NO_EFFECT

    @property
    def message(self) -> str:
        resources = format_plural(self.stonith_id_list, "resource")
        group = (
            f"Group '{self.group_id}' contains stonith {resources}. "
            if self.group_id
            else ""
        )
        stonith_list = format_list(self.stonith_id_list)
        return (
            f"{group}No need to clone stonith {resources} "
            f"{stonith_list}, any node can use a stonith resource "
            "(unless specifically banned) regardless of whether the stonith "
            "resource is running on that node or not"
        )


@dataclass(frozen=True)
class StonithResourcesDoNotExist(ReportItemMessage):
    """
    specified stonith resource doesn't exist (e.g. when creating in constraints)
    stoniths -- list of specified stonith id
    """

    stonith_ids: List[str]
    _code = codes.STONITH_RESOURCES_DO_NOT_EXIST

    @property
    def message(self) -> str:
        stoniths = format_list(self.stonith_ids)
        return f"Stonith resource(s) {stoniths} do not exist"


@dataclass(frozen=True)
class StonithRestartlessUpdateOfScsiDevicesNotSupported(ReportItemMessage):
    """
    Pacemaker does not support the digests option for calculation of digests
    needed for restartless update of scsi devices.
    """

    _code = codes.STONITH_RESTARTLESS_UPDATE_OF_SCSI_DEVICES_NOT_SUPPORTED

    @property
    def message(self) -> str:
        return (
            "Restartless update of scsi devices is not supported, please "
            "upgrade pacemaker"
        )


@dataclass(frozen=True)
class StonithRestartlessUpdateUnsupportedAgent(ReportItemMessage):
    """
    Specified resource is not supported for scsi devices update.

    resource_id -- resource id
    resource_type -- resource type
    supported_stonith_types -- list of supported stonith types
    """

    resource_id: str
    resource_type: str
    supported_stonith_types: List[str]
    _code = codes.STONITH_RESTARTLESS_UPDATE_UNSUPPORTED_AGENT

    @property
    def message(self) -> str:
        return (
            "Resource '{resource_id}' is not a stonith resource or its type "
            "'{resource_type}' is not supported for devices update. Supported "
            "{_type}: {supported_types}"
        ).format(
            resource_id=self.resource_id,
            resource_type=self.resource_type,
            _type=format_plural(self.supported_stonith_types, "type"),
            supported_types=format_list(self.supported_stonith_types),
        )


@dataclass(frozen=True)
class StonithUnfencingFailed(ReportItemMessage):
    """
    Unfencing failed on a cluster node.
    """

    reason: str

    _code = codes.STONITH_UNFENCING_FAILED

    @property
    def message(self) -> str:
        return f"Unfencing failed:\n{self.reason}"


@dataclass(frozen=True)
class StonithUnfencingDeviceStatusFailed(ReportItemMessage):
    """
    Unfencing failed on a cluster node.
    """

    device: str
    reason: str

    _code = codes.STONITH_UNFENCING_DEVICE_STATUS_FAILED

    @property
    def message(self) -> str:
        return (
            "Unfencing failed, unable to check status of device "
            f"'{self.device}': {self.reason}"
        )


@dataclass(frozen=True)
class StonithUnfencingSkippedDevicesFenced(ReportItemMessage):
    """
    Unfencing skipped on a cluster node, because fenced devices were found on
    the node.
    """

    devices: List[str]

    _code = codes.STONITH_UNFENCING_SKIPPED_DEVICES_FENCED

    @property
    def message(self) -> str:
        return (
            "Unfencing skipped, {device_pl} {devices} {is_pl} fenced"
        ).format(
            device_pl=format_plural(self.devices, "device"),
            devices=format_list(self.devices),
            is_pl=format_plural(self.devices, "is", "are"),
        )


@dataclass(frozen=True)
class StonithRestartlessUpdateUnableToPerform(ReportItemMessage):
    """
    Unable to update scsi devices without restart for various reason

    reason -- reason
    reason_type -- type for reason differentiation
    """

    reason: str
    reason_type: types.StonithRestartlessUpdateUnableToPerformReason = (
        const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_OTHER
    )
    _code = codes.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM

    @property
    def message(self) -> str:
        return (
            "Unable to perform restartless update of scsi devices: "
            f"{self.reason}"
        )


@dataclass(frozen=True)
class StonithRestartlessUpdateMissingMpathKeys(ReportItemMessage):
    """
    Unable to update mpath devices because reservation keys for some nodes are
    missing.

    pcmk_host_map_value -- a string which specifies nodes to keys map
    missing_nodes -- nodes which do not have keys
    """

    pcmk_host_map_value: Optional[str]
    missing_nodes: List[str]
    _code = codes.STONITH_RESTARTLESS_UPDATE_MISSING_MPATH_KEYS

    @property
    def message(self) -> str:
        if not self.pcmk_host_map_value:
            return "Missing mpath reservation keys, 'pcmk_host_map' not set"
        keys = format_plural(self.missing_nodes, "key")
        nodes = format_plural(self.missing_nodes, "node")
        node_list = format_list(self.missing_nodes)
        node_names = f": {node_list},"
        if not self.missing_nodes:
            keys = "keys"
            nodes = "nodes"
            node_names = ""
        return (
            f"Missing mpath reservation {keys} for {nodes}{node_names} in "
            f"'pcmk_host_map' value: '{self.pcmk_host_map_value}'"
        )


@dataclass(frozen=True)
class ResourceRunningOnNodes(ReportItemMessage):
    """
    Resource is running on some nodes. Taken from cluster state.

    resource_id -- represent the resource
    """

    resource_id: str
    roles_with_nodes: Dict[str, List[str]]
    _code = codes.RESOURCE_RUNNING_ON_NODES

    @property
    def message(self) -> str:
        role_label_map = {
            "Started": "running",
        }
        state_info: Dict[str, List[str]] = {}
        for state, node_list in self.roles_with_nodes.items():
            state_info.setdefault(
                role_label_map.get(state, state.lower()), []
            ).extend(node_list)

        return "resource '{resource_id}' is {detail_list}".format(
            resource_id=self.resource_id,
            detail_list="; ".join(
                sorted(
                    [
                        "{run_type} on {node} {node_list}".format(
                            run_type=run_type,
                            node=format_plural(node_list, "node"),
                            node_list=format_list(node_list),
                        )
                        for run_type, node_list in state_info.items()
                    ]
                )
            ),
        )


@dataclass(frozen=True)
class ResourceDoesNotRun(ReportItemMessage):
    """
    Resource is not running on any node. Taken from cluster state.

    resource_id -- represent the resource
    """

    resource_id: str
    _code = codes.RESOURCE_DOES_NOT_RUN

    @property
    def message(self) -> str:
        return f"resource '{self.resource_id}' is not running on any node"


@dataclass(frozen=True)
class ResourceIsGuestNodeAlready(ReportItemMessage):
    """
    The resource is already used as guest node (i.e. has meta attribute
    remote-node).

    resource_id -- id of the resource that is guest node
    """

    resource_id: str
    _code = codes.RESOURCE_IS_GUEST_NODE_ALREADY

    @property
    def message(self) -> str:
        return f"the resource '{self.resource_id}' is already a guest node"


@dataclass(frozen=True)
class ResourceIsUnmanaged(ReportItemMessage):
    """
    The resource the user works with is unmanaged (e.g. in enable/disable)

    resource_id -- id of the unmanaged resource
    """

    resource_id: str
    _code = codes.RESOURCE_IS_UNMANAGED

    @property
    def message(self) -> str:
        return f"'{self.resource_id}' is unmanaged"


@dataclass(frozen=True)
class ResourceManagedNoMonitorEnabled(ReportItemMessage):
    """
    The resource which was set to managed mode has no monitor operations enabled

    resource_id -- id of the resource
    """

    resource_id: str
    _code = codes.RESOURCE_MANAGED_NO_MONITOR_ENABLED

    @property
    def message(self) -> str:
        return (
            f"Resource '{self.resource_id}' has no enabled monitor operations"
        )


@dataclass(frozen=True)
class CibLoadError(ReportItemMessage):
    """
    Cannot load cib from cibadmin, cibadmin exited with non-zero code

    reason -- error description
    """

    reason: str
    _code = codes.CIB_LOAD_ERROR

    @property
    def message(self) -> str:
        return "unable to get cib"


@dataclass(frozen=True)
class CibLoadErrorGetNodesForValidation(ReportItemMessage):
    """
    Unable to load CIB, unable to get remote and guest nodes for validation
    """

    _code = codes.CIB_LOAD_ERROR_GET_NODES_FOR_VALIDATION

    @property
    def message(self) -> str:
        return (
            "Unable to load CIB to get guest and remote nodes from it, "
            "those nodes cannot be considered in configuration validation"
        )


@dataclass(frozen=True)
class CibLoadErrorScopeMissing(ReportItemMessage):
    """
    Cannot load cib from cibadmin, specified scope is missing in the cib

    scope -- requested cib scope
    reason -- error description
    """

    scope: str
    reason: str
    _code = codes.CIB_LOAD_ERROR_SCOPE_MISSING

    @property
    def message(self) -> str:
        return f"unable to get cib, scope '{self.scope}' not present in cib"


@dataclass(frozen=True)
class CibLoadErrorBadFormat(ReportItemMessage):
    """
    Cib does not conform to the schema
    """

    reason: str
    _code = codes.CIB_LOAD_ERROR_BAD_FORMAT

    @property
    def message(self) -> str:
        return f"unable to get cib, {self.reason}"


@dataclass(frozen=True)
class CibCannotFindMandatorySection(ReportItemMessage):
    """
    CIB is missing a section which is required to be present

    section -- name of the missing section (element name or path)
    """

    section: str
    _code = codes.CIB_CANNOT_FIND_MANDATORY_SECTION

    @property
    def message(self) -> str:
        return f"Unable to get '{self.section}' section of cib"


@dataclass(frozen=True)
class CibPushError(ReportItemMessage):
    """
    Cannot push cib to cibadmin, cibadmin exited with non-zero code

    reason -- error description
    pushed_cib -- cib which failed to be pushed
    """

    reason: str
    pushed_cib: str
    _code = codes.CIB_PUSH_ERROR

    @property
    def message(self) -> str:
        return f"Unable to update cib\n{self.reason}\n{self.pushed_cib}"


@dataclass(frozen=True)
class CibSaveTmpError(ReportItemMessage):
    """
    Cannot save CIB into a temporary file

    reason -- error description
    """

    reason: str
    _code = codes.CIB_SAVE_TMP_ERROR

    @property
    def message(self) -> str:
        return f"Unable to save CIB to a temporary file: {self.reason}"


@dataclass(frozen=True)
class CibDiffError(ReportItemMessage):
    """
    Cannot obtain a diff of CIBs

    reason -- error description
    cib_old -- the CIB to be diffed against
    cib_new -- the CIB diffed against the old cib
    """

    reason: str
    cib_old: str
    cib_new: str
    _code = codes.CIB_DIFF_ERROR

    @property
    def message(self) -> str:
        return f"Unable to diff CIB: {self.reason}\n{self.cib_new}"


@dataclass(frozen=True)
class CibSimulateError(ReportItemMessage):
    """
    Cannot simulate effects a CIB would have on a live cluster

    reason -- error description
    """

    reason: str
    _code = codes.CIB_SIMULATE_ERROR

    @property
    def message(self) -> str:
        return "Unable to simulate changes in CIB{_reason}".format(
            _reason=format_optional(self.reason, ": {0}"),
        )


@dataclass(frozen=True)
class CrmMonError(ReportItemMessage):
    """
    Cannot load cluster status from crm_mon, crm_mon exited with non-zero code

    reason -- description of the error
    """

    reason: str
    _code = codes.CRM_MON_ERROR

    @property
    def message(self) -> str:
        return "error running crm_mon, is pacemaker running?{reason}".format(
            reason=(
                ("\n" + "\n".join(indent(self.reason.strip().splitlines())))
                if self.reason.strip()
                else ""
            ),
        )


@dataclass(frozen=True)
class BadClusterStateFormat(ReportItemMessage):
    """
    crm_mon xml output does not conform to the schema
    """

    _code = codes.BAD_CLUSTER_STATE_FORMAT

    @property
    def message(self) -> str:
        return "cannot load cluster status, xml does not conform to the schema"


@dataclass(frozen=True)
class BadClusterStateData(ReportItemMessage):
    """
    crm_mon xml output is invalid despite conforming to the schema

    reason -- error description
    """

    reason: Optional[str] = None
    _code = codes.BAD_CLUSTER_STATE_DATA

    @property
    def message(self) -> str:
        return (
            "Cannot load cluster status, xml does not describe valid cluster "
            f"status{format_optional(self.reason, template=': {}')}"
        )


@dataclass(frozen=True)
class ClusterStatusBundleMemberIdAsImplicit(ReportItemMessage):
    """
    Member of bundle in cluster status xml has the same id as one of the
    implicit resources

    bundle_id -- id of the bundle
    bad_ids -- ids of the bad members
    """

    bundle_id: str
    bad_ids: list[str]
    _code = codes.CLUSTER_STATUS_BUNDLE_MEMBER_ID_AS_IMPLICIT

    @property
    def message(self) -> str:
        return (
            "Skipping bundle '{bundle_id}': {resource_word} "
            "{bad_ids} {has} the same id as some of the "
            "implicit bundle resources"
        ).format(
            bundle_id=self.bundle_id,
            resource_word=format_plural(self.bad_ids, "resource"),
            bad_ids=format_list(self.bad_ids),
            has=format_plural(self.bad_ids, "has"),
        )


@dataclass(frozen=True)
class WaitForIdleStarted(ReportItemMessage):
    """
    Waiting for cluster to apply updated configuration and to settle down

    timeout -- wait timeout in seconds
    """

    timeout: int
    _code = codes.WAIT_FOR_IDLE_STARTED

    @property
    def message(self) -> str:
        timeout_str = (
            " (timeout: {timeout} {second_pl})".format(
                timeout=self.timeout,
                second_pl=format_plural(self.timeout, "second"),
            )
            if self.timeout > 0
            else ""
        )
        return (
            "Waiting for the cluster to apply configuration changes"
            f"{timeout_str}..."
        )


@dataclass(frozen=True)
class WaitForIdleTimedOut(ReportItemMessage):
    """
    Waiting for resources (crm_resource --wait) failed, timeout expired

    reason -- error description
    """

    reason: str
    _code = codes.WAIT_FOR_IDLE_TIMED_OUT

    @property
    def message(self) -> str:
        return f"waiting timeout\n\n{self.reason}"


@dataclass(frozen=True)
class WaitForIdleError(ReportItemMessage):
    """
    Waiting for resources (crm_resource --wait) failed

    reason -- error description
    """

    reason: str
    _code = codes.WAIT_FOR_IDLE_ERROR

    @property
    def message(self) -> str:
        return self.reason


@dataclass(frozen=True)
class WaitForIdleNotLiveCluster(ReportItemMessage):
    """
    Cannot wait for the cluster if not running with a live cluster
    """

    _code = codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER

    @property
    def message(self) -> str:
        return "Cannot use 'mocked CIB' together with 'wait'"


@dataclass(frozen=True)
class ResourceRestartError(ReportItemMessage):
    """
    An error occurred when restarting a resource in pacemaker

    reason -- error description
    resource -- resource which has been restarted
    node -- node where the resource has been restarted
    """

    reason: str
    resource: str
    node: Optional[str] = None
    _code = codes.RESOURCE_RESTART_ERROR

    @property
    def message(self) -> str:
        return f"Unable to restart resource '{self.resource}':\n{self.reason}"


@dataclass(frozen=True)
class ResourceRestartNodeIsForMultiinstanceOnly(ReportItemMessage):
    """
    Restart can be limited to a specified node only for multiinstance resources

    resource -- resource to be restarted
    resource_type -- actual type of the resource
    node -- node where the resource was to be restarted
    """

    resource: str
    resource_type: str
    node: str
    _code = codes.RESOURCE_RESTART_NODE_IS_FOR_MULTIINSTANCE_ONLY

    @property
    def message(self) -> str:
        resource_type = _type_to_string(self.resource_type, article=True)
        return (
            "Can only restart on a specific node for a clone or bundle, "
            f"'{self.resource}' is {resource_type}"
        )


@dataclass(frozen=True)
class ResourceRestartUsingParentRersource(ReportItemMessage):
    """
    Multiinstance parent is restarted instead of a specified primitive

    resource -- resource which has been asked to be restarted
    parent -- parent resource to be restarted instead
    """

    resource: str
    parent: str
    _code = codes.RESOURCE_RESTART_USING_PARENT_RESOURCE

    @property
    def message(self) -> str:
        return (
            f"Restarting '{self.parent}' instead...\n"
            "(If a resource is a clone or bundle, you must use the clone or "
            "bundle instead)"
        )


@dataclass(frozen=True)
class ResourceCleanupError(ReportItemMessage):
    """
    An error occurred when deleting resource failed operations in pacemaker

    reason -- error description
    resource -- resource which has been cleaned up
    node -- node which has been cleaned up
    """

    reason: str
    resource: Optional[str] = None
    node: Optional[str] = None
    _code = codes.RESOURCE_CLEANUP_ERROR

    @property
    def message(self) -> str:
        if self.resource:
            return (
                "Unable to forget failed operations of resource: "
                f"{self.resource}\n{self.reason}"
            )
        return f"Unable to forget failed operations of resources\n{self.reason}"


@dataclass(frozen=True)
class ResourceRefreshError(ReportItemMessage):
    """
    An error occurred when deleting resource history in pacemaker

    reason -- error description
    resource -- resource which has been cleaned up
    node -- node which has been cleaned up
    """

    reason: str
    resource: Optional[str] = None
    node: Optional[str] = None
    _code = codes.RESOURCE_REFRESH_ERROR

    @property
    def message(self) -> str:
        if self.resource:
            return (
                "Unable to delete history of resource: "
                f"{self.resource}\n{self.reason}"
            )
        return f"Unable to delete history of resources\n{self.reason}"


@dataclass(frozen=True)
class ResourceRefreshTooTimeConsuming(ReportItemMessage):
    """
    Resource refresh would execute more than threshold operations in a cluster

    threshold -- current threshold for triggering this error
    """

    threshold: int
    _code = codes.RESOURCE_REFRESH_TOO_TIME_CONSUMING

    @property
    def message(self) -> str:
        return (
            "Deleting history of all resources on all nodes will execute more "
            f"than {self.threshold} operations in the cluster, which may "
            "negatively impact the responsiveness of the cluster. "
            "Consider specifying resource and/or node"
        )


@dataclass(frozen=True)
class ResourceOperationIntervalDuplication(ReportItemMessage):
    """
    More operations with the same name and the same interval appeared.
    Each operation with the same name (e.g. monitoring) needs to have a unique
    interval.

    dict duplications see resource operation interval duplication
        in pcs/lib/exchange_formats.md
    """

    duplications: Mapping[str, List[List[str]]]
    _code = codes.RESOURCE_OPERATION_INTERVAL_DUPLICATION

    @property
    def message(self) -> str:
        return (
            "multiple specification of the same operation with the same "
            "interval:\n"
            + "\n".join(
                [
                    "{0} with intervals {1}".format(name, ", ".join(intervals))
                    for name, intervals_list in self.duplications.items()
                    for intervals in intervals_list
                ]
            )
        )


@dataclass(frozen=True)
class ResourceOperationIntervalAdapted(ReportItemMessage):
    """
    Interval of resource operation was adopted to operation (with the same
    name) intervals were unique.  Each operation with the same name (e.g.
    monitoring) need to have unique interval.
    """

    operation_name: str
    original_interval: str
    adapted_interval: str
    _code = codes.RESOURCE_OPERATION_INTERVAL_ADAPTED

    @property
    def message(self) -> str:
        return (
            f"changing a {self.operation_name} operation interval from "
            f"{self.original_interval} to {self.adapted_interval} to make the "
            "operation unique"
        )


@dataclass(frozen=True)
class NodeNotFound(ReportItemMessage):
    """
    Specified node does not exist

    node -- specified node
    searched_types
    """

    node: str
    searched_types: List[str] = field(default_factory=list)
    _code = codes.NODE_NOT_FOUND

    @property
    def message(self) -> str:
        desc = _build_node_description(self.searched_types)
        return f"{desc} '{self.node}' does not appear to exist in configuration"


@dataclass(frozen=True)
class NodeToClearIsStillInCluster(ReportItemMessage):
    """
    specified node is still in cluster and `crm_node --remove` should be not
    used

    node -- specified node
    """

    node: str
    _code = codes.NODE_TO_CLEAR_IS_STILL_IN_CLUSTER

    @property
    def message(self) -> str:
        return (
            f"node '{self.node}' seems to be still in the cluster; this "
            "command should be used only with nodes that have been removed "
            "from the cluster"
        )


@dataclass(frozen=True)
class NodeRemoveInPacemakerFailed(ReportItemMessage):
    """
    Removing nodes from pacemaker failed.

    node_list_to_remove -- nodes which should be removed
    node -- node on which operation was performed
    reason -- reason of failure
    """

    node_list_to_remove: List[str]
    node: str = ""
    reason: str = ""
    _code = codes.NODE_REMOVE_IN_PACEMAKER_FAILED

    @property
    def message(self) -> str:
        return (
            "{node}Unable to remove node(s) {node_list} from pacemaker{reason}"
        ).format(
            node=format_optional(self.node, "{}: "),
            reason=format_optional(self.reason, ": {}"),
            node_list=format_list(self.node_list_to_remove),
        )


@dataclass(frozen=True)
class MultipleResultsFound(ReportItemMessage):
    """
    Multiple result was found when something was looked for. E.g. resource for
    remote node.

    result_type -- specifies what was looked for, e.g. "resource"
    result_identifier_list -- contains identifiers of results e.g. resource
        ids
    search_description -- e.g. name of remote_node
    """

    result_type: str
    result_identifier_list: List[str]
    search_description: str = ""
    _code = codes.MULTIPLE_RESULTS_FOUND

    @property
    def message(self) -> str:
        return "more than one {result_type}{desc} found: {what_found}".format(
            what_found=format_list(self.result_identifier_list),
            desc=format_optional(self.search_description, " for '{}'"),
            result_type=self.result_type,
        )


@dataclass(frozen=True)
class PacemakerSimulationResult(ReportItemMessage):
    """
    This report contains crm_simulate output.

    str plaintext_output -- plaintext output from crm_simulate
    """

    plaintext_output: str
    _code = codes.PACEMAKER_SIMULATION_RESULT

    @property
    def message(self) -> str:
        return f"\nSimulation result:\n{self.plaintext_output}"


@dataclass(frozen=True)
class PacemakerLocalNodeNameNotFound(ReportItemMessage):
    """
    We are unable to figure out pacemaker's local node's name

    reason -- error message
    """

    reason: str
    _code = codes.PACEMAKER_LOCAL_NODE_NAME_NOT_FOUND

    @property
    def message(self) -> str:
        return f"unable to get local node name from pacemaker: {self.reason}"


@dataclass(frozen=True)
class ServiceActionStarted(ReportItemMessage):
    """
    System service action started

    action -- started service action
    service -- service name or description
    instance -- instance of service
    """

    action: types.ServiceAction
    service: str
    instance: str = ""
    _code = codes.SERVICE_ACTION_STARTED

    @property
    def message(self) -> str:
        action_str = _service_action_str(self.action, "ing").capitalize()
        instance_suffix = format_optional(self.instance, INSTANCE_SUFFIX)
        return f"{action_str} {self.service}{instance_suffix}..."


@dataclass(frozen=True)
class ServiceActionFailed(ReportItemMessage):
    """
    System service action failed

    action -- failed service action
    service -- service name or description
    reason -- error message
    node -- node on which service has been requested to start
    instance -- instance of service
    """

    action: types.ServiceAction
    service: str
    reason: str
    node: str = ""
    instance: str = ""
    _code = codes.SERVICE_ACTION_FAILED

    @property
    def message(self) -> str:
        return (
            "{node_prefix}Unable to {action} {service}{instance_suffix}:"
            " {reason}"
        ).format(
            action=_service_action_str(self.action),
            service=self.service,
            reason=self.reason,
            instance_suffix=format_optional(self.instance, INSTANCE_SUFFIX),
            node_prefix=format_optional(self.node, NODE_PREFIX),
        )


@dataclass(frozen=True)
class ServiceActionSucceeded(ReportItemMessage):
    """
    System service action was successful

    action -- successful service action
    service -- service name or description
    node -- node on which service has been requested to start
    instance -- instance of service
    """

    action: types.ServiceAction
    service: str
    node: str = ""
    instance: str = ""
    _code = codes.SERVICE_ACTION_SUCCEEDED

    @property
    def message(self) -> str:
        return "{node_prefix}{service}{instance_suffix} {action}".format(
            action=_service_action_str(self.action, "ed"),
            service=self.service,
            instance_suffix=format_optional(self.instance, INSTANCE_SUFFIX),
            node_prefix=format_optional(self.node, NODE_PREFIX),
        )


@dataclass(frozen=True)
class ServiceActionSkipped(ReportItemMessage):
    """
    System service action was skipped, no error occurred

    action -- skipped service action
    service -- service name or description
    reason why the start has been skipped
    node node on which service has been requested to start
    instance instance of service
    """

    action: types.ServiceAction
    service: str
    reason: str
    node: str = ""
    instance: str = ""
    _code = codes.SERVICE_ACTION_SKIPPED

    @property
    def message(self) -> str:
        return (
            "{node_prefix}not {action} {service}{instance_suffix}: {reason}"
        ).format(
            action=_service_action_str(self.action, "ing"),
            service=self.service,
            reason=self.reason,
            instance_suffix=format_optional(self.instance, INSTANCE_SUFFIX),
            node_prefix=format_optional(self.node, NODE_PREFIX),
        )


@dataclass(frozen=True)
class ServiceUnableToDetectInitSystem(ReportItemMessage):
    """
    Autodetection of currently used init system was not successful, therefore
    system service management is not be available.
    """

    _code = codes.SERVICE_UNABLE_TO_DETECT_INIT_SYSTEM

    @property
    def message(self) -> str:
        return (
            "Unable to detect init system. All actions related to system "
            "services will be skipped."
        )


@dataclass(frozen=True)
class UnableToGetAgentMetadata(ReportItemMessage):
    """
    There were some issues trying to get metadata of agent

    agent -- agent which metadata were unable to obtain
    reason -- reason of failure
    """

    agent: str
    reason: str
    _code = codes.UNABLE_TO_GET_AGENT_METADATA

    @property
    def message(self) -> str:
        return (
            f"Agent '{self.agent}' is not installed or does not provide valid"
            f" metadata: {self.reason}"
        )


@dataclass(frozen=True)
class InvalidResourceAgentName(ReportItemMessage):
    """
    The entered resource agent name is not valid. This name has the internal
    structure. The code needs to work with parts of this structure and fails
    if parts can not be obtained.

    name -- entered name
    """

    name: str
    _code = codes.INVALID_RESOURCE_AGENT_NAME

    @property
    def message(self) -> str:
        return (
            f"Invalid resource agent name '{self.name}'."
            " Use standard:provider:type when standard is 'ocf' or"
            " standard:type otherwise."
        )


@dataclass(frozen=True)
class InvalidStonithAgentName(ReportItemMessage):
    """
    The entered stonith agent name is not valid.

    name -- entered stonith agent name
    """

    name: str
    _code = codes.INVALID_STONITH_AGENT_NAME

    @property
    def message(self) -> str:
        return (
            f"Invalid stonith agent name '{self.name}'. Agent name cannot "
            "contain the ':' character, do not use the 'stonith:' prefix."
        )


@dataclass(frozen=True)
class AgentNameGuessed(ReportItemMessage):
    """
    Resource agent name was deduced from the entered name. Pcs supports the
    using of abbreviated resource agent name (e.g. ocf:heartbeat:Delay =>
    Delay) when it can be clearly deduced.

    entered_name -- entered name
    guessed_name -- deduced name
    """

    entered_name: str
    guessed_name: str
    _code = codes.AGENT_NAME_GUESSED

    @property
    def message(self) -> str:
        return (
            f"Assumed agent name '{self.guessed_name}' (deduced from "
            f"'{self.entered_name}')"
        )


@dataclass(frozen=True)
class AgentNameGuessFoundMoreThanOne(ReportItemMessage):
    """
    More than one agents found based on the search string, specify one of them

    agent -- searched name of an agent
    possible_agents -- full names of agents matching the search
    """

    agent: str
    possible_agents: List[str]
    _code = codes.AGENT_NAME_GUESS_FOUND_MORE_THAN_ONE

    @property
    def message(self) -> str:
        possible = format_list_custom_last_separator(
            self.possible_agents, " or "
        )
        return (
            f"Multiple agents match '{self.agent}', please specify full name: "
            f"{possible}"
        )


@dataclass(frozen=True)
class AgentNameGuessFoundNone(ReportItemMessage):
    """
    Specified agent doesn't exist

    agent -- name of the agent which doesn't exist
    """

    agent: str
    _code = codes.AGENT_NAME_GUESS_FOUND_NONE

    @property
    def message(self) -> str:
        return (
            f"Unable to find agent '{self.agent}', try specifying its full name"
        )


@dataclass(frozen=True)
class AgentImplementsUnsupportedOcfVersion(ReportItemMessage):
    """
    Specified agent implements OCF version not supported by pcs

    agent -- name of the agent
    ocf_version -- OCF version implemented by the agent
    supported_versions -- OCF versions supported by pcs
    """

    agent: str
    ocf_version: str
    supported_versions: List[str]
    _code = codes.AGENT_IMPLEMENTS_UNSUPPORTED_OCF_VERSION

    @property
    def message(self) -> str:
        _version = format_plural(self.supported_versions, "version")
        _is = format_plural(self.supported_versions, "is")
        _version_list = format_list(self.supported_versions)
        return (
            f"Unable to process agent '{self.agent}' as it implements "
            f"unsupported OCF version '{self.ocf_version}', supported "
            f"{_version} {_is}: {_version_list}"
        )


@dataclass(frozen=True)
class AgentGenericError(ReportItemMessage):
    """
    Unspecifed error related to resource / fence agent

    agent -- name of the agent
    """

    agent: str

    @property
    def message(self) -> str:
        return f"Unable to load agent '{self.agent}'"


@dataclass(frozen=True)
class OmittingNode(ReportItemMessage):
    """
    Warning that specified node will be omitted in following actions

    node -- node name
    """

    node: str
    _code = codes.OMITTING_NODE

    @property
    def message(self) -> str:
        return f"Omitting node '{self.node}'"


@dataclass(frozen=True)
class SbdCheckStarted(ReportItemMessage):
    """
    Info that SBD pre-enabling checks started
    """

    _code = codes.SBD_CHECK_STARTED

    @property
    def message(self) -> str:
        return "Running SBD pre-enabling checks..."


@dataclass(frozen=True)
class SbdCheckSuccess(ReportItemMessage):
    """
    info that SBD pre-enabling check finished without issues on specified node

    node -- node name
    """

    node: str
    _code = codes.SBD_CHECK_SUCCESS

    @property
    def message(self) -> str:
        return f"{self.node}: SBD pre-enabling checks done"


@dataclass(frozen=True)
class SbdConfigDistributionStarted(ReportItemMessage):
    """
    Distribution of SBD configuration started
    """

    _code = codes.SBD_CONFIG_DISTRIBUTION_STARTED

    @property
    def message(self) -> str:
        return "Distributing SBD config..."


@dataclass(frozen=True)
class SbdConfigAcceptedByNode(ReportItemMessage):
    """
    info that SBD configuration has been saved successfully on specified node

    node -- node name
    """

    node: str
    _code = codes.SBD_CONFIG_ACCEPTED_BY_NODE

    @property
    def message(self) -> str:
        return f"{self.node}: SBD config saved"


@dataclass(frozen=True)
class UnableToGetSbdConfig(ReportItemMessage):
    """
    Unable to get SBD config from specified node (communication or parsing
    error)

    node -- node name
    reason -- reason of failure
    """

    node: str
    reason: str
    _code = codes.UNABLE_TO_GET_SBD_CONFIG

    @property
    def message(self) -> str:
        return (
            "Unable to get SBD configuration from node '{node}'{reason}"
        ).format(
            node=self.node,
            reason=format_optional(self.reason, ": {}"),
        )


@dataclass(frozen=True)
class SbdDeviceInitializationStarted(ReportItemMessage):
    """
    Initialization of SBD device(s) started
    """

    device_list: List[str]
    _code = codes.SBD_DEVICE_INITIALIZATION_STARTED

    @property
    def message(self) -> str:
        return "Initializing {device} {device_list}...".format(
            device=format_plural(self.device_list, "device"),
            device_list=format_list(self.device_list),
        )


@dataclass(frozen=True)
class SbdDeviceInitializationSuccess(ReportItemMessage):
    """
    Initialization of SBD device(s) succeeded
    """

    device_list: List[str]
    _code = codes.SBD_DEVICE_INITIALIZATION_SUCCESS

    @property
    def message(self) -> str:
        device = format_plural(self.device_list, "Device")
        return f"{device} initialized successfully"


@dataclass(frozen=True)
class SbdDeviceInitializationError(ReportItemMessage):
    """
    Initialization of SBD device failed
    """

    device_list: List[str]
    reason: str
    _code = codes.SBD_DEVICE_INITIALIZATION_ERROR

    @property
    def message(self) -> str:
        return (
            "Initialization of {device} {device_list} failed: {reason}"
        ).format(
            device=format_plural(self.device_list, "device"),
            device_list=format_list(self.device_list),
            reason=self.reason,
        )


@dataclass(frozen=True)
class SbdDeviceListError(ReportItemMessage):
    """
    Command 'sbd list' failed
    """

    device: str
    reason: str
    _code = codes.SBD_DEVICE_LIST_ERROR

    @property
    def message(self) -> str:
        return (
            f"Unable to get list of messages from device '{self.device}': "
            f"{self.reason}"
        )


@dataclass(frozen=True)
class SbdDeviceMessageError(ReportItemMessage):
    """
    Unable to set message 'message' on shared block device 'device'
    for node 'node'.
    """

    device: str
    node: str
    sbd_message: str
    reason: str
    _code = codes.SBD_DEVICE_MESSAGE_ERROR

    @property
    def message(self) -> str:
        return (
            f"Unable to set message '{self.sbd_message}' for node "
            f"'{self.node}' on device '{self.device}': {self.reason}"
        )


@dataclass(frozen=True)
class SbdDeviceDumpError(ReportItemMessage):
    """
    Command 'sbd dump' failed
    """

    device: str
    reason: str
    _code = codes.SBD_DEVICE_DUMP_ERROR

    @property
    def message(self) -> str:
        return (
            f"Unable to get SBD headers from device '{self.device}': "
            f"{self.reason}"
        )


@dataclass(frozen=True)
class FilesDistributionStarted(ReportItemMessage):
    """
    files are about to be sent to nodes

    file_list -- files to be sent
    node_list -- node names where the files are being sent
    """

    file_list: List[str] = field(default_factory=list)
    node_list: List[str] = field(default_factory=list)
    _code = codes.FILES_DISTRIBUTION_STARTED

    @property
    def message(self) -> str:
        return "Sending {description}{where}".format(
            where=format_optional(format_list(self.node_list), " to {}"),
            description=format_list(self.file_list),
        )


@dataclass(frozen=True)
class FilesDistributionSkipped(ReportItemMessage):
    """
    Files distribution skipped due to unreachable nodes or not live cluster

    reason_type -- why was the action skipped (unreachable, not_live_cib)
    file_list -- contains description of files
    node_list -- where the files should have been sent to
    """

    reason_type: types.ReasonType
    file_list: List[str]
    node_list: List[str]
    _code = codes.FILES_DISTRIBUTION_SKIPPED

    @property
    def message(self) -> str:
        return (
            "Distribution of {files} to {nodes} was skipped because "
            "{reason}. Please, distribute the file(s) manually."
        ).format(
            files=format_list(self.file_list),
            nodes=format_list(self.node_list),
            reason=_skip_reason_to_string(self.reason_type),
        )


@dataclass(frozen=True)
class FileDistributionSuccess(ReportItemMessage):
    """
    A file has been successfully distributed to a node

    node -- name of a destination node
    file_description -- name (code) of a successfully put file
    """

    node: str
    file_description: str
    _code = codes.FILE_DISTRIBUTION_SUCCESS

    @property
    def message(self) -> str:
        return (
            f"{self.node}: successful distribution of the file "
            f"'{self.file_description}'"
        )


@dataclass(frozen=True)
class FileDistributionError(ReportItemMessage):
    """
    Cannot put a file to a specific node

    node -- name of a destination node
    file_description -- code of a file
    reason -- an error message
    """

    node: str
    file_description: str
    reason: str
    _code = codes.FILE_DISTRIBUTION_ERROR

    @property
    def message(self) -> str:
        return (
            f"{self.node}: unable to distribute file "
            f"'{self.file_description}': {self.reason}"
        )


@dataclass(frozen=True)
class FilesRemoveFromNodesStarted(ReportItemMessage):
    """
    files are about to be removed from nodes

    file_list -- files to be sent
    node_list -- node names the files are being removed from
    """

    file_list: List[str] = field(default_factory=list)
    node_list: List[str] = field(default_factory=list)
    _code = codes.FILES_REMOVE_FROM_NODES_STARTED

    @property
    def message(self) -> str:
        return "Requesting remove {description}{where}".format(
            where=format_optional(format_list(self.node_list), " from {}"),
            description=format_list(self.file_list),
        )


@dataclass(frozen=True)
class FilesRemoveFromNodesSkipped(ReportItemMessage):
    """
    Files removal skipped due to unreachable nodes or not live cluster

    reason_type -- why was the action skipped (unreachable, not_live_cib)
    file_list -- contains description of files
    node_list -- node names the files are being removed from
    """

    reason_type: types.ReasonType
    file_list: List[str]
    node_list: List[str]
    _code = codes.FILES_REMOVE_FROM_NODES_SKIPPED

    @property
    def message(self) -> str:
        return (
            "Removing {files} from {nodes} was skipped because {reason}. "
            "Please, remove the file(s) manually."
        ).format(
            files=format_list(self.file_list),
            nodes=format_list(self.node_list),
            reason=_skip_reason_to_string(self.reason_type),
        )


@dataclass(frozen=True)
class FileRemoveFromNodeSuccess(ReportItemMessage):
    """
    files was successfully removed nodes

    node -- name of destination node
    file_description -- name (code) of successfully put files
    """

    node: str
    file_description: str
    _code = codes.FILE_REMOVE_FROM_NODE_SUCCESS

    @property
    def message(self) -> str:
        return (
            f"{self.node}: successful removal of the file "
            f"'{self.file_description}'"
        )


@dataclass(frozen=True)
class FileRemoveFromNodeError(ReportItemMessage):
    """
    cannot remove files from specific nodes

    node -- name of destination node
    file_description -- is file code
    reason -- is error message
    """

    node: str
    file_description: str
    reason: str
    _code = codes.FILE_REMOVE_FROM_NODE_ERROR

    @property
    def message(self) -> str:
        return (
            f"{self.node}: unable to remove file '{self.file_description}': "
            f"{self.reason}"
        )


@dataclass(frozen=True)
class ServiceCommandsOnNodesStarted(ReportItemMessage):
    """
    Node was requested for actions
    """

    action_list: List[str] = field(default_factory=list)
    node_list: List[str] = field(default_factory=list)
    _code = codes.SERVICE_COMMANDS_ON_NODES_STARTED

    @property
    def message(self) -> str:
        return "Requesting {description}{where}".format(
            where=format_optional(format_list(self.node_list), " on {}"),
            description=format_list(self.action_list),
        )


@dataclass(frozen=True)
class ServiceCommandsOnNodesSkipped(ReportItemMessage):
    """
    Service actions skipped due to unreachable nodes or not live cluster

    reason_type -- why was the action skipped (unreachable, not_live_cib)
    action_list -- contains description of service actions
    node_list -- destinations where the action should have been executed
    """

    reason_type: types.ReasonType
    action_list: List[str]
    node_list: List[str]
    _code = codes.SERVICE_COMMANDS_ON_NODES_SKIPPED

    @property
    def message(self) -> str:
        return (
            "Running action(s) {actions} on {nodes} was skipped because "
            "{reason}. Please, run the action(s) manually."
        ).format(
            actions=format_list(self.action_list),
            nodes=format_list(self.node_list),
            reason=_skip_reason_to_string(self.reason_type),
        )


@dataclass(frozen=True)
class ServiceCommandOnNodeSuccess(ReportItemMessage):
    """
    Files was successfully distributed on nodes

    service_command_description -- name (code) of successfully service command
    """

    node: str
    service_command_description: str
    _code = codes.SERVICE_COMMAND_ON_NODE_SUCCESS

    @property
    def message(self) -> str:
        return (
            f"{self.node}: successful run of "
            f"'{self.service_command_description}'"
        )


@dataclass(frozen=True)
class ServiceCommandOnNodeError(ReportItemMessage):
    """
    Action on nodes failed

    service_command_description -- name (code) of successfully service command
    reason -- is error message
    """

    node: str
    service_command_description: str
    reason: str
    _code = codes.SERVICE_COMMAND_ON_NODE_ERROR

    @property
    def message(self) -> str:
        return (
            f"{self.node}: service command failed: "
            f"{self.service_command_description}: {self.reason}"
        )


@dataclass(frozen=True)
class InvalidResponseFormat(ReportItemMessage):
    """
    Error message that response in invalid format has been received from
    specified node

    node -- node name
    """

    node: str
    _code = codes.INVALID_RESPONSE_FORMAT

    @property
    def message(self) -> str:
        return f"{self.node}: Invalid format of response"


@dataclass(frozen=True)
class SbdNotUsedCannotSetSbdOptions(ReportItemMessage):
    """
    The cluster is not using SBD, cannot specify SBD options

    options -- list of specified not allowed SBD options
    node -- node name
    """

    options: List[str]
    node: str
    _code = codes.SBD_NOT_USED_CANNOT_SET_SBD_OPTIONS

    @property
    def message(self) -> str:
        return (
            "Cluster is not configured to use SBD, cannot specify SBD "
            "option(s) {options} for node '{node}'"
        ).format(
            options=format_list(self.options),
            node=self.node,
        )


@dataclass(frozen=True)
class SbdWithDevicesNotUsedCannotSetDevice(ReportItemMessage):
    """
    The cluster is not using SBD with devices, cannot specify a device.

    node -- node name
    """

    node: str
    _code = codes.SBD_WITH_DEVICES_NOT_USED_CANNOT_SET_DEVICE

    @property
    def message(self) -> str:
        return (
            "Cluster is not configured to use SBD with shared storage, cannot "
            f"specify SBD devices for node '{self.node}'"
        )


@dataclass(frozen=True)
class SbdNoDeviceForNode(ReportItemMessage):
    """
    No SBD device defined for a node when it should be

    node -- node name
    sbd_enabled_in_cluster -- additional context for displaying the error
    """

    node: str
    sbd_enabled_in_cluster: bool = False
    _code = codes.SBD_NO_DEVICE_FOR_NODE

    @property
    def message(self) -> str:
        if self.sbd_enabled_in_cluster:
            return (
                "Cluster uses SBD with shared storage so SBD devices must be "
                "specified for all nodes, no device specified for node "
                f"'{self.node}'"
            )
        return f"No SBD device specified for node '{self.node}'"


@dataclass(frozen=True)
class SbdTooManyDevicesForNode(ReportItemMessage):
    """
    More than allowed number of SBD devices specified for a node

    node -- node name
    device_list -- list of SND devices specified for the node
    max_devices -- maximum number of SBD devices
    """

    node: str
    device_list: List[str]
    max_devices: int
    _code = codes.SBD_TOO_MANY_DEVICES_FOR_NODE

    @property
    def message(self) -> str:
        devices = format_list(self.device_list)
        return (
            f"At most {self.max_devices} SBD devices can be specified for a "
            f"node, {devices} specified for node '{self.node}'"
        )


@dataclass(frozen=True)
class SbdDevicePathNotAbsolute(ReportItemMessage):
    """
    Path of SBD device is not absolute
    """

    device: str
    node: str
    _code = codes.SBD_DEVICE_PATH_NOT_ABSOLUTE

    @property
    def message(self) -> str:
        return (
            f"Device path '{self.device}' on node '{self.node}' is not absolute"
        )


@dataclass(frozen=True)
class SbdDeviceDoesNotExist(ReportItemMessage):
    """
    Specified device on node doesn't exist
    """

    device: str
    node: str
    _code = codes.SBD_DEVICE_DOES_NOT_EXIST

    @property
    def message(self) -> str:
        return f"{self.node}: device '{self.device}' not found"


@dataclass(frozen=True)
class SbdDeviceIsNotBlockDevice(ReportItemMessage):
    """
    Specified device on node is not block device
    """

    device: str
    node: str
    _code = codes.SBD_DEVICE_IS_NOT_BLOCK_DEVICE

    @property
    def message(self) -> str:
        return f"{self.node}: device '{self.device}' is not a block device"


@dataclass(frozen=True)
class StonithWatchdogTimeoutCannotBeSet(ReportItemMessage):
    """
    Can't set stonith-watchdog-timeout
    """

    reason: types.StonithWatchdogTimeoutCannotBeSetReason
    _code = codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET

    @property
    def message(self) -> str:
        return (
            "stonith-watchdog-timeout can only be unset or set to 0 while "
            + _stonith_watchdog_timeout_reason_to_str(self.reason)
        )


@dataclass(frozen=True)
class StonithWatchdogTimeoutCannotBeUnset(ReportItemMessage):
    """
    Can't unset stonith-watchdog-timeout
    """

    reason: types.StonithWatchdogTimeoutCannotBeSetReason
    _code = codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET

    @property
    def message(self) -> str:
        return (
            "stonith-watchdog-timeout cannot be unset or set to 0 while "
            + _stonith_watchdog_timeout_reason_to_str(self.reason)
        )


@dataclass(frozen=True)
class StonithWatchdogTimeoutTooSmall(ReportItemMessage):
    """
    The value of stonith-watchdog-timeout is too small

    cluster_sbd_watchdog_timeout -- sbd watchdog timeout set in sbd config
    entered_watchdog_timeout -- entered stonith-watchdog-timeout property
    """

    cluster_sbd_watchdog_timeout: int
    entered_watchdog_timeout: str
    _code = codes.STONITH_WATCHDOG_TIMEOUT_TOO_SMALL

    @property
    def message(self) -> str:
        return (
            "The stonith-watchdog-timeout must be greater than SBD watchdog "
            f"timeout '{self.cluster_sbd_watchdog_timeout}', entered "
            f"'{self.entered_watchdog_timeout}'"
        )


@dataclass(frozen=True)
class WatchdogNotFound(ReportItemMessage):
    """
    Watchdog doesn't exist on specified node

    node -- node name
    watchdog -- watchdog device path
    """

    node: str
    watchdog: str
    _code = codes.WATCHDOG_NOT_FOUND

    @property
    def message(self) -> str:
        return (
            f"Watchdog '{self.watchdog}' does not exist on node '{self.node}'"
        )


@dataclass(frozen=True)
class WatchdogInvalid(ReportItemMessage):
    """
    Watchdog path is not an absolute path

    watchdog -- watchdog device path
    """

    watchdog: str
    _code = codes.WATCHDOG_INVALID

    @property
    def message(self) -> str:
        return f"Watchdog path '{self.watchdog}' is invalid."


@dataclass(frozen=True)
class UnableToGetSbdStatus(ReportItemMessage):
    """
    There was (communication or parsing) failure during obtaining status of SBD
    from specified node

    node -- node name
    reason -- reason of failure
    """

    node: str
    reason: str
    _code = codes.UNABLE_TO_GET_SBD_STATUS

    @property
    def message(self) -> str:
        return "Unable to get status of SBD from node '{node}'{reason}".format(
            node=self.node,
            reason=format_optional(self.reason, ": {}"),
        )


@dataclass(frozen=True)
class ClusterRestartRequiredToApplyChanges(ReportItemMessage):
    """
    Warn user a cluster needs to be manually restarted to use new configuration
    """

    _code = codes.CLUSTER_RESTART_REQUIRED_TO_APPLY_CHANGES

    @property
    def message(self) -> str:
        return "Cluster restart is required in order to apply these changes."


@dataclass(frozen=True)
class CibAlertRecipientAlreadyExists(ReportItemMessage):
    """
    Recipient with specified value already exists in alert with id 'alert_id'

    alert_id -- id of alert to which recipient belongs
    recipient_value -- value of recipient
    """

    alert: str
    recipient: str
    _code = codes.CIB_ALERT_RECIPIENT_ALREADY_EXISTS

    @property
    def message(self) -> str:
        return (
            f"Recipient '{self.recipient}' in alert '{self.alert}' "
            "already exists"
        )


@dataclass(frozen=True)
class CibAlertRecipientValueInvalid(ReportItemMessage):
    """
    Invalid recipient value.

    recipient -- recipient value
    """

    recipient: str
    _code = codes.CIB_ALERT_RECIPIENT_VALUE_INVALID

    @property
    def message(self) -> str:
        return f"Recipient value '{self.recipient}' is not valid."


@dataclass(frozen=True)
class CibUpgradeSuccessful(ReportItemMessage):
    """
    Upgrade of CIB schema was successful.
    """

    _code = codes.CIB_UPGRADE_SUCCESSFUL

    @property
    def message(self) -> str:
        return "CIB has been upgraded to the latest schema version."


@dataclass(frozen=True)
class CibUpgradeFailed(ReportItemMessage):
    """
    Upgrade of CIB schema failed.

    reason -- reason of failure
    """

    reason: str
    _code = codes.CIB_UPGRADE_FAILED

    @property
    def message(self) -> str:
        return f"Upgrading of CIB to the latest schema failed: {self.reason}"


@dataclass(frozen=True)
class CibUpgradeFailedToMinimalRequiredVersion(ReportItemMessage):
    """
    Unable to upgrade CIB to minimal required schema version.

    current_version -- current version of CIB schema
    required_version -- required version of CIB schema
    """

    current_version: str
    required_version: str
    _code = codes.CIB_UPGRADE_FAILED_TO_MINIMAL_REQUIRED_VERSION

    @property
    def message(self) -> str:
        return (
            "Unable to upgrade CIB to required schema version"
            f" {self.required_version} or higher. Current version is"
            f" {self.current_version}. Newer version of pacemaker is needed."
        )


@dataclass(frozen=True)
class FileAlreadyExists(ReportItemMessage):
    file_type_code: file_type_codes.FileTypeCode
    file_path: str
    node: str = ""
    _code = codes.FILE_ALREADY_EXISTS

    @property
    def message(self) -> str:
        return "{node}{file_role} file '{file_path}' already exists".format(
            file_path=self.file_path,
            node=format_optional(self.node, NODE_PREFIX),
            file_role=_format_file_role(self.file_type_code),
        )


@dataclass(frozen=True)
class FileIoError(ReportItemMessage):
    """
    Unable to work with a file

    file_type_code -- file type, item of pcs.common.file_type_codes
    operation -- failed action, item of pcs.common.file.RawFileError
    reason -- an error message
    file_path -- file path, optional for cases when unknown (GhostFiles)
    """

    file_type_code: file_type_codes.FileTypeCode
    operation: FileAction
    reason: str
    file_path: str = ""
    _code = codes.FILE_IO_ERROR

    @property
    def message(self) -> str:
        return "Unable to {action} {file_role}{file_path}: {reason}".format(
            reason=self.reason,
            action=_format_file_action(self.operation),
            file_path=format_optional(self.file_path, " '{0}'"),
            file_role=_format_file_role(self.file_type_code),
        )


@dataclass(frozen=True)
class UnsupportedOperationOnNonSystemdSystems(ReportItemMessage):
    _code = codes.UNSUPPORTED_OPERATION_ON_NON_SYSTEMD_SYSTEMS

    @property
    def message(self) -> str:
        return "unsupported operation on non systemd systems"


@dataclass(frozen=True)
class LiveEnvironmentRequired(ReportItemMessage):
    """
    The command cannot operate in a non-live cluster (mocked / ghost files)

    forbidden_options -- list of items forbidden in the command
    """

    forbidden_options: List[file_type_codes.FileTypeCode]
    _code = codes.LIVE_ENVIRONMENT_REQUIRED

    @property
    def message(self) -> str:
        return "This command does not support {forbidden_options}".format(
            forbidden_options=format_list(
                [str(item) for item in self.forbidden_options]
            ),
        )


@dataclass(frozen=True)
class LiveEnvironmentRequiredForLocalNode(ReportItemMessage):
    """
    The operation cannot be performed on CIB in file (not live cluster) if no
    node name is specified i.e. working with the local node
    """

    _code = codes.LIVE_ENVIRONMENT_REQUIRED_FOR_LOCAL_NODE

    @property
    def message(self) -> str:
        return "Node(s) must be specified if mocked CIB is used"


@dataclass(frozen=True)
class LiveEnvironmentNotConsistent(ReportItemMessage):
    """
    The command cannot operate with mixed live / non-live cluster configs

    mocked_files -- given mocked files (pcs.common.file_type_codes)
    required_files -- files that must be mocked as well
    """

    mocked_files: List[file_type_codes.FileTypeCode]
    required_files: List[file_type_codes.FileTypeCode]
    _code = codes.LIVE_ENVIRONMENT_NOT_CONSISTENT

    @property
    def message(self) -> str:
        return (
            "When {given} {_is} specified, {missing} must be specified as well"
        ).format(
            given=format_list([str(item) for item in self.mocked_files]),
            _is=format_plural(self.mocked_files, "is"),
            missing=format_list([str(item) for item in self.required_files]),
        )


@dataclass(frozen=True)
class CorosyncNodeConflictCheckSkipped(ReportItemMessage):
    """
    A command has been run with -f, can't check corosync.conf for node conflicts

    reason_type -- why was the action skipped (unreachable, not_live_cib)
    """

    reason_type: types.ReasonType
    _code = codes.COROSYNC_NODE_CONFLICT_CHECK_SKIPPED

    @property
    def message(self) -> str:
        return (
            "Unable to check if there is a conflict with nodes set in corosync "
            "because {reason}"
        ).format(reason=_skip_reason_to_string(self.reason_type))


@dataclass(frozen=True)
class CorosyncQuorumAtbCannotBeDisabledDueToSbd(ReportItemMessage):
    """
    Quorum option auto_tie_breaker cannot be disabled due to SBD.
    """

    _code = codes.COROSYNC_QUORUM_ATB_CANNOT_BE_DISABLED_DUE_TO_SBD

    @property
    def message(self) -> str:
        return (
            "Unable to disable auto_tie_breaker, SBD fencing would have no "
            "effect"
        )


@dataclass(frozen=True)
class CorosyncQuorumAtbWillBeEnabledDueToSbd(ReportItemMessage):
    """
    Quorum option auto_tie_breaker will be enabled due to a user action in
    order to keep SBD fencing effective. The cluster has to be stopped to make
    this change.
    """

    _code = codes.COROSYNC_QUORUM_ATB_WILL_BE_ENABLED_DUE_TO_SBD

    @property
    def message(self) -> str:
        return (
            "SBD fencing is enabled in the cluster. To keep it effective, "
            "auto_tie_breaker quorum option will be enabled."
        )


@dataclass(frozen=True)
class CorosyncQuorumAtbWillBeEnabledDueToSbdClusterIsRunning(ReportItemMessage):
    """
    Pcs needs to enable quorum option auto_tie_breaker due to a user action in
    order to keep SBD fencing effective. The cluster has to be stopped to make
    this change, but it is currently running.
    """

    _code = (
        codes.COROSYNC_QUORUM_ATB_WILL_BE_ENABLED_DUE_TO_SBD_CLUSTER_IS_RUNNING
    )

    @property
    def message(self) -> str:
        return (
            "SBD fencing is enabled in the cluster. To keep it effective, "
            "auto_tie_breaker quorum option needs to be enabled. This can only "
            "be done when the cluster is stopped. To proceed, stop the cluster, "
            "enable auto_tie_breaker, and start the cluster. Then, repeat the "
            "requested action."
        )


@dataclass(frozen=True)
class CibAclRoleIsAlreadyAssignedToTarget(ReportItemMessage):
    """
    Error that ACL target or group has already assigned role.
    """

    role_id: str
    target_id: str
    _code = codes.CIB_ACL_ROLE_IS_ALREADY_ASSIGNED_TO_TARGET

    @property
    def message(self) -> str:
        return (
            f"Role '{self.role_id}' is already assigned to '{self.target_id}'"
        )


@dataclass(frozen=True)
class CibAclRoleIsNotAssignedToTarget(ReportItemMessage):
    """
    Error that acl role is not assigned to target or group
    """

    role_id: str
    target_id: str
    _code = codes.CIB_ACL_ROLE_IS_NOT_ASSIGNED_TO_TARGET

    @property
    def message(self) -> str:
        return f"Role '{self.role_id}' is not assigned to '{self.target_id}'"


@dataclass(frozen=True)
class CibAclTargetAlreadyExists(ReportItemMessage):
    """
    Error that target with specified id already exists in configuration.
    """

    target_id: str
    _code = codes.CIB_ACL_TARGET_ALREADY_EXISTS

    @property
    def message(self) -> str:
        return f"'{self.target_id}' already exists"


@dataclass(frozen=True)
class CibFencingLevelAlreadyExists(ReportItemMessage):
    """
    Fencing level already exists, it cannot be created
    """

    level: str
    target_type: str
    target_value: Optional[Tuple[str, str]]
    devices: List[str]
    _code = codes.CIB_FENCING_LEVEL_ALREADY_EXISTS

    @property
    def message(self) -> str:
        return (
            "Fencing level for '{target}' at level '{level}' "
            "with device(s) {device_list} already exists"
        ).format(
            level=self.level,
            device_list=format_list(self.devices),
            target=_format_fencing_level_target(
                self.target_type, self.target_value
            ),
        )


@dataclass(frozen=True)
class CibFencingLevelDoesNotExist(ReportItemMessage):
    """
    Fencing level does not exist, it cannot be updated or deleted
    """

    level: str = ""
    target_type: Optional[str] = None
    target_value: Optional[Tuple[str, str]] = None
    devices: List[str] = field(default_factory=list)
    _code = codes.CIB_FENCING_LEVEL_DOES_NOT_EXIST

    @property
    def message(self) -> str:
        return (
            "Fencing level {part_target}{part_level}{part_devices}does not "
            "exist"
        ).format(
            part_target=(
                "for '{0}' ".format(
                    _format_fencing_level_target(
                        self.target_type, self.target_value
                    )
                )
                if self.target_type and self.target_value
                else ""
            ),
            part_level=format_optional(self.level, "at level '{}' "),
            part_devices=format_optional(
                format_list(self.devices), "with device(s) {0} "
            ),
        )


@dataclass(frozen=True)
class CibRemoveResources(ReportItemMessage):
    """
    Information about removal of resources from cib.
    """

    id_list: list[str]
    _code = codes.CIB_REMOVE_RESOURCES

    @property
    def message(self) -> str:
        return "Removing {resource_pl}: {resource_list}".format(
            resource_pl=format_plural(self.id_list, "resource"),
            resource_list=format_list(self.id_list),
        )


@dataclass(frozen=True)
class CibRemoveDependantElements(ReportItemMessage):
    """
    Information about removal of additional cib elements due to dependencies.
    """

    id_tag_map: Mapping[str, str]
    _code = codes.CIB_REMOVE_DEPENDANT_ELEMENTS

    @property
    def message(self) -> str:
        def _format_line(tag: str, ids: list[str]) -> str:
            tag_desc = format_plural(ids, _type_to_string(tag)).capitalize()
            id_list = format_list(ids)
            return f"  {tag_desc}: {id_list}"

        element_pl = format_plural(self.id_tag_map, "element")
        tag_ids_map: Mapping[str, list[str]] = defaultdict(list)
        for _id, tag in self.id_tag_map.items():
            tag_ids_map[tag].append(_id)
        info_lines = "\n".join(
            sorted([_format_line(tag, ids) for tag, ids in tag_ids_map.items()])
        )
        return f"Removing dependant {element_pl}:\n{info_lines}"


@dataclass(frozen=True)
class CibRemoveReferences(ReportItemMessage):
    """
    Information about removal of references from cib elements due to
    dependencies.
    """

    id_tag_map: Mapping[str, str]
    removing_references_from: Mapping[str, StringIterable]

    _code = codes.CIB_REMOVE_REFERENCES

    @property
    def message(self) -> str:
        id_tag_map = defaultdict(lambda: "element", self.id_tag_map)

        def _format_line(tag: str, ids: list[str]) -> str:
            tag_desc = format_plural(ids, _type_to_string(tag)).capitalize()
            id_list = format_list(ids)
            return f"    {tag_desc}: {id_list}"

        def _format_one_element(element_id: str, ids: StringIterable) -> str:
            tag_ids_map = defaultdict(list)
            for _id in ids:
                tag_ids_map[id_tag_map[_id]].append(_id)
            info_lines = "\n".join(
                sorted(
                    [_format_line(tag, ids) for tag, ids in tag_ids_map.items()]
                )
            )
            tag_desc = _type_to_string(id_tag_map[element_id]).capitalize()
            return f"  {tag_desc} '{element_id}' from:\n{info_lines}"

        lines = "\n".join(
            _format_one_element(key, self.removing_references_from[key])
            for key in sorted(self.removing_references_from)
        )

        return f"Removing references:\n{lines}"


@dataclass(frozen=True)
class UseCommandNodeAddRemote(ReportItemMessage):
    """
    Advise the user for more appropriate command.
    """

    _code = codes.USE_COMMAND_NODE_ADD_REMOTE

    @property
    def message(self) -> str:
        return "this command is not sufficient for creating a remote connection"


@dataclass(frozen=True)
class UseCommandNodeAddGuest(ReportItemMessage):
    """
    Advise the user for more appropriate command.
    """

    _code = codes.USE_COMMAND_NODE_ADD_GUEST

    @property
    def message(self) -> str:
        return "this command is not sufficient for creating a guest node"


@dataclass(frozen=True)
class UseCommandNodeRemoveRemote(ReportItemMessage):
    """
    Advise the user for more appropriate command.
    """

    resource_id: Optional[str] = None
    _code = codes.USE_COMMAND_NODE_REMOVE_REMOTE

    @property
    def message(self) -> str:
        return "this command is not sufficient for removing a remote node{id}".format(
            id=format_optional(self.resource_id, template=": '{}'")
        )


@dataclass(frozen=True)
class UseCommandNodeRemoveGuest(ReportItemMessage):
    """
    Advise the user for more appropriate command.
    """

    resource_id: Optional[str] = None
    _code = codes.USE_COMMAND_NODE_REMOVE_GUEST

    @property
    def message(self) -> str:
        return "this command is not sufficient for removing a guest node{id}".format(
            id=format_optional(self.resource_id, template=": '{}")
        )


@dataclass(frozen=True)
class TmpFileWrite(ReportItemMessage):
    """
    It has been written into a temporary file

    file_path -- the file path
    content -- content which has been written
    """

    file_path: str
    content: str
    _code = codes.TMP_FILE_WRITE

    @property
    def message(self) -> str:
        return (
            f"Writing to a temporary file {self.file_path}:\n"
            f"--Debug Content Start--\n{self.content}\n--Debug Content End--\n"
        )


@dataclass(frozen=True)
class NodeAddressesUnresolvable(ReportItemMessage):
    """
    Unable to resolve addresses of cluster nodes to be added

    address_list -- a list of unresolvable addresses
    """

    address_list: List[str]
    _code = codes.NODE_ADDRESSES_UNRESOLVABLE

    @property
    def message(self) -> str:
        addrs = format_list(self.address_list)
        return f"Unable to resolve addresses: {addrs}"


@dataclass(frozen=True)
class UnableToPerformOperationOnAnyNode(ReportItemMessage):
    """
    This report is raised whenever
    pcs.lib.communication.tools.OneByOneStrategyMixin strategy mixin is used
    for network communication and operation failed on all available hosts and
    because of this it is not possible to continue.
    """

    _code = codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE

    @property
    def message(self) -> str:
        return (
            "Unable to perform operation on any available node/host, therefore "
            "it is not possible to continue"
        )


@dataclass(frozen=True)
class HostNotFound(ReportItemMessage):
    """
    Hosts with names in host_list are not included in pcs known hosts,
    therefore it is not possible to communicate with them.
    """

    host_list: List[str]
    _code = codes.HOST_NOT_FOUND

    @property
    def message(self) -> str:
        pluralize = partial(format_plural, self.host_list)
        return "{host} {hosts_comma} {_is} not known to pcs".format(
            host=pluralize("host"),
            hosts_comma=format_list(self.host_list),
            _is=pluralize("is"),
        ).capitalize()


@dataclass(frozen=True)
class NoneHostFound(ReportItemMessage):
    _code = codes.NONE_HOST_FOUND

    @property
    def message(self) -> str:
        return "None of hosts is known to pcs."


@dataclass(frozen=True)
class HostAlreadyAuthorized(ReportItemMessage):
    host_name: str
    _code = codes.HOST_ALREADY_AUTHORIZED

    @property
    def message(self) -> str:
        return f"{self.host_name}: Already authorized"


@dataclass(frozen=True)
class ClusterDestroyStarted(ReportItemMessage):
    host_name_list: List[str]
    _code = codes.CLUSTER_DESTROY_STARTED

    @property
    def message(self) -> str:
        hosts = format_list(self.host_name_list)
        return f"Destroying cluster on hosts: {hosts}..."


@dataclass(frozen=True)
class ClusterDestroySuccess(ReportItemMessage):
    node: str
    _code = codes.CLUSTER_DESTROY_SUCCESS

    @property
    def message(self) -> str:
        return f"{self.node}: Successfully destroyed cluster"


@dataclass(frozen=True)
class ClusterEnableStarted(ReportItemMessage):
    host_name_list: List[str]
    _code = codes.CLUSTER_ENABLE_STARTED

    @property
    def message(self) -> str:
        hosts = format_list(self.host_name_list)
        return f"Enabling cluster on hosts: {hosts}..."


@dataclass(frozen=True)
class ClusterEnableSuccess(ReportItemMessage):
    node: str
    _code = codes.CLUSTER_ENABLE_SUCCESS

    @property
    def message(self) -> str:
        return f"{self.node}: Cluster enabled"


@dataclass(frozen=True)
class ClusterStartStarted(ReportItemMessage):
    host_name_list: List[str]
    _code = codes.CLUSTER_START_STARTED

    @property
    def message(self) -> str:
        hosts = format_list(self.host_name_list)
        return f"Starting cluster on hosts: {hosts}..."


@dataclass(frozen=True)
class ClusterStartSuccess(ReportItemMessage):
    node: str
    _code = codes.CLUSTER_START_SUCCESS

    @property
    def message(self) -> str:
        return f"{self.node}: Cluster started"


@dataclass(frozen=True)
class ServiceNotInstalled(ReportItemMessage):
    node: str
    service_list: List[str]
    _code = codes.SERVICE_NOT_INSTALLED

    @property
    def message(self) -> str:
        services = format_list(self.service_list)
        return (
            f"{self.node}: Required cluster services not installed: {services}"
        )


@dataclass(frozen=True)
class HostAlreadyInClusterConfig(ReportItemMessage):
    """
    A host, which is being added to a cluster, already has cluster configs

    host_name -- a name of the host which is in a cluster already
    """

    host_name: str
    _code = codes.HOST_ALREADY_IN_CLUSTER_CONFIG

    @property
    def message(self) -> str:
        return (
            f"{self.host_name}: The host seems to be in a cluster already as "
            "cluster configuration files have been found on the host"
        )


@dataclass(frozen=True)
class HostAlreadyInClusterServices(ReportItemMessage):
    """
    A host, which is being added to a cluster, already runs cluster daemons

    host_name -- a name of the host which is in a cluster already
    service_list -- list of cluster daemons running on the host
    """

    host_name: str
    service_list: List[str]
    _code = codes.HOST_ALREADY_IN_CLUSTER_SERVICES

    @property
    def message(self) -> str:
        services = format_list(self.service_list)
        services_plural = format_plural(self.service_list, "service")
        are_plural = format_plural(self.service_list, "is")
        return (
            f"{self.host_name}: The host seems to be in a cluster already as "
            f"the following {services_plural} {are_plural} found to be "
            f"running: {services}. If the host is not part of a cluster, stop "
            f"the {services_plural} and retry"
        )


@dataclass(frozen=True)
class ServiceVersionMismatch(ReportItemMessage):
    service: str
    hosts_version: Mapping[str, str]
    _code = codes.SERVICE_VERSION_MISMATCH

    @property
    def message(self) -> str:
        version_host: Dict[str, List[str]] = defaultdict(list)
        for host_name, version in self.hosts_version.items():
            version_host[version].append(host_name)
        parts = [f"Hosts do not have the same version of '{self.service}'"]
        # List most common versions first.
        for version, hosts in sorted(
            version_host.items(), key=lambda pair: len(pair[1]), reverse=True
        ):
            pluralize = partial(format_plural, hosts)
            parts.append(
                "{host} {hosts} {has} version {version}".format(
                    host=pluralize("host"),
                    hosts=format_list(hosts),
                    has=pluralize("has"),
                    version=version,
                )
            )
        return "; ".join(parts)


@dataclass(frozen=True)
class WaitForNodeStartupStarted(ReportItemMessage):
    node_name_list: List[str]
    _code = codes.WAIT_FOR_NODE_STARTUP_STARTED

    @property
    def message(self) -> str:
        nodes = format_list(self.node_name_list)
        return f"Waiting for node(s) to start: {nodes}..."


@dataclass(frozen=True)
class WaitForNodeStartupTimedOut(ReportItemMessage):
    _code = codes.WAIT_FOR_NODE_STARTUP_TIMED_OUT

    @property
    def message(self) -> str:
        return "Node(s) startup timed out"


@dataclass(frozen=True)
class WaitForNodeStartupError(ReportItemMessage):
    _code = codes.WAIT_FOR_NODE_STARTUP_ERROR

    @property
    def message(self) -> str:
        return "Unable to verify all nodes have started"


@dataclass(frozen=True)
class WaitForNodeStartupWithoutStart(ReportItemMessage):
    """
    User requested waiting for nodes to start without instructing pcs to start
    the nodes
    """

    _code = codes.WAIT_FOR_NODE_STARTUP_WITHOUT_START

    @property
    def message(self) -> str:
        return "Cannot specify 'wait' without specifying 'start'"


@dataclass(frozen=True)
class PcsdVersionTooOld(ReportItemMessage):
    node: str
    _code = codes.PCSD_VERSION_TOO_OLD

    @property
    def message(self) -> str:
        return (
            f"{self.node}: Old version of pcsd is running on the node, "
            "therefore it is unable to perform the action"
        )


@dataclass(frozen=True)
class PcsdSslCertAndKeyDistributionStarted(ReportItemMessage):
    """
    We are about to distribute pcsd SSL certificate and key to nodes

    node_name_list -- node names to distribute to
    """

    node_name_list: List[str]
    _code = codes.PCSD_SSL_CERT_AND_KEY_DISTRIBUTION_STARTED

    @property
    def message(self) -> str:
        nodes = format_list(self.node_name_list)
        return f"Synchronizing pcsd SSL certificates on node(s) {nodes}..."


@dataclass(frozen=True)
class PcsdSslCertAndKeySetSuccess(ReportItemMessage):
    """
    Pcsd SSL certificate and key have been successfully saved on a node

    node -- node name
    """

    node: str
    _code = codes.PCSD_SSL_CERT_AND_KEY_SET_SUCCESS

    @property
    def message(self) -> str:
        return f"{self.node}: Success"


@dataclass(frozen=True)
class ClusterWillBeDestroyed(ReportItemMessage):
    """
    If the user continues with force, cluster will be destroyed on some hosts
    """

    _code = codes.CLUSTER_WILL_BE_DESTROYED

    @property
    def message(self) -> str:
        return (
            "Some nodes are already in a cluster. Enforcing this will destroy "
            "existing cluster on those nodes. You should remove the nodes from "
            "their clusters instead to keep the clusters working properly"
        )


@dataclass(frozen=True)
class ClusterSetupSuccess(ReportItemMessage):
    _code = codes.CLUSTER_SETUP_SUCCESS

    @property
    def message(self) -> str:
        return "Cluster has been successfully set up."


@dataclass(frozen=True)
class UsingDefaultAddressForHost(ReportItemMessage):
    """
    When no address was specified for a host, a default address was used for it
    """

    host_name: str
    address: str
    address_source: types.DefaultAddressSource
    _code = codes.USING_DEFAULT_ADDRESS_FOR_HOST

    @property
    def message(self) -> str:
        return (
            f"No addresses specified for host '{self.host_name}', using "
            f"'{self.address}'"
        )


@dataclass(frozen=True)
class ResourceInBundleNotAccessible(ReportItemMessage):
    bundle_id: str
    inner_resource_id: str
    _code = codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE

    @property
    def message(self) -> str:
        return (
            f"Resource '{self.inner_resource_id}' will not be accessible by "
            f"the cluster inside bundle '{self.bundle_id}', at least one of "
            "bundle options 'control-port' or 'ip-range-start' has to be "
            "specified"
        )


@dataclass(frozen=True)
class UsingDefaultWatchdog(ReportItemMessage):
    """
    No watchdog has been specified for the node, therefore pcs will use
    a default watchdog.
    """

    watchdog: str
    node: str
    _code = codes.USING_DEFAULT_WATCHDOG

    @property
    def message(self) -> str:
        return (
            f"No watchdog has been specified for node '{self.node}'. Using "
            f"default watchdog '{self.watchdog}'"
        )


@dataclass(frozen=True)
class CannotRemoveAllClusterNodes(ReportItemMessage):
    """
    It is not possible to remove all cluster nodes using 'pcs cluster node
    remove' command. 'pcs cluster destroy --all' should be used in such case.
    """

    _code = codes.CANNOT_REMOVE_ALL_CLUSTER_NODES

    @property
    def message(self) -> str:
        return "No nodes would be left in the cluster"


@dataclass(frozen=True)
class UnableToConnectToAnyRemainingNode(ReportItemMessage):
    _code = codes.UNABLE_TO_CONNECT_TO_ANY_REMAINING_NODE

    @property
    def message(self) -> str:
        return "Unable to connect to any remaining cluster node"


@dataclass(frozen=True)
class UnableToConnectToAllRemainingNodes(ReportItemMessage):
    """
    Some of remaining cluster nodes are unreachable. 'pcs cluster sync' should
    be executed on now online nodes when the offline nodes come back online.

    node_list -- names of nodes which are staying in the cluster and are
        currently unreachable
    """

    node_list: List[str]
    _code = codes.UNABLE_TO_CONNECT_TO_ALL_REMAINING_NODE

    @property
    def message(self) -> str:
        return ("Remaining cluster {node} {nodes} could not be reached").format(
            node=format_plural(self.node_list, "node"),
            nodes=format_list(self.node_list),
        )


@dataclass(frozen=True)
class NodesToRemoveUnreachable(ReportItemMessage):
    """
    Nodes which should be removed are currently unreachable. 'pcs cluster
    destroy' should be executed on these nodes when they come back online.

    node_list -- names of nodes which are being removed from the cluster but
        they are currently unreachable
    """

    node_list: List[str]
    _code = codes.NODES_TO_REMOVE_UNREACHABLE

    @property
    def message(self) -> str:
        return (
            "Removed {node} {nodes} could not be reached and subsequently "
            "deconfigured"
        ).format(
            node=format_plural(self.node_list, "node"),
            nodes=format_list(self.node_list),
        )


@dataclass(frozen=True)
class NodeUsedAsTieBreaker(ReportItemMessage):
    """
    Node which should be removed is currently used as a tie breaker for a
    qdevice, therefore it is not possible to remove it from the cluster.

    node -- node name
    node_id -- node id
    """

    node: Optional[str]
    node_id: Optional[str]
    _code = codes.NODE_USED_AS_TIE_BREAKER

    @property
    def message(self) -> str:
        return (
            f"Node '{self.node}' with id '{self.node_id}' is used as a tie "
            "breaker for a qdevice and therefore cannot be removed"
        )


@dataclass(frozen=True)
class CorosyncQuorumWillBeLost(ReportItemMessage):
    """
    Ongoing action will cause loss of the quorum in the cluster.
    """

    _code = codes.COROSYNC_QUORUM_WILL_BE_LOST

    @property
    def message(self) -> str:
        return "This action will cause a loss of the quorum"


@dataclass(frozen=True)
class CorosyncQuorumLossUnableToCheck(ReportItemMessage):
    """
    It is not possible to check if ongoing action will cause loss of the quorum
    """

    _code = codes.COROSYNC_QUORUM_LOSS_UNABLE_TO_CHECK

    @property
    def message(self) -> str:
        return (
            "Unable to determine whether this action will cause a loss of the "
            "quorum"
        )


@dataclass(frozen=True)
class SbdListWatchdogError(ReportItemMessage):
    """
    Unable to get list of available watchdogs from sbd. Sbd cmd reutrned non 0.

    reason -- stderr of command
    """

    reason: str
    _code = codes.SBD_LIST_WATCHDOG_ERROR

    @property
    def message(self) -> str:
        return f"Unable to query available watchdogs from sbd: {self.reason}"


@dataclass(frozen=True)
class SbdWatchdogNotSupported(ReportItemMessage):
    """
    Specified watchdog is not supported in sbd (softdog?).

    node -- node name
    watchdog -- watchdog path
    """

    node: str
    watchdog: str
    _code = codes.SBD_WATCHDOG_NOT_SUPPORTED

    @property
    def message(self) -> str:
        return (
            f"{self.node}: Watchdog '{self.watchdog}' is not supported (it "
            "may be a software watchdog)"
        )


@dataclass(frozen=True)
class SbdWatchdogValidationInactive(ReportItemMessage):
    """
    Warning message about not validating watchdog.
    """

    _code = codes.SBD_WATCHDOG_VALIDATION_INACTIVE

    @property
    def message(self) -> str:
        return "Not validating the watchdog"


@dataclass(frozen=True)
class SbdWatchdogTestError(ReportItemMessage):
    """
    Sbd test watchdog exited with an error.
    """

    reason: str
    _code = codes.SBD_WATCHDOG_TEST_ERROR

    @property
    def message(self) -> str:
        return f"Unable to initialize test of the watchdog: {self.reason}"


@dataclass(frozen=True)
class SbdWatchdogTestMultipleDevices(ReportItemMessage):
    """
    No watchdog device has been specified for test. Because of multiple
    available watchdogs, watchdog device to test has to be specified.
    """

    _code = codes.SBD_WATCHDOG_TEST_MULTIPLE_DEVICES

    @property
    def message(self) -> str:
        return (
            "Multiple watchdog devices available, therefore, watchdog which "
            "should be tested has to be specified."
        )


@dataclass(frozen=True)
class SbdWatchdogTestFailed(ReportItemMessage):
    """
    System has not been reset.
    """

    _code = codes.SBD_WATCHDOG_TEST_FAILED

    @property
    def message(self) -> str:
        return "System should have been reset already"


@dataclass(frozen=True)
class SystemWillReset(ReportItemMessage):
    _code = codes.SYSTEM_WILL_RESET

    @property
    def message(self) -> str:
        return "System will reset shortly"


@dataclass(frozen=True)
class ResourceBundleUnsupportedContainerType(ReportItemMessage):
    bundle_id: str
    supported_container_types: List[str]
    updating_options: bool = True
    _code = codes.RESOURCE_BUNDLE_UNSUPPORTED_CONTAINER_TYPE

    @property
    def message(self) -> str:
        container_types = format_list(self.supported_container_types)
        inner_text = format_optional(
            self.updating_options,
            ", therefore it is not possible to set its container options",
        )
        return (
            f"Bundle '{self.bundle_id}' uses unsupported container type"
            f"{inner_text}. Supported container types are: {container_types}"
        )


@dataclass(frozen=True)
class FenceHistoryCommandError(ReportItemMessage):
    """
    Pacemaker command for working with fence history returned an error

    reason -- output of the pacemaker command
    command -- the action of the command - what it should have achieved
    """

    reason: str
    command: types.FenceHistoryCommandType
    _code = codes.FENCE_HISTORY_COMMAND_ERROR

    @property
    def message(self) -> str:
        command_label = {
            const.FENCE_HISTORY_COMMAND_CLEANUP: "cleanup",
            const.FENCE_HISTORY_COMMAND_SHOW: "show",
            const.FENCE_HISTORY_COMMAND_UPDATE: "update",
        }.get(self.command, self.command)
        return f"Unable to {command_label} fence history: {self.reason}"


@dataclass(frozen=True)
class FenceHistoryNotSupported(ReportItemMessage):
    """
    Pacemaker does not support the fence history feature
    """

    _code = codes.FENCE_HISTORY_NOT_SUPPORTED

    @property
    def message(self) -> str:
        return "Fence history is not supported, please upgrade pacemaker"


@dataclass(frozen=True)
class ResourceInstanceAttrValueNotUnique(ReportItemMessage):
    """
    Value of a resource instance attribute is not unique in the configuration
    when creating/updating a resource

    instance_attr_name -- name of attr which should be unique
    instance_attr_value -- value which is already used by some resources
    agent_name -- resource agent name of resource
    resource_id_list -- resource ids which already have the instance_attr_name
        set to instance_attr_value
    """

    instance_attr_name: str
    instance_attr_value: str
    agent_name: str
    resource_id_list: List[str]
    _code = codes.RESOURCE_INSTANCE_ATTR_VALUE_NOT_UNIQUE

    @property
    def message(self) -> str:
        return (
            "Value '{val}' of option '{attr}' is not unique across "
            "'{agent}' resources. Following resources are configured "
            "with the same value of the instance attribute: {res_id_list}"
        ).format(
            val=self.instance_attr_value,
            attr=self.instance_attr_name,
            agent=self.agent_name,
            res_id_list=format_list(self.resource_id_list),
        )


@dataclass(frozen=True)
class ResourceInstanceAttrGroupValueNotUnique(ReportItemMessage):
    """
    Value of a group of resource instance attributes is not unique in the
    configuration when creating/updating a resource

    group_name -- name of a group of attributes
    instance_attrs_map -- attributes which should be unique and their values
    agent_name -- resource agent name of the resources
    resource_id_list -- resources which already have the same instance_attr_values
    """

    group_name: str
    instance_attrs_map: Dict[str, str]
    agent_name: str
    resource_id_list: List[str]
    _code = codes.RESOURCE_INSTANCE_ATTR_GROUP_VALUE_NOT_UNIQUE

    @property
    def message(self) -> str:
        attr_names, attr_values = zip(*sorted(self.instance_attrs_map.items()))
        attr_names_str = format_list_dont_sort(list(attr_names))
        attr_values_str = format_list_dont_sort(list(attr_values))
        options = format_plural(self.instance_attrs_map, "option")
        res_id_list = format_list(self.resource_id_list)
        return (
            f"Value {attr_values_str} of {options} {attr_names_str} (group "
            f"'{self.group_name}') is not unique across '{self.agent_name}' "
            f"resources. Following resources are configured with the same "
            f"values of the instance attributes: {res_id_list}"
        )


@dataclass(frozen=True)
class CannotLeaveGroupEmptyAfterMove(ReportItemMessage):
    """
    User is trying to add resources to another group and their old group would
    be left empty and need to be deleted. Deletion is not yet migrated to lib.

    str group_id -- ID of original group that would be deleted
    list inner_resource_ids -- List of group members
    """

    group_id: str
    inner_resource_ids: List[str]
    _code = codes.CANNOT_LEAVE_GROUP_EMPTY_AFTER_MOVE

    @property
    def message(self) -> str:
        return (
            "Unable to move {resource_pl} {resource_list} as it would leave "
            "group '{group_id}' empty."
        ).format(
            resource_pl=format_plural(self.inner_resource_ids, "resource"),
            resource_list=format_list(self.inner_resource_ids),
            group_id=self.group_id,
        )


@dataclass(frozen=True)
class CannotMoveResourceBundleInner(ReportItemMessage):
    """
    User is trying to move a bundle's inner resource

    resource_id -- id of the resource to be moved
    bundle_id -- id of the relevant parent bundle resource
    """

    resource_id: str
    bundle_id: str
    _code = codes.CANNOT_MOVE_RESOURCE_BUNDLE_INNER

    @property
    def message(self) -> str:
        return (
            "Resources cannot be moved out of their bundles. If you want to "
            f"move a bundle, use the bundle id ({self.bundle_id})"
        )


@dataclass(frozen=True)
class CannotMoveResourceMultipleInstances(ReportItemMessage):
    """
    User is trying to move a resource of which more than one instance is running

    resource_id -- id of the resource to be moved
    """

    resource_id: str
    _code = codes.CANNOT_MOVE_RESOURCE_MULTIPLE_INSTANCES

    @property
    def message(self) -> str:
        return (
            f"more than one instance of resource '{self.resource_id}' is "
            "running, thus the resource cannot be moved"
        )


@dataclass(frozen=True)
class CannotMoveResourceMultipleInstancesNoNodeSpecified(ReportItemMessage):
    """
    User is trying to move a resource of which more than one instance is running
    without specifying a destination node

    resource_id -- id of the resource to be moved
    """

    resource_id: str
    _code = codes.CANNOT_MOVE_RESOURCE_MULTIPLE_INSTANCES_NO_NODE_SPECIFIED

    @property
    def message(self) -> str:
        return (
            f"more than one instance of resource '{self.resource_id}' is "
            "running, thus the resource cannot be moved, "
            "unless a destination node is specified"
        )


@dataclass(frozen=True)
class CannotMoveResourceCloneInner(ReportItemMessage):
    """
    User is trying to move a clone's inner resource which is not possible

    resource_id -- id of the resource to be moved
    clone_id -- id of relevant parent clone resource
    """

    resource_id: str
    clone_id: str
    _code = codes.CANNOT_MOVE_RESOURCE_CLONE_INNER

    @property
    def message(self) -> str:
        return (
            "to move clone resources you must use the clone id "
            f"({self.clone_id})"
        )


@dataclass(frozen=True)
class CannotMoveResourcePromotableInner(ReportItemMessage):
    """
    User is trying to move a promotable clone's inner resource

    resource_id -- id of the resource to be moved
    promotable_id -- id of relevant parent promotable resource
    """

    resource_id: str
    promotable_id: str
    _code = codes.CANNOT_MOVE_RESOURCE_PROMOTABLE_INNER

    @property
    def message(self) -> str:
        return (
            "to move promotable clone resources you must use the "
            f"promotable clone id ({self.promotable_id})"
        )


@dataclass(frozen=True)
class CannotMoveResourceMasterResourceNotPromotable(ReportItemMessage):
    """
    User is trying to move a non-promotable resource and limit it to master role

    resource_id -- id of the resource to be moved
    promotable_id -- id of relevant parent promotable resource
    """

    resource_id: str
    promotable_id: str = ""
    _code = codes.CANNOT_MOVE_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE

    @property
    def message(self) -> str:
        return _resource_move_ban_clear_master_resource_not_promotable(
            self.promotable_id
        )


@dataclass(frozen=True)
class CannotMoveResourceNotRunning(ReportItemMessage):
    """
    It is not possible to move a stopped resource and remove constraint used
    for moving it

    resource_id -- id of the resource to be moved
    """

    resource_id: str
    _code = codes.CANNOT_MOVE_RESOURCE_NOT_RUNNING

    @property
    def message(self) -> str:
        return (
            f"It is not possible to move resource '{self.resource_id}' as it "
            "is not running at the moment"
        )


@dataclass(frozen=True)
class CannotMoveResourceStoppedNoNodeSpecified(ReportItemMessage):
    """
    When moving a stopped resource, a node to move it to must be specified

    resource_id -- id of the resource to be moved
    """

    resource_id: str
    _code = codes.CANNOT_MOVE_RESOURCE_STOPPED_NO_NODE_SPECIFIED

    @property
    def message(self) -> str:
        # Use both "moving" and "banning" to let user know using "ban" instead
        # of "move" will not help
        return "You must specify a node when moving/banning a stopped resource"


@dataclass(frozen=True)
class ResourceMovePcmkError(ReportItemMessage):
    """
    crm_resource exited with an error when moving a resource

    resource_id -- id of the resource to be moved
    stdout -- stdout of crm_resource
    stderr -- stderr of crm_resource
    """

    resource_id: str
    stdout: str
    stderr: str
    _code = codes.RESOURCE_MOVE_PCMK_ERROR

    @property
    def message(self) -> str:
        return _stdout_stderr_to_string(
            self.stdout,
            self.stderr,
            prefix=f"cannot move resource '{self.resource_id}'",
        )


@dataclass(frozen=True)
class ResourceMovePcmkSuccess(ReportItemMessage):
    """
    crm_resource exited successfully when moving a resource

    resource_id -- id of the resource to be moved
    stdout -- stdout of crm_resource
    stderr -- stderr of crm_resource
    """

    resource_id: str
    stdout: str
    stderr: str
    _code = codes.RESOURCE_MOVE_PCMK_SUCCESS

    @property
    def message(self) -> str:
        return _resource_move_ban_pcmk_success(self.stdout, self.stderr)


@dataclass(frozen=True)
class CannotBanResourceBundleInner(ReportItemMessage):
    """
    User is trying to ban a bundle's inner resource

    resource_id -- id of the resource to be banned
    bundle_id -- id of the relevant parent bundle resource
    """

    resource_id: str
    bundle_id: str
    _code = codes.CANNOT_BAN_RESOURCE_BUNDLE_INNER

    @property
    def message(self) -> str:
        return (
            f"Resource '{self.resource_id}' is in a bundle and cannot be banned. "
            f"If you want to ban the bundle, use the bundle id ({self.bundle_id})"
        )


@dataclass(frozen=True)
class CannotBanResourceMasterResourceNotPromotable(ReportItemMessage):
    """
    User is trying to ban a non-promotable resource and limit it to master role

    resource_id -- id of the resource to be banned
    promotable_id -- id of relevant parent promotable resource
    """

    resource_id: str
    promotable_id: str = ""
    _code = codes.CANNOT_BAN_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE

    @property
    def message(self) -> str:
        return _resource_move_ban_clear_master_resource_not_promotable(
            self.promotable_id
        )


@dataclass(frozen=True)
class CannotBanResourceMultipleInstancesNoNodeSpecified(ReportItemMessage):
    """
    User is trying to ban a resource of which more than one instance is running
    without specifying a destination node

    resource_id -- id of the resource to be banned
    """

    resource_id: str
    _code = codes.CANNOT_BAN_RESOURCE_MULTIPLE_INSTANCES_NO_NODE_SPECIFIED

    @property
    def message(self) -> str:
        return (
            f"more than one instance of resource '{self.resource_id}' is "
            "running, thus the resource cannot be banned, "
            "unless a destination node is specified"
        )


@dataclass(frozen=True)
class CannotBanResourceStoppedNoNodeSpecified(ReportItemMessage):
    """
    When banning a stopped resource, a node to ban it on must be specified

    resource_id -- id of the resource to be banned
    """

    resource_id: str
    _code = codes.CANNOT_BAN_RESOURCE_STOPPED_NO_NODE_SPECIFIED

    @property
    def message(self) -> str:
        # Use both "moving" and "banning" to let user know using "move" instead
        # of "ban" will not help
        return "You must specify a node when moving/banning a stopped resource"


@dataclass(frozen=True)
class StoppingResourcesBeforeDeleting(ReportItemMessage):
    """
    Resources are going to be stopped before deletion

    resource_id_list -- ids of resources that are going to be stopped
    """

    resource_id_list: list[str]
    _code = codes.STOPPING_RESOURCES_BEFORE_DELETING

    @property
    def message(self) -> str:
        return "Stopping {resource} {resource_list} before deleting".format(
            resource=format_plural(self.resource_id_list, "resource"),
            resource_list=format_list(self.resource_id_list),
        )


@dataclass(frozen=True)
class StoppingResourcesBeforeDeletingSkipped(ReportItemMessage):
    """
    Resources are not going to be stopped before deletion.
    """

    _code = codes.STOPPING_RESOURCES_BEFORE_DELETING_SKIPPED

    @property
    def message(self) -> str:
        return (
            "Resources are not going to be stopped before deletion, this may "
            "result in orphaned resources being present in the cluster"
        )


@dataclass(frozen=True)
class CannotStopResourcesBeforeDeleting(ReportItemMessage):
    """
    Cannot stop resources that are being removed

    resource_id_list -- ids of resources that cannot be stopped
    """

    resource_id_list: list[str]
    _code = codes.CANNOT_STOP_RESOURCES_BEFORE_DELETING

    @property
    def message(self) -> str:
        return "Cannot stop {resource} {resource_list} before deleting".format(
            resource=format_plural(self.resource_id_list, "resource"),
            resource_list=format_list(self.resource_id_list),
        )


@dataclass(frozen=True)
class ResourceBanPcmkError(ReportItemMessage):
    """
    crm_resource exited with an error when banning a resource

    resource_id -- id of the resource to be banned
    stdout -- stdout of crm_resource
    stderr -- stderr of crm_resource
    """

    resource_id: str
    stdout: str
    stderr: str
    _code = codes.RESOURCE_BAN_PCMK_ERROR

    @property
    def message(self) -> str:
        # Pacemaker no longer prints crm_resource specific options since commit
        # 8008a5f0c0aa728fbce25f60069d622d0bcbbc9f. There is no need to
        # translate them or anything else anymore.
        return _stdout_stderr_to_string(
            self.stdout,
            self.stderr,
            prefix=f"cannot ban resource '{self.resource_id}'",
        )


@dataclass(frozen=True)
class ResourceBanPcmkSuccess(ReportItemMessage):
    """
    crm_resource exited successfully when banning a resource

    resource_id -- id of the resource to be banned
    stdout -- stdout of crm_resource
    stderr -- stderr of crm_resource
    """

    resource_id: str
    stdout: str
    stderr: str
    _code = codes.RESOURCE_BAN_PCMK_SUCCESS

    @property
    def message(self) -> str:
        return _resource_move_ban_pcmk_success(self.stdout, self.stderr)


@dataclass(frozen=True)
class CannotUnmoveUnbanResourceMasterResourceNotPromotable(ReportItemMessage):
    """
    User is trying to unmove/unban master of a non-promotable resource

    resource_id -- id of the resource to be unmoved/unbanned
    promotable_id -- id of relevant parent promotable resource
    """

    resource_id: str
    promotable_id: str = ""
    _code = codes.CANNOT_UNMOVE_UNBAN_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE

    @property
    def message(self) -> str:
        return _resource_move_ban_clear_master_resource_not_promotable(
            self.promotable_id
        )


@dataclass(frozen=True)
class ResourceUnmoveUnbanPcmkExpiredNotSupported(ReportItemMessage):
    """
    crm_resource does not support --expired when unmoving/unbanning a resource
    """

    _code = codes.RESOURCE_UNMOVE_UNBAN_PCMK_EXPIRED_NOT_SUPPORTED

    @property
    def message(self) -> str:
        return "expired is not supported, please upgrade pacemaker"


@dataclass(frozen=True)
class ResourceUnmoveUnbanPcmkError(ReportItemMessage):
    """
    crm_resource exited with an error when unmoving/unbanning a resource

    resource_id -- id of the resource to be unmoved/unbanned
    stdout -- stdout of crm_resource
    stderr -- stderr of crm_resource
    """

    resource_id: str
    stdout: str
    stderr: str
    _code = codes.RESOURCE_UNMOVE_UNBAN_PCMK_ERROR

    @property
    def message(self) -> str:
        return _stdout_stderr_to_string(
            self.stdout,
            self.stderr,
            prefix=f"cannot clear resource '{self.resource_id}'",
        )


@dataclass(frozen=True)
class ResourceUnmoveUnbanPcmkSuccess(ReportItemMessage):
    """
    crm_resource exited successfully when clearing unmoving/unbanning a resource

    resource_id -- id of the resource to be unmoved/unbanned
    stdout -- stdout of crm_resource
    stderr -- stderr of crm_resource
    """

    resource_id: str
    stdout: str
    stderr: str
    _code = codes.RESOURCE_UNMOVE_UNBAN_PCMK_SUCCESS

    @property
    def message(self) -> str:
        return _stdout_stderr_to_string(self.stdout, self.stderr)


@dataclass(frozen=True)
class ResourceMayOrMayNotMove(ReportItemMessage):
    """
    A move constraint has been created and the resource may or may not move
    depending on other configuration.

    resource_id -- id of the resource to be moved
    """

    resource_id: str
    _code = codes.RESOURCE_MAY_OR_MAY_NOT_MOVE

    @property
    def message(self) -> str:
        return (
            "A move constraint has been created and the resource "
            f"'{self.resource_id}' may or may not move depending on other "
            "configuration"
        )


@dataclass(frozen=True)
class ResourceMoveConstraintCreated(ReportItemMessage):
    """
    A constraint to move resource has been created.

    resource_id -- id of the resource to be moved
    """

    resource_id: str
    _code = codes.RESOURCE_MOVE_CONSTRAINT_CREATED

    @property
    def message(self) -> str:
        return (
            f"Location constraint to move resource '{self.resource_id}' has "
            "been created"
        )


@dataclass(frozen=True)
class ResourceMoveConstraintRemoved(ReportItemMessage):
    """
    A constraint to move resource has been removed.

    resource_id -- id of the resource to be moved
    """

    resource_id: str
    _code = codes.RESOURCE_MOVE_CONSTRAINT_REMOVED

    @property
    def message(self) -> str:
        return (
            f"Location constraint created to move resource "
            f"'{self.resource_id}' has been removed"
        )


@dataclass(frozen=True)
class ResourceMoveNotAffectingResource(ReportItemMessage):
    """
    Creating a location constraint to move a resource has no effect on the
    resource.

    resource_id -- id of the resource to be moved
    """

    resource_id: str
    _code = codes.RESOURCE_MOVE_NOT_AFFECTING_RESOURCE

    @property
    def message(self) -> str:
        return (
            f"Unable to move resource '{self.resource_id}' using a location "
            "constraint. Current location of the resource may be affected by "
            "some other constraint."
        )


@dataclass(frozen=True)
class ResourceMoveAffectsOtherResources(ReportItemMessage):
    """
    Moving a resource will also affect other resources.

    resource_id -- id of the resource to be moved
    affected_resources -- resources affected by the move operation
    """

    resource_id: str
    affected_resources: List[str]
    _code = codes.RESOURCE_MOVE_AFFECTS_OTRHER_RESOURCES

    @property
    def message(self) -> str:
        return (
            "Moving resource '{resource_id}' affects {resource_pl}: "
            "{affected_resources}"
        ).format(
            resource_id=self.resource_id,
            resource_pl=format_plural(self.affected_resources, "resource"),
            affected_resources=format_list(self.affected_resources),
        )


@dataclass(frozen=True)
class ResourceMoveAutocleanSimulationFailure(ReportItemMessage):
    """
    Autocleaning a constraint used for moving the resource would cause moving
    the resource itself or other resources.

    resource_id -- id of the resource to be moved
    others_affected -- True if also other resource would be affected, False
        otherwise
    node -- target node the resource should be moved to
    move_constraint_left_in_cib -- move has happened and the failure occurred
        when trying to remove the move constraint from the live cib
    """

    resource_id: str
    others_affected: bool
    node: Optional[str] = None
    move_constraint_left_in_cib: bool = False
    _code = codes.RESOURCE_MOVE_AUTOCLEAN_SIMULATION_FAILURE

    @property
    def message(self) -> str:
        template = (
            "Unable to ensure that moved resource '{resource_id}'{others} will "
            "stay on the same node after a constraint used for moving it is "
            "removed."
        )
        if self.move_constraint_left_in_cib:
            template += (
                " The constraint to move the resource has not been removed "
                "from configuration. Consider removing it manually. Be aware "
                "that removing the constraint may cause resources to move "
                "to other nodes."
            )
        return template.format(
            resource_id=self.resource_id,
            others=" or other resources" if self.others_affected else "",
        )


@dataclass(frozen=True)
class ParseErrorJsonFile(ReportItemMessage):
    """
    Unable to parse a file with JSON data

    file_type_code -- item from pcs.common.file_type_codes
    line_number -- the line where parsing failed
    column_number -- the column where parsing failed
    position -- the start index of the file where parsing failed
    reason -- the unformatted error message
    full_msg -- full error message including above int attributes
    file_path -- path to the parsed file if available
    """

    file_type_code: file_type_codes.FileTypeCode
    line_number: int
    column_number: int
    position: int
    reason: str
    full_msg: str
    file_path: Optional[str]
    _code = codes.PARSE_ERROR_JSON_FILE

    @property
    def message(self) -> str:
        return (
            "Unable to parse {_file_type} file{_file_path}: {full_msg}"
        ).format(
            _file_path=format_optional(self.file_path, " '{}'"),
            _file_type=_format_file_role(self.file_type_code),
            full_msg=self.full_msg,
        )


@dataclass(frozen=True)
class ResourceDisableAffectsOtherResources(ReportItemMessage):
    """
    User requested disabling resources without affecting other resources but
    some resources would be affected

    disabled_resource_list -- list of resources to disable
    affected_resource_list -- other affected resources
    """

    disabled_resource_list: List[str]
    affected_resource_list: List[str]
    _code = codes.RESOURCE_DISABLE_AFFECTS_OTHER_RESOURCES

    @property
    def message(self) -> str:
        return (
            "Disabling specified {disabled_resource_pl} would have an effect "
            "on {this_pl} {affected_resource_pl}: "
            "{affected_resource_list}".format(
                disabled_resource_pl=format_plural(
                    self.disabled_resource_list, "resource"
                ),
                this_pl=format_plural(
                    self.affected_resource_list, "this", "these"
                ),
                affected_resource_pl=format_plural(
                    self.affected_resource_list, "resource"
                ),
                affected_resource_list=format_list(self.affected_resource_list),
            )
        )


@dataclass(frozen=True)
class DrConfigAlreadyExist(ReportItemMessage):
    """
    Disaster recovery config exists when the opposite was expected
    """

    _code = codes.DR_CONFIG_ALREADY_EXIST

    @property
    def message(self) -> str:
        return "Disaster-recovery already configured"


@dataclass(frozen=True)
class DrConfigDoesNotExist(ReportItemMessage):
    """
    Disaster recovery config does not exist when the opposite was expected
    """

    _code = codes.DR_CONFIG_DOES_NOT_EXIST

    @property
    def message(self) -> str:
        return "Disaster-recovery is not configured"


@dataclass(frozen=True)
class NodeInLocalCluster(ReportItemMessage):
    """
    Node is part of local cluster and it cannot be used for example to set up
    disaster-recovery site

    node -- node which is part of local cluster
    """

    node: str
    _code = codes.NODE_IN_LOCAL_CLUSTER

    @property
    def message(self) -> str:
        return f"Node '{self.node}' is part of local cluster"


@dataclass(frozen=True)
class BoothPathNotExists(ReportItemMessage):
    """
    Path '/etc/booth' is generated when Booth is installed, so it can be used to
    check whether Booth is installed

    path -- The path generated by booth installation
    """

    path: str
    _code = codes.BOOTH_PATH_NOT_EXISTS

    @property
    def message(self) -> str:
        return (
            f"Configuration directory for booth '{self.path}' is missing. "
            "Is booth installed?"
        )


@dataclass(frozen=True)
class BoothLackOfSites(ReportItemMessage):
    """
    Less than 2 booth sites entered. But it does not make sense.

    sites -- contains currently entered sites
    """

    sites: List[str]
    _code = codes.BOOTH_LACK_OF_SITES

    @property
    def message(self) -> str:
        sites = format_list(self.sites) if self.sites else "missing"
        return (
            "lack of sites for booth configuration (need 2 at least): sites "
            f"{sites}"
        )


@dataclass(frozen=True)
class BoothEvenPeersNumber(ReportItemMessage):
    """
    Booth requires odd number of peers. But even number of peers was entered.

    number -- determines how many peers was entered
    """

    number: int
    _code = codes.BOOTH_EVEN_PEERS_NUM

    @property
    def message(self) -> str:
        return f"odd number of peers is required (entered {self.number} peers)"


@dataclass(frozen=True)
class BoothAddressDuplication(ReportItemMessage):
    """
    Address of each peer must be unique. But address duplication appeared.

    duplicate_addresses -- contains addresses entered multiple times
    """

    duplicate_addresses: List[str]
    _code = codes.BOOTH_ADDRESS_DUPLICATION

    @property
    def message(self) -> str:
        addresses = format_list(self.duplicate_addresses)
        return f"duplicate address for booth configuration: {addresses}"


@dataclass(frozen=True)
class BoothConfigUnexpectedLines(ReportItemMessage):
    """
    Lines not conforming to expected config structure found in a booth config

    line_list -- not valid lines
    file_path -- path to the conf file if available
    """

    line_list: List[str]
    file_path: str = ""
    _code = codes.BOOTH_CONFIG_UNEXPECTED_LINES

    @property
    def message(self) -> str:
        return "unexpected {line_pl} in booth config{path}:\n{lines}".format(
            line_pl=format_plural(self.line_list, "line"),
            path=format_optional(self.file_path, " '{}'"),
            lines="\n".join(self.line_list),
        )


@dataclass(frozen=True)
class BoothInvalidName(ReportItemMessage):
    """
    Booth instance name is not valid

    name -- entered booth instance name
    forbidden_characters -- characters the name cannot contain
    """

    name: str
    forbidden_characters: str
    _code = codes.BOOTH_INVALID_NAME

    @property
    def message(self) -> str:
        return (
            f"booth name '{self.name}' is not valid, it cannot contain "
            f"{self.forbidden_characters} characters"
        )


@dataclass(frozen=True)
class BoothTicketNameInvalid(ReportItemMessage):
    """
    Name of booth ticket may consists of alphanumeric characters or dash.
    Entered ticket name is violating this rule.

    ticket_name -- entered booth ticket name
    """

    ticket_name: str
    _code = codes.BOOTH_TICKET_NAME_INVALID

    @property
    def message(self) -> str:
        return (
            f"booth ticket name '{self.ticket_name}' is not valid, use "
            "up to 63 alphanumeric characters or dash"
        )


@dataclass(frozen=True)
class BoothTicketDuplicate(ReportItemMessage):
    """
    Each booth ticket name must be unique. But duplicate booth ticket name was
    entered.

    ticket_name -- entered booth ticket name
    """

    ticket_name: str
    _code = codes.BOOTH_TICKET_DUPLICATE

    @property
    def message(self) -> str:
        return (
            f"booth ticket name '{self.ticket_name}' already exists in "
            "configuration"
        )


@dataclass(frozen=True)
class BoothTicketDoesNotExist(ReportItemMessage):
    """
    Some operations (like ticket remove) expect the ticket name in booth
    configuration. But the ticket name was not found in booth configuration.

    ticket_name -- entered booth ticket name
    """

    ticket_name: str
    _code = codes.BOOTH_TICKET_DOES_NOT_EXIST

    @property
    def message(self) -> str:
        return f"booth ticket name '{self.ticket_name}' does not exist"


@dataclass(frozen=True)
class BoothAlreadyInCib(ReportItemMessage):
    """
    Each booth instance should be in a cib once maximally. Existence of booth
    instance in cib detected during creating new one.

    name -- booth instance name
    """

    name: str
    _code = codes.BOOTH_ALREADY_IN_CIB

    @property
    def message(self) -> str:
        return (
            f"booth instance '{self.name}' is already created as cluster "
            "resource"
        )


@dataclass(frozen=True)
class BoothNotExistsInCib(ReportItemMessage):
    """
    Remove booth instance from cib required. But no such instance found in cib.

    name -- booth instance name
    """

    name: str
    _code = codes.BOOTH_NOT_EXISTS_IN_CIB

    @property
    def message(self) -> str:
        return f"booth instance '{self.name}' not found in cib"


@dataclass(frozen=True)
class BoothConfigIsUsed(ReportItemMessage):
    """
    Booth config use detected during destroy request.

    name -- booth instance name
    detail -- provides more details (for example booth instance is used as
        cluster resource or is started/enabled under systemd)
    resource_name -- which resource uses the booth instance, only valid if
        detail == BOOTH_CONFIG_USED_IN_CLUSTER_RESOURCE
    """

    name: str
    detail: types.BoothConfigUsedWhere
    resource_name: Optional[str] = None
    _code = codes.BOOTH_CONFIG_IS_USED

    @property
    def message(self) -> str:
        detail_map = {
            const.BOOTH_CONFIG_USED_IN_CLUSTER_RESOURCE: "in a cluster resource",
            const.BOOTH_CONFIG_USED_ENABLED_IN_SYSTEMD: "- it is enabled in systemd",
            const.BOOTH_CONFIG_USED_RUNNING_IN_SYSTEMD: "- it is running by systemd",
        }
        detail = detail_map.get(self.detail, str(self.detail))
        if (
            self.detail == const.BOOTH_CONFIG_USED_IN_CLUSTER_RESOURCE
            and self.resource_name
        ):
            detail = f"in cluster resource '{self.resource_name}'"
        return f"booth instance '{self.name}' is used {detail}"


@dataclass(frozen=True)
class BoothMultipleTimesInCib(ReportItemMessage):
    """
    Each booth instance should be in a cib once maximally. But multiple
    occurrences detected. For example during remove booth instance from cib.
    Notify user about this fact is required. When operation is forced user
    should be notified about multiple occurrences.

    name -- booth instance name
    """

    name: str
    _code = codes.BOOTH_MULTIPLE_TIMES_IN_CIB

    @property
    def message(self) -> str:
        return f"found more than one booth instance '{self.name}' in cib"


@dataclass(frozen=True)
class BoothConfigDistributionStarted(ReportItemMessage):
    """
    Booth configuration is about to be sent to nodes
    """

    _code = codes.BOOTH_CONFIG_DISTRIBUTION_STARTED

    @property
    def message(self) -> str:
        return "Sending booth configuration to cluster nodes..."


@dataclass(frozen=True)
class BoothConfigAcceptedByNode(ReportItemMessage):
    """
    Booth config has been saved on specified node.

    node -- name of node
    name_list -- list of names of booth instance
    """

    node: str = ""
    name_list: List[str] = field(default_factory=list)
    _code = codes.BOOTH_CONFIG_ACCEPTED_BY_NODE

    @property
    def message(self) -> str:
        desc = ""
        if self.name_list and self.name_list not in [["booth"]]:
            desc = "{_s} {_list}".format(
                _s="s" if len(self.name_list) > 1 else "",
                _list=format_list(self.name_list),
            )
        return "{node}Booth config{desc} saved".format(
            node=format_optional(self.node, "{}: "),
            desc=desc,
        )


@dataclass(frozen=True)
class BoothConfigDistributionNodeError(ReportItemMessage):
    """
    Saving booth config failed on specified node.

    node -- node name
    reason -- reason of failure
    name -- name of booth instance
    """

    node: str
    reason: str
    name: str = ""
    _code = codes.BOOTH_CONFIG_DISTRIBUTION_NODE_ERROR

    @property
    def message(self) -> str:
        desc = _format_booth_default(self.name, " '{}'")
        return (
            f"Unable to save booth config{desc} on node '{self.node}': "
            f"{self.reason}"
        )


@dataclass(frozen=True)
class BoothFetchingConfigFromNode(ReportItemMessage):
    """
    Fetching of booth config from specified node started.

    node -- node from which config is fetching
    config -- config name
    """

    node: str
    config: str = ""
    _code = codes.BOOTH_FETCHING_CONFIG_FROM_NODE

    @property
    def message(self) -> str:
        desc = _format_booth_default(self.config, " '{}'")
        return f"Fetching booth config{desc} from node '{self.node}'..."


@dataclass(frozen=True)
class BoothUnsupportedFileLocation(ReportItemMessage):
    """
    A booth file (config, authfile) is not in the expected dir, skipping it.

    file_path -- the actual path of the file
    expected_dir -- where the file is supposed to be
    file_type_code -- item from pcs.common.file_type_codes
    """

    file_path: str
    expected_dir: str
    file_type_code: file_type_codes.FileTypeCode
    _code = codes.BOOTH_UNSUPPORTED_FILE_LOCATION

    @property
    def message(self) -> str:
        file_role = _format_file_role(self.file_type_code)
        return (
            f"{file_role} '{self.file_path}' is outside of supported booth "
            f"config directory '{self.expected_dir}', ignoring the file"
        )


@dataclass(frozen=True)
class BoothDaemonStatusError(ReportItemMessage):
    """
    Unable to get status of booth daemon because of error.

    reason -- reason
    """

    reason: str
    _code = codes.BOOTH_DAEMON_STATUS_ERROR

    @property
    def message(self) -> str:
        return f"unable to get status of booth daemon: {self.reason}"


@dataclass(frozen=True)
class BoothTicketStatusError(ReportItemMessage):
    """
    Unable to get status of booth tickets because of error.

    reason -- reason
    """

    reason: str = ""
    _code = codes.BOOTH_TICKET_STATUS_ERROR

    @property
    def message(self) -> str:
        reason = format_optional(self.reason, ": {}")
        return f"unable to get status of booth tickets{reason}"


@dataclass(frozen=True)
class BoothPeersStatusError(ReportItemMessage):
    """
    Unable to get status of booth peers because of error.

    reason -- reason
    """

    reason: str = ""
    _code = codes.BOOTH_PEERS_STATUS_ERROR

    @property
    def message(self) -> str:
        reason = format_optional(self.reason, ": {}")
        return f"unable to get status of booth peers{reason}"


@dataclass(frozen=True)
class BoothCannotDetermineLocalSiteIp(ReportItemMessage):
    """
    Some booth operations are performed on specific site and requires to
    specify site ip. When site specification omitted pcs can try determine
    local ip. But determine local site ip failed.
    """

    _code = codes.BOOTH_CANNOT_DETERMINE_LOCAL_SITE_IP

    @property
    def message(self) -> str:
        return "cannot determine local site ip, please specify site parameter"


@dataclass(frozen=True)
class BoothTicketOperationFailed(ReportItemMessage):
    """
    Pcs uses external booth tools for some ticket_name operations. For example
    grand and revoke. But the external command failed.

    operation  -- determine what was intended perform with ticket_name
    reason -- error description from external booth command
    site_ip -- specify what site had to run the command
    ticket_name -- specify with which ticket had to run the command
    """

    operation: str
    reason: str
    site_ip: str
    ticket_name: str
    _code = codes.BOOTH_TICKET_OPERATION_FAILED

    @property
    def message(self) -> str:
        return (
            f"unable to {self.operation} booth ticket '{self.ticket_name}'"
            f" for site '{self.site_ip}', reason: {self.reason}"
        )


# TODO: remove, use ADD_REMOVE reports
@dataclass(frozen=True)
class TagAddRemoveIdsDuplication(ReportItemMessage):
    """
    Duplicate reference ids were found in tag create or update add/remove
    specification.
    """

    duplicate_ids_list: List[str]
    add_or_not_remove: bool = True
    _code = codes.TAG_ADD_REMOVE_IDS_DUPLICATION

    @property
    def message(self) -> str:
        action = "add" if self.add_or_not_remove else "remove"
        duplicate_ids = format_list(self.duplicate_ids_list)
        return f"Ids to {action} must be unique, duplicate ids: {duplicate_ids}"


# TODO: remove, use ADD_REMOVE reports
@dataclass(frozen=True)
class TagAdjacentReferenceIdNotInTheTag(ReportItemMessage):
    """
    Cannot put reference ids next to an adjacent reference id in a tag, because
    the adjacent reference id does not belong to the tag.

    adjacent_id -- adjacent reference id
    tag_id -- tag id
    """

    adjacent_id: str
    tag_id: str
    _code = codes.TAG_ADJACENT_REFERENCE_ID_NOT_IN_THE_TAG

    @property
    def message(self) -> str:
        return (
            f"There is no reference id '{self.adjacent_id}' in the tag "
            f"'{self.tag_id}', cannot put reference ids next to it in the tag"
        )


# TODO: remove, use ADD_REMOVE reports
@dataclass(frozen=True)
class TagCannotAddAndRemoveIdsAtTheSameTime(ReportItemMessage):
    """
    Cannot add and remove ids at the same time. Avoid operation without an
    effect.

    idref_list -- common ids from add and remove lists
    """

    idref_list: List[str]
    _code = codes.TAG_CANNOT_ADD_AND_REMOVE_IDS_AT_THE_SAME_TIME

    @property
    def message(self) -> str:
        idref_list = format_list(self.idref_list)
        return f"Ids cannot be added and removed at the same time: {idref_list}"


# TODO: remove, use ADD_REMOVE reports
@dataclass(frozen=True)
class TagCannotAddReferenceIdsAlreadyInTheTag(ReportItemMessage):
    """
    Cannot add reference ids already in the tag.

    tag_id -- tag id
    idref_list -- reference ids already in tag
    """

    tag_id: str
    idref_list: List[str]
    _code = codes.TAG_CANNOT_ADD_REFERENCE_IDS_ALREADY_IN_THE_TAG

    @property
    def message(self) -> str:
        return (
            "Cannot add reference {ids} already in the tag '{tag_id}': "
            "{idref_list}"
        ).format(
            ids=format_plural(self.idref_list, "id"),
            tag_id=self.tag_id,
            idref_list=format_list(self.idref_list),
        )


@dataclass(frozen=True)
class TagCannotContainItself(ReportItemMessage):
    """
    List of object reference ids contains the same id as specified tag_id.
    """

    _code = codes.TAG_CANNOT_CONTAIN_ITSELF

    @property
    def message(self) -> str:
        return "Tag cannot contain itself"


@dataclass(frozen=True)
class TagCannotCreateEmptyTagNoIdsSpecified(ReportItemMessage):
    """
    Cannot create empty tag, no reference ids were specified.
    """

    _code = codes.TAG_CANNOT_CREATE_EMPTY_TAG_NO_IDS_SPECIFIED

    @property
    def message(self) -> str:
        return "Cannot create empty tag, no resource ids specified"


# TODO: remove, use ADD_REMOVE reports
@dataclass(frozen=True)
class TagCannotPutIdNextToItself(ReportItemMessage):
    """
    Cannot put id next to itself. Wrong adjacent id.

    adjacent_id -- adjacent reference id
    """

    adjacent_id: str
    _code = codes.TAG_CANNOT_PUT_ID_NEXT_TO_ITSELF

    @property
    def message(self) -> str:
        return f"Cannot put id '{self.adjacent_id}' next to itself."


# TODO: remove, use ADD_REMOVE reports
@dataclass(frozen=True)
class TagCannotRemoveAdjacentId(ReportItemMessage):
    """
    Cannot remove adjacent id.

    adjacent_id -- adjacent reference id
    """

    adjacent_id: str
    _code = codes.TAG_CANNOT_REMOVE_ADJACENT_ID

    @property
    def message(self) -> str:
        return (
            f"Cannot remove id '{self.adjacent_id}' next to which ids are being"
            " added"
        )


# TODO: remove, use ADD_REMOVE reports
@dataclass(frozen=True)
class TagCannotRemoveReferencesWithoutRemovingTag(ReportItemMessage):
    """
    Cannot remove references without removing a tag.
    """

    tag_id: str
    _code = codes.TAG_CANNOT_REMOVE_REFERENCES_WITHOUT_REMOVING_TAG

    @property
    def message(self) -> str:
        return f"There would be no references left in the tag '{self.tag_id}'"


@dataclass(frozen=True)
class TagCannotRemoveTagReferencedInConstraints(ReportItemMessage):
    """
    Cannot remove tag which is referenced in constraints.

    tag_id -- tag id
    constraint_id_list -- list of constraint ids which are referencing tag
    """

    tag_id: str
    constraint_id_list: List[str]
    _code = codes.TAG_CANNOT_REMOVE_TAG_REFERENCED_IN_CONSTRAINTS

    @property
    def message(self) -> str:
        return (
            "Tag '{tag_id}' cannot be removed because it is referenced in "
            "{constraints} {constraint_id_list}"
        ).format(
            tag_id=self.tag_id,
            constraints=format_plural(self.constraint_id_list, "constraint"),
            constraint_id_list=format_list(self.constraint_id_list),
        )


@dataclass(frozen=True)
class TagCannotRemoveTagsNoTagsSpecified(ReportItemMessage):
    """
    Cannot remove tags, no tags were specified.
    """

    _code = codes.TAG_CANNOT_REMOVE_TAGS_NO_TAGS_SPECIFIED

    @property
    def message(self) -> str:
        return "Cannot remove tags, no tags to remove specified"


# TODO: remove, use ADD_REMOVE reports
@dataclass(frozen=True)
class TagCannotSpecifyAdjacentIdWithoutIdsToAdd(ReportItemMessage):
    """
    Cannot specify adjacent id without ids to add.

    adjacent_id -- adjacent reference id
    """

    adjacent_id: str
    _code = codes.TAG_CANNOT_SPECIFY_ADJACENT_ID_WITHOUT_IDS_TO_ADD

    @property
    def message(self) -> str:
        return (
            f"Cannot specify adjacent id '{self.adjacent_id}' without ids to "
            "add"
        )


# TODO: remove, use ADD_REMOVE reports
@dataclass(frozen=True)
class TagCannotUpdateTagNoIdsSpecified(ReportItemMessage):
    """
    Cannot update tag, no ids specified.
    """

    _code = codes.TAG_CANNOT_UPDATE_TAG_NO_IDS_SPECIFIED

    @property
    def message(self) -> str:
        return "Cannot update tag, no ids to be added or removed specified"


# TODO: remove, use ADD_REMOVE reports
@dataclass(frozen=True)
class TagIdsNotInTheTag(ReportItemMessage):
    """
    Specified ids are not present in the specified tag.
    """

    tag_id: str
    id_list: List[str]
    _code = codes.TAG_IDS_NOT_IN_THE_TAG

    @property
    def message(self) -> str:
        return "Tag '{tag_id}' does not contain {ids}: {id_list}".format(
            tag_id=self.tag_id,
            ids=format_plural(self.id_list, "id"),
            id_list=format_list(self.id_list),
        )


@dataclass(frozen=True)
class RuleInEffectStatusDetectionNotSupported(ReportItemMessage):
    """
    Pacemaker tool for detecting if a rule is expired or not is not available
    """

    _code = codes.RULE_IN_EFFECT_STATUS_DETECTION_NOT_SUPPORTED

    @property
    def message(self) -> str:
        return (
            "crm_rule is not available, therefore expired parts of "
            "configuration may not be detected. Consider upgrading pacemaker."
        )


@dataclass(frozen=True)
class RuleExpressionOptionsDuplication(ReportItemMessage):
    """
    Keys are specified more than once in a single rule (sub)expression

    duplicate_option_list -- list of keys duplicated in a single (sub)expression
    """

    duplicate_option_list: List[str]
    _code = codes.RULE_EXPRESSION_OPTIONS_DUPLICATION

    @property
    def message(self) -> str:
        options = format_list(self.duplicate_option_list)
        return f"Duplicate options in a single (sub)expression: {options}"


@dataclass(frozen=True)
class RuleExpressionParseError(ReportItemMessage):
    """
    Unable to parse pacemaker cib rule expression string

    rule_string -- the whole rule expression string
    reason -- error message from rule parser
    rule_line -- part of rule_string - the line where the error occurred
    line_number -- the line where parsing failed
    column_number -- the column where parsing failed
    position -- the start index where parsing failed
    """

    rule_string: str
    reason: str
    rule_line: str
    line_number: int
    column_number: int
    position: int
    _code = codes.RULE_EXPRESSION_PARSE_ERROR

    @property
    def message(self) -> str:
        # Messages coming from the parser are not very useful and readable,
        # they mostly contain one line grammar expression covering the whole
        # rule. No user would be able to parse that. Therefore we omit the
        # messages.
        return (
            f"'{self.rule_string}' is not a valid rule expression, parse error "
            f"near or after line {self.line_number} column {self.column_number}"
        )


@dataclass(frozen=True)
class RuleExpressionNotAllowed(ReportItemMessage):
    """
    Used rule expression is not allowed in current context

    expression_type -- disallowed expression type
    """

    expression_type: CibRuleExpressionType
    _code = codes.RULE_EXPRESSION_NOT_ALLOWED

    @property
    def message(self) -> str:
        type_map = {
            CibRuleExpressionType.EXPRESSION: (
                "Keywords 'defined', 'not_defined', 'eq', 'ne', 'gte', 'gt', "
                "'lte' and 'lt'"
            ),
            CibRuleExpressionType.OP_EXPRESSION: "Keyword 'op'",
            CibRuleExpressionType.RSC_EXPRESSION: "Keyword 'resource'",
        }
        return (
            f"{type_map[self.expression_type]} cannot be used "
            "in a rule in this command"
        )


@dataclass(frozen=True)
class RuleExpressionSinceGreaterThanUntil(ReportItemMessage):
    """
    In a date expression, 'until' predates 'since'
    """

    since: str
    until: str
    _code = codes.RULE_EXPRESSION_SINCE_GREATER_THAN_UNTIL

    @property
    def message(self) -> str:
        return f"Since '{self.since}' is not sooner than until '{self.until}'"


@dataclass(frozen=True)
class RuleNoExpressionSpecified(ReportItemMessage):
    """
    No rule was specified / empty rule was specified when a rule is required
    """

    _code = codes.RULE_NO_EXPRESSION_SPECIFIED

    @property
    def message(self) -> str:
        return "No rule expression was specified"


@dataclass(frozen=True)
class CibNvsetAmbiguousProvideNvsetId(ReportItemMessage):
    """
    An old command supporting only one nvset have been used when several nvsets
    exist. We require an nvset ID the command should work with to be specified.
    """

    pcs_command: types.PcsCommand
    _code = codes.CIB_NVSET_AMBIGUOUS_PROVIDE_NVSET_ID

    @property
    def message(self) -> str:
        return "Several options sets exist, please specify an option set ID"


@dataclass(frozen=True)
class AddRemoveItemsNotSpecified(ReportItemMessage):
    """
    Cannot modify container, no add or remove items specified.

    container_type -- type of item container
    item_type -- type of item in a container
    container_id -- id of a container
    """

    container_type: types.AddRemoveContainerType
    item_type: types.AddRemoveItemType
    container_id: str
    _code = codes.ADD_REMOVE_ITEMS_NOT_SPECIFIED

    @property
    def message(self) -> str:
        container = _add_remove_container_str(self.container_type)
        items = get_plural(_add_remove_item_str(self.item_type))
        return (
            f"Cannot modify {container} '{self.container_id}', no {items} to "
            "add or remove specified"
        )


@dataclass(frozen=True)
class AddRemoveItemsDuplication(ReportItemMessage):
    """
    Duplicate items were found in add/remove item lists.

    container_type -- type of item container
    item_type -- type of item in a container
    container_id -- id of a container
    duplicate_items_list -- list of duplicate items
    """

    container_type: types.AddRemoveContainerType
    item_type: types.AddRemoveItemType
    container_id: str
    duplicate_items_list: List[str]
    _code = codes.ADD_REMOVE_ITEMS_DUPLICATION

    @property
    def message(self) -> str:
        items = get_plural(_add_remove_item_str(self.item_type))
        duplicate_items = format_list(self.duplicate_items_list)
        return (
            f"{items.capitalize()} to add or remove must be unique, duplicate "
            f"{items}: {duplicate_items}"
        )


@dataclass(frozen=True)
class AddRemoveCannotAddItemsAlreadyInTheContainer(ReportItemMessage):
    """
    Cannot add items already existing in the container.

    container_type -- type of item container
    item_type -- type of item in a container
    container_id -- id of a container
    item_list -- list of items already in the container
    """

    container_type: types.AddRemoveContainerType
    item_type: types.AddRemoveItemType
    container_id: str
    item_list: List[str]
    _code = codes.ADD_REMOVE_CANNOT_ADD_ITEMS_ALREADY_IN_THE_CONTAINER

    @property
    def message(self) -> str:
        items = format_plural(
            self.item_list, _add_remove_item_str(self.item_type)
        )
        item_list = format_list(self.item_list)
        they = format_plural(self.item_list, "it")
        are = format_plural(self.item_list, "is")
        container = _add_remove_container_str(self.container_type)
        return (
            f"Cannot add {items} {item_list}, {they} {are} already present in "
            f"{container} '{self.container_id}'"
        )


@dataclass(frozen=True)
class AddRemoveCannotRemoveItemsNotInTheContainer(ReportItemMessage):
    """
    Cannot remove items not existing in the container.

    container_type -- type of item container
    item_type -- type of item in a container
    container_id -- id of a container
    item_list -- list of items not in the container
    """

    container_type: types.AddRemoveContainerType
    item_type: types.AddRemoveItemType
    container_id: str
    item_list: List[str]
    _code = codes.ADD_REMOVE_CANNOT_REMOVE_ITEMS_NOT_IN_THE_CONTAINER

    @property
    def message(self) -> str:
        items = format_plural(
            self.item_list, _add_remove_item_str(self.item_type)
        )
        item_list = format_list(self.item_list)
        they = format_plural(self.item_list, "it")
        are = format_plural(self.item_list, "is")
        container = _add_remove_container_str(self.container_type)
        items = format_plural(
            self.item_list, _add_remove_item_str(self.item_type)
        )
        return (
            f"Cannot remove {items} {item_list}, {they} {are} not present in "
            f"{container} '{self.container_id}'"
        )


@dataclass(frozen=True)
class AddRemoveCannotAddAndRemoveItemsAtTheSameTime(ReportItemMessage):
    """
    Cannot add and remove items at the same time. Avoid operation without an
    effect.

    container_type -- type of item container
    item_type -- type of item in a container
    container_id -- id of a container
    item_list -- common items from add and remove item lists
    """

    container_type: types.AddRemoveContainerType
    item_type: types.AddRemoveItemType
    container_id: str
    item_list: List[str]
    _code = codes.ADD_REMOVE_CANNOT_ADD_AND_REMOVE_ITEMS_AT_THE_SAME_TIME

    @property
    def message(self) -> str:
        items = format_plural(
            self.item_list, _add_remove_item_str(self.item_type)
        )
        item_list = format_list(self.item_list)
        return (
            f"{items.capitalize()} cannot be added and removed at the same "
            f"time: {item_list}"
        )


@dataclass(frozen=True)
class AddRemoveCannotRemoveAllItemsFromTheContainer(ReportItemMessage):
    """
    Cannot remove all items from a container.

    container_type -- type of item container
    item_type -- type of item in a container
    container_id -- id of a container
    item_list -- common items from add and remove item lists
    """

    container_type: types.AddRemoveContainerType
    item_type: types.AddRemoveItemType
    container_id: str
    item_list: List[str]
    _code = codes.ADD_REMOVE_CANNOT_REMOVE_ALL_ITEMS_FROM_THE_CONTAINER

    @property
    def message(self) -> str:
        container = _add_remove_container_str(self.container_type)
        items = get_plural(_add_remove_item_str(self.item_type))
        return (
            f"Cannot remove all {items} from {container} '{self.container_id}'"
        )


@dataclass(frozen=True)
class AddRemoveAdjacentItemNotInTheContainer(ReportItemMessage):
    """
    Cannot put items next to an adjacent item in the container, because the
    adjacent item does not exist in the container.

    container_type -- type of item container
    item_type -- type of item in a container
    container_id -- id of a container
    adjacent_item_id -- id of an adjacent item
    """

    container_type: types.AddRemoveContainerType
    item_type: types.AddRemoveItemType
    container_id: str
    adjacent_item_id: str
    _code = codes.ADD_REMOVE_ADJACENT_ITEM_NOT_IN_THE_CONTAINER

    @property
    def message(self) -> str:
        container = _add_remove_container_str(self.container_type)
        item = _add_remove_item_str(self.item_type)
        items = get_plural(item)
        return (
            f"There is no {item} '{self.adjacent_item_id}' in the "
            f"{container} '{self.container_id}', cannot add {items} next to it"
        )


@dataclass(frozen=True)
class AddRemoveCannotPutItemNextToItself(ReportItemMessage):
    """
    Cannot put an item into a container next to itself.

    container_type -- type of item container
    item_type -- type of item in a container
    container_id -- id of a container
    adjacent_item_id -- id of an adjacent item
    """

    container_type: types.AddRemoveContainerType
    item_type: types.AddRemoveItemType
    container_id: str
    adjacent_item_id: str
    _code = codes.ADD_REMOVE_CANNOT_PUT_ITEM_NEXT_TO_ITSELF

    @property
    def message(self) -> str:
        item = _add_remove_item_str(self.item_type)
        return f"Cannot put {item} '{self.adjacent_item_id}' next to itself"


@dataclass(frozen=True)
class AddRemoveCannotSpecifyAdjacentItemWithoutItemsToAdd(ReportItemMessage):
    """
    Cannot specify adjacent item without items to add.

    container_type -- type of item container
    item_type -- type of item in a container
    container_id -- id of a container
    adjacent_item_id -- id of an adjacent item
    """

    container_type: types.AddRemoveContainerType
    item_type: types.AddRemoveItemType
    container_id: str
    adjacent_item_id: str
    _code = codes.ADD_REMOVE_CANNOT_SPECIFY_ADJACENT_ITEM_WITHOUT_ITEMS_TO_ADD

    @property
    def message(self) -> str:
        item = _add_remove_item_str(self.item_type)
        items = get_plural(item)
        return (
            f"Cannot specify adjacent {item} '{self.adjacent_item_id}' without "
            f"{items} to add"
        )


@dataclass(frozen=True)
class ResourceWaitDeprecated(ReportItemMessage):
    """
    Deprecated wait parameter was used in command.
    """

    _code = codes.RESOURCE_WAIT_DEPRECATED

    @property
    def message(self) -> str:
        return (
            "Ability of this command to accept 'wait' argument is "
            "deprecated and will be removed in a future release."
        )


@dataclass(frozen=True)
class CommandInvalidPayload(ReportItemMessage):
    reason: str
    _code = codes.COMMAND_INVALID_PAYLOAD

    @property
    def message(self) -> str:
        return f"Invalid command payload: {self.reason}"


@dataclass(frozen=True)
class CommandUnknown(ReportItemMessage):
    command: str
    _code = codes.COMMAND_UNKNOWN

    @property
    def message(self) -> str:
        return f"Unknown command '{self.command}'"


@dataclass(frozen=True)
class NotAuthorized(ReportItemMessage):
    _code = codes.NOT_AUTHORIZED

    @property
    def message(self) -> str:
        return "Current user is not authorized for this operation"


@dataclass(frozen=True)
class AgentSelfValidationResult(ReportItemMessage):
    """
    Result of running of resource options by agent itself

    result -- output of agent
    """

    result: str
    _code = codes.AGENT_SELF_VALIDATION_RESULT

    @property
    def message(self) -> str:
        return "Validation result from agent:\n{result}".format(
            result="\n".join(indent(self.result.splitlines()))
        )


@dataclass(frozen=True)
class AgentSelfValidationInvalidData(ReportItemMessage):
    """
    Agent self validation produced an invalid data

    reason -- text description of the issue
    """

    reason: str
    _code = codes.AGENT_SELF_VALIDATION_INVALID_DATA

    @property
    def message(self) -> str:
        return f"Invalid validation data from agent: {self.reason}"


@dataclass(frozen=True)
class AgentSelfValidationSkippedUpdatedResourceMisconfigured(ReportItemMessage):
    """
    Agent self validation is skipped when updating a resource as it is
    misconfigured in its current state.
    """

    result: str
    _code = codes.AGENT_SELF_VALIDATION_SKIPPED_UPDATED_RESOURCE_MISCONFIGURED

    @property
    def message(self) -> str:
        return (
            "The resource was misconfigured before the update, therefore agent "
            "self-validation will not be run for the updated configuration. "
            "Validation output of the original configuration:\n{result}"
        ).format(result="\n".join(indent(self.result.splitlines())))


class AgentSelfValidationAutoOnWithWarnings(ReportItemMessage):
    """
    Agent self validation is enabled for all applicable commands and it produces
    warnings. In a future version, this may be switched to errors.
    """

    _code = codes.AGENT_SELF_VALIDATION_AUTO_ON_WITH_WARNINGS

    @property
    def message(self) -> str:
        return (
            "Validating resource options using the resource agent itself is "
            "enabled by default and produces warnings. In a future version, "
            "this might be changed to errors. Enable agent validation to "
            "switch to the future behavior."
        )


@dataclass(frozen=True)
class ResourceCloneIncompatibleMetaAttributes(ReportItemMessage):
    """
    Some clone specific meta attributes are not compatible with some resource
    agents

    attribute -- incompatible attribute name
    resource_agent -- agent which doesn't support specified attribute
    resource_id -- id of primitive resource to which this apply
    group_id -- id of resource group in which resource_id is placed
    """

    attribute: str
    resource_agent: ResourceAgentNameDto
    resource_id: Optional[str] = None
    group_id: Optional[str] = None
    _code = codes.RESOURCE_CLONE_INCOMPATIBLE_META_ATTRIBUTES

    @property
    def message(self) -> str:
        resource_desc = ""
        if self.resource_id:
            resource_desc = f" of resource '{self.resource_id}'"
            if self.group_id:
                resource_desc += f" in group '{self.group_id}'"
        return (
            f"Clone option '{self.attribute}' is not compatible with "
            f"'{get_resource_agent_full_name(self.resource_agent)}' resource "
            f"agent{resource_desc}"
        )


@dataclass(frozen=True)
class BoothAuthfileNotUsed(ReportItemMessage):
    """
    Booth autfile configured but has no effect, another option should be
    enabled as well.
    """

    instance: Optional[str]
    _code = codes.BOOTH_AUTHFILE_NOT_USED

    @property
    def message(self) -> str:
        return "Booth authfile is not enabled"


@dataclass(frozen=True)
class BoothUnsupportedOptionEnableAuthfile(ReportItemMessage):
    """
    Booth enable-autfile option is present in the booth configuration but is
    not accepted by booth, which will cause booth to fail at startup.
    """

    instance: Optional[str]
    _code = codes.BOOTH_UNSUPPORTED_OPTION_ENABLE_AUTHFILE

    @property
    def message(self) -> str:
        return (
            "Unsupported option 'enable-authfile' is set in booth configuration"
        )


@dataclass(frozen=True)
class CannotCreateDefaultClusterPropertySet(ReportItemMessage):
    """
    Cannot create default cluster properties nvset

    nvset_id -- id of the nvset
    """

    nvset_id: str
    _code = codes.CANNOT_CREATE_DEFAULT_CLUSTER_PROPERTY_SET

    @property
    def message(self) -> str:
        return (
            "Cannot create default cluster_property_set element, ID "
            f"'{self.nvset_id}' already exists. Find elements with the ID and "
            "remove them from cluster configuration."
        )


@dataclass(frozen=True)
class CommandArgumentTypeMismatch(ReportItemMessage):
    """
    Command does not accept specific type of an argument.

    not_accepted_type -- description of an entity not being accepted
    command_to_use_instead -- identifier of a command to use instead
    """

    not_accepted_type: str
    command_to_use_instead: Optional[types.PcsCommand] = None
    _code = codes.COMMAND_ARGUMENT_TYPE_MISMATCH

    @property
    def message(self) -> str:
        return f"This command does not accept {self.not_accepted_type}."


@dataclass(frozen=True)
class ClusterOptionsMetadataNotSupported(ReportItemMessage):
    """
    Pacemaker crm_attribute does not support new cluster options metadata.
    """

    _code = codes.CLUSTER_OPTIONS_METADATA_NOT_SUPPORTED

    @property
    def message(self) -> str:
        return (
            "Cluster options metadata are not supported, please upgrade "
            "pacemaker"
        )
