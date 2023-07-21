"""
Module contains validator classes and predicate functions useful for validation.
Example of use (how things play together):
    >>> option_dict = {"some_option": "A"}
    >>> validators = [
    ...     IsRequiredAll(["name"]),
    ...     ValueIn("some_option", ["B", "C"]),
    ... ]
    >>> report_list = ValidatorAll(validators).validate(option_dict)
    >>> for report in report_list:
    ...     print(report)
    ...
    ...
    ERROR REQUIRED_OPTION_IS_MISSING: {
        'option_type': 'option',
        'option_names': ['name']
    }
    ERROR INVALID_OPTION_VALUE: {
        'option_name': 'some_option',
        'option_value': 'A',
        'allowed_values': ['B', 'C']
    }

ValuePair class and values_to_pairs and pairs_to_values helpers are usefull in
cases when we walidate a normalized value. If the normalized value is not
valid, we want to put the original value into resulting reports. This is to
prevent confusion which may happen if the normalized value different from the
entered one is reported as not valid.
"""
import ipaddress
import re
from collections import Counter
from typing import (
    Any,
    Callable,
    Container,
    Dict,
    Iterable,
    Mapping,
    NamedTuple,
    Optional,
    Pattern,
    Set,
    Union,
    cast,
)

from pcs.common import reports
from pcs.common.reports import (
    ReportItem,
    ReportItemList,
    ReportItemSeverity,
)
from pcs.common.str_tools import format_list
from pcs.common.tools import timeout_to_seconds
from pcs.common.types import (
    StringCollection,
    StringIterable,
)
from pcs.common.validate import (
    is_integer,
    is_port_number,
)
from pcs.lib.cib.tools import IdProvider
from pcs.lib.corosync import constants as corosync_constants
from pcs.lib.external import CommandRunner
from pcs.lib.pacemaker.values import (
    BOOLEAN_VALUES,
    SCORE_INFINITY,
    is_boolean,
    is_duration,
    is_score,
    validate_id,
)

_FLOAT_RE = re.compile(r"^[-+]?(\d+|(\d*\.\d+)|(\d+\.\d*))([eE][+-]?\d+)?$")
_PCMK_DATESPEC_PART_RE = re.compile(r"^(?P<since>[0-9]+)(-(?P<until>[0-9]+))?$")

TypeOptionName = str
TypeOptionValue = str
TypeOptionRawMap = Dict[TypeOptionName, TypeOptionValue]
TypeNormalizeFunc = Callable[[TypeOptionName, TypeOptionValue], TypeOptionValue]

### normalization


class ValuePair(NamedTuple):
    """
    Storage for the original value and its normalized form
    """

    original: TypeOptionValue
    normalized: TypeOptionValue

    @staticmethod
    def get(val: Union["ValuePair", TypeOptionValue]) -> "ValuePair":
        return val if isinstance(val, ValuePair) else ValuePair(val, val)


TypeOptionNormalizedMap = Mapping[TypeOptionName, ValuePair]
TypeOptionMap = Mapping[TypeOptionName, Union[TypeOptionValue, ValuePair]]


def values_to_pairs(
    option_dict: TypeOptionMap, normalize: TypeNormalizeFunc
) -> TypeOptionNormalizedMap:
    """
    Return a dict derived from option_dict where every value is instance of
    ValuePair.

    option_dict -- values that should be paired with the normalized form
    normalize -- Takes key and value and returns normalized form. Function
        option_value_normalization can be good base for create such callable.
    """
    option_dict_with_pairs = {}
    for key, value in option_dict.items():
        if not isinstance(value, ValuePair):
            value = ValuePair(original=value, normalized=normalize(key, value))
        option_dict_with_pairs[key] = value
    return option_dict_with_pairs


def pairs_to_values(
    option_dict: Mapping[TypeOptionName, Union[TypeOptionValue, ValuePair]]
) -> TypeOptionRawMap:
    """
    Take a dict which has OptionValuePairs as its values and return dict with
    normalized forms as its values. It is reverse function to
    values_to_pairs.

    option_dict -- contains OptionValuePairs as its values
    """
    raw_option_dict = {}
    for key, value in option_dict.items():
        if isinstance(value, ValuePair):
            value = value.normalized
        raw_option_dict[key] = str(value)
    return raw_option_dict


def option_value_normalization(
    normalization_map: Mapping[
        TypeOptionName, Callable[[TypeOptionValue], TypeOptionValue]
    ]
) -> TypeNormalizeFunc:
    """
    Return function that takes key and value and return the normalized form.

    normalization_map -- has on each key function that takes value and return
        its normalized form.
    """

    def normalize(
        key: TypeOptionName, value: TypeOptionValue
    ) -> TypeOptionValue:
        return (
            value
            if key not in normalization_map
            else normalization_map[key](value)
        )

    return normalize


### generic validators


class ValidatorInterface:
    """
    Base interface of all validators
    """

    def validate(self, option_dict: TypeOptionMap) -> ReportItemList:
        raise NotImplementedError()


class CompoundValidator(ValidatorInterface):
    """
    Base abstract class for compound validators
    """

    def __init__(self, validator_list: Iterable[ValidatorInterface]):
        self._validator_list = validator_list

    def validate(self, option_dict: TypeOptionMap) -> ReportItemList:
        raise NotImplementedError()


class ValidatorAll(CompoundValidator):
    """
    Run all validators and return all their reports
    """

    def validate(self, option_dict: TypeOptionMap) -> ReportItemList:
        report_list = []
        for validator in self._validator_list:
            report_list.extend(validator.validate(option_dict))
        return report_list


class ValidatorFirstError(CompoundValidator):
    """
    Run validators in sequence, return reports once one reports an error
    """

    def validate(self, option_dict: TypeOptionMap) -> ReportItemList:
        report_list = []
        for validator in self._validator_list:
            new_report_list: ReportItemList = validator.validate(option_dict)
            report_list.extend(new_report_list)
            error_reported = False
            for report_item in new_report_list:
                if report_item.severity.level == ReportItemSeverity.ERROR:
                    error_reported = True
                    break
            if error_reported:
                break
        return report_list


### keys validators


class KeyValidator(ValidatorInterface):
    def __init__(
        self,
        option_name_list: Iterable[TypeOptionName],
        option_type: Optional[str] = None,
        severity: Optional[ReportItemSeverity] = None,
    ):
        """
        option_name_list -- names of the options to check
        option_type -- describes a type of the options for reporting
        severity -- severity of produced reports, defaults to error
        """
        self._option_name_list = option_name_list
        self._option_type = option_type
        self._severity = (
            ReportItemSeverity.error() if severity is None else severity
        )

    def validate(self, option_dict: TypeOptionMap) -> ReportItemList:
        raise NotImplementedError()


class CorosyncOption(KeyValidator):
    """
    Report INVALID_USERDEFINED_OPTIONS when the option_dict contains names not
    suitable for corosync.conf
    """

    def __init__(
        self,
        option_type: Optional[str] = None,
        severity: Optional[ReportItemSeverity] = None,
    ):
        super().__init__([], option_type=option_type, severity=severity)

    def validate(self, option_dict: TypeOptionMap) -> ReportItemList:
        not_valid_options = [
            name
            for name in option_dict
            if corosync_constants.OPTION_NAME_RE.fullmatch(name) is None
        ]
        if not_valid_options:
            # We must be strict and do not allow to override this validation,
            # otherwise setting a cratfed option name could be misused for
            # setting arbitrary corosync.conf settings.
            return [
                ReportItem(
                    self._severity,
                    reports.messages.InvalidUserdefinedOptions(
                        sorted(not_valid_options),
                        "a-z A-Z 0-9 /_-",
                        self._option_type,
                    ),
                )
            ]
        return []


class DependsOnOption(KeyValidator):
    """
    Report REQUIRED_OPTION_IS_MISSING when the option_dict contains
    option_name_list options and does not contain the prerequisite_option
    """

    def __init__(
        self,
        option_name_list: Iterable[TypeOptionName],
        prerequisite_name: TypeOptionName,
        option_type: Optional[str] = None,
        prerequisite_type: Optional[str] = None,
        severity: Optional[ReportItemSeverity] = None,
    ):
        """
        prerequisite_name -- name of the prerequisite options
        prerequisite_type -- describes the prerequisite for reporting
        """
        super().__init__(
            option_name_list, option_type=option_type, severity=severity
        )
        self._prerequisite_name = prerequisite_name
        self._prerequisite_type = prerequisite_type

    def validate(self, option_dict: TypeOptionMap) -> ReportItemList:
        return [
            ReportItem(
                self._severity,
                reports.messages.PrerequisiteOptionIsMissing(
                    option_name,
                    self._prerequisite_name,
                    self._option_type,
                    self._prerequisite_type,
                ),
            )
            for option_name in self._option_name_list
            if (
                option_name in option_dict
                and self._prerequisite_name not in option_dict
            )
        ]


class DeprecatedOption(KeyValidator):
    """
    Report DEPRECATED_OPTION when the option_dict contains option_name_list
    options
    """

    def __init__(
        self,
        option_name_list: Iterable[TypeOptionName],
        deprecated_by: Iterable[TypeOptionName],
        option_type: Optional[str] = None,
        severity: Optional[ReportItemSeverity] = None,
    ):
        """
        deprecated_by -- names of the options which should be used instead
        """
        super().__init__(
            option_name_list,
            option_type=option_type,
            severity=(
                ReportItemSeverity.deprecation()
                if severity is None
                else severity
            ),
        )
        self._deprecated_by = sorted(deprecated_by)

    def validate(self, option_dict: TypeOptionMap) -> ReportItemList:
        return [
            ReportItem(
                severity=self._severity,
                message=reports.messages.DeprecatedOption(
                    option_name,
                    self._deprecated_by,
                    self._option_type,
                ),
            )
            for option_name in self._option_name_list
            if (option_name in option_dict)
        ]


class IsRequiredAll(KeyValidator):
    """
    Report REQUIRED_OPTIONS_ARE_MISSING with all option_name_list options
    missing in option_dict
    """

    def validate(self, option_dict: TypeOptionMap) -> ReportItemList:
        missing = set(self._option_name_list) - set(option_dict.keys())
        if missing:
            return [
                ReportItem(
                    severity=self._severity,
                    message=reports.messages.RequiredOptionsAreMissing(
                        sorted(missing),
                        self._option_type,
                    ),
                )
            ]
        return []


class IsRequiredSome(KeyValidator):
    """
    Report REQUIRED_OPTIONS_ARE_MISSING when the option_dict does not contain
    at least one item from the option_name_list
    """

    def __init__(
        self,
        option_name_list: Iterable[TypeOptionName],
        option_type: Optional[str] = None,
        deprecated_option_name_list: Iterable[TypeOptionName] = frozenset(),
        severity: Optional[ReportItemSeverity] = None,
    ):
        """
        deprecated_option_name_list -- deprecated options from option_name_list
        """
        super().__init__(
            option_name_list, option_type=option_type, severity=severity
        )
        self._deprecated_option_name_list = deprecated_option_name_list

    def validate(self, option_dict: TypeOptionMap) -> ReportItemList:
        found = set(self._option_name_list) & set(option_dict.keys())
        if not found:
            return [
                ReportItem(
                    self._severity,
                    reports.messages.RequiredOptionOfAlternativesIsMissing(
                        sorted(self._option_name_list),
                        sorted(self._deprecated_option_name_list),
                        self._option_type,
                    ),
                )
            ]
        return []


class MutuallyExclusive(KeyValidator):
    """
    Report MUTUALLY_EXCLUSIVE_OPTIONS when there is more than one of
    mutually_exclusive_names in option_dict.
    """

    def validate(self, option_dict: TypeOptionMap) -> ReportItemList:
        found = set(self._option_name_list) & set(option_dict.keys())
        if len(found) > 1:
            return [
                ReportItem(
                    self._severity,
                    reports.messages.MutuallyExclusiveOptions(
                        sorted(found),
                        self._option_type,
                    ),
                )
            ]
        return []


class NamesIn(KeyValidator):
    """
    Report INVALID_OPTIONS for option_dict keys not in option_name_list
    """

    def __init__(
        self,
        option_name_list: Iterable[TypeOptionName],
        option_type: Optional[str] = None,
        allowed_option_patterns: Optional[StringIterable] = None,
        banned_name_list: Optional[Iterable[TypeOptionName]] = None,
        severity: Optional[ReportItemSeverity] = None,
    ):
        """
        allowed_option_patterns -- option patterns to be added to a report
        banned_name_list -- list of options which cannot be forced
        """
        super().__init__(
            option_name_list, option_type=option_type, severity=severity
        )
        self._allowed_option_patterns = allowed_option_patterns or []
        self._banned_name_set = set(banned_name_list or [])

    def validate(self, option_dict: TypeOptionMap) -> ReportItemList:
        name_set = set(option_dict.keys())
        banned_names = set()
        if not (
            self._severity.force_code is None
            and self._severity.level == ReportItemSeverity.ERROR
        ):
            banned_names = name_set & self._banned_name_set
        invalid_names = name_set - set(self._option_name_list) - banned_names

        report_list = []
        if invalid_names:
            report_list.append(
                ReportItem(
                    severity=self._severity,
                    message=reports.messages.InvalidOptions(
                        sorted(invalid_names),
                        sorted(self._option_name_list),
                        self._option_type,
                        allowed_patterns=sorted(self._allowed_option_patterns),
                    ),
                )
            )
        if banned_names:
            report_list.append(
                ReportItem.error(
                    reports.messages.InvalidOptions(
                        sorted(banned_names),
                        sorted(self._option_name_list),
                        self._option_type,
                    )
                )
            )
        return report_list


### values validators


class ValueValidator(ValidatorInterface):
    def __init__(
        self,
        option_name: TypeOptionName,
        option_name_for_report: Optional[str] = None,
    ):
        """
        option_name -- name of the option to check
        option_name_for_report -- optional option_name override
        """
        self._option_name = option_name
        self._option_name_for_report = option_name_for_report
        self.empty_string_valid = False

    def validate(self, option_dict: TypeOptionMap) -> ReportItemList:
        if self._option_name not in option_dict:
            return []
        value = ValuePair.get(option_dict[self._option_name])
        if self.empty_string_valid and is_empty_string(value.normalized):
            return []
        return self._validate_value(value)

    def _get_option_name_for_report(self) -> str:
        return (
            self._option_name_for_report
            if self._option_name_for_report is not None
            else self._option_name
        )

    def _validate_value(self, value: ValuePair) -> ReportItemList:
        raise NotImplementedError()


class ValuePredicateBase(ValueValidator):
    """
    Base class for simple predicate validators
    """

    def __init__(
        self,
        option_name: TypeOptionName,
        option_name_for_report: Optional[str] = None,
        severity: Optional[ReportItemSeverity] = None,
    ):
        """
        severity -- severity of produced reports, defaults to error
        """
        super().__init__(
            option_name, option_name_for_report=option_name_for_report
        )
        self._severity = (
            ReportItemSeverity.error() if severity is None else severity
        )
        self._value_cannot_be_empty = False
        self._forbidden_characters = None

    def _validate_value(self, value: ValuePair) -> ReportItemList:
        return (
            []
            if self._is_valid(value.normalized)
            else [self._get_report_item(value)]
        )

    def _get_report_item(self, value: ValuePair) -> ReportItem:
        return ReportItem(
            severity=self._severity,
            message=reports.messages.InvalidOptionValue(
                self._get_option_name_for_report(),
                value.original,
                self._get_allowed_values(),
                cannot_be_empty=self._value_cannot_be_empty,
                forbidden_characters=self._forbidden_characters,
            ),
        )

    def _is_valid(self, value: TypeOptionValue) -> bool:
        raise NotImplementedError()

    def _get_allowed_values(self) -> Any:
        # TODO Set proper return type. Currently it is not possible as pretty
        # much anything can be returned. ReportItemMessage must be fixed first.
        raise NotImplementedError()


class ValueCorosyncValue(ValueValidator):
    """
    Report INVALID_OPTION_VALUE when a value is not a valid corosync value

    This is meant to prevent entering characters which could be used to add
    custom sections / values to corosync.conf. It must never be allowed to
    force this validator.
    Other validators are meant to check if the value is otherwise valid
    (ValueIn, ValueIntegerInRange...) and empty / not empty. Their errors may be
    made forcible.
    """

    def _validate_value(self, value: ValuePair) -> ReportItemList:
        if not isinstance(value.normalized, str):
            return []
        forbidden_characters = "{}\n\r"
        if set(value.normalized) & set(forbidden_characters):
            # We must be strict and do not allow to override this validation,
            # otherwise setting a cratfed option value could be misused for
            # setting arbitrary corosync.conf settings.
            return [
                ReportItem.error(
                    reports.messages.InvalidOptionValue(
                        self._get_option_name_for_report(),
                        value.original,
                        None,
                        # Make it actually print "\n" and "\r" strings instead
                        # of going to the next line.
                        # Let the user know all
                        # forbidden characters right away. Do not let them try
                        # them one by one by only reporting those actually used
                        # in the value.
                        forbidden_characters="{}\\n\\r",
                    )
                )
            ]
        return []


class ValueFloat(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not a float number
    """

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return is_float(value)

    def _get_allowed_values(self) -> Any:
        return "a floating-point number"


class ValueId(ValueValidator):
    """
    Report ID errors and optionally book IDs along the way
    """

    def __init__(
        self,
        option_name: TypeOptionName,
        option_name_for_report: Optional[str] = None,
        id_provider: Optional[IdProvider] = None,
    ):
        """
        id_provider -- checks id uniqueness and books ids if set
        """
        super().__init__(
            option_name, option_name_for_report=option_name_for_report
        )
        self._id_provider = id_provider

    def _validate_value(self, value: ValuePair) -> ReportItemList:
        report_list: ReportItemList = []
        validate_id(value.normalized, self._option_name_for_report, report_list)
        if self._id_provider is not None and not report_list:
            report_list.extend(self._id_provider.book_ids(value.normalized))
        return report_list


class ValueDeprecated(ValueValidator):
    """
    Report DEPRECATED_OPTION_VALUE when a value has been deprecated and
    replaced by new value
    """

    def __init__(
        self,
        option_name: TypeOptionName,
        deprecation_map: Mapping[str, Optional[str]],
        severity: Optional[ReportItemSeverity] = None,
        option_name_for_report: Optional[str] = None,
    ):
        """
        deprecation_map -- keys are deprecated values and values are new
            values. If values is None, deprecated value has no direct
            replacement
        """
        super().__init__(
            option_name,
            option_name_for_report=option_name_for_report,
        )
        self._severity = (
            ReportItemSeverity.deprecation() if severity is None else severity
        )
        self._deprecation_map = deprecation_map

    def _validate_value(self, value: ValuePair) -> ReportItemList:
        if value.normalized in self._deprecation_map:
            return [
                ReportItem(
                    severity=self._severity,
                    message=reports.messages.DeprecatedOptionValue(
                        option_name=self._get_option_name_for_report(),
                        deprecated_value=value.original,
                        replaced_by=self._deprecation_map[value.normalized],
                    ),
                )
            ]

        return []


class ValueIn(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when a value is not in a set of allowed values
    """

    def __init__(
        self,
        option_name: TypeOptionName,
        allowed_value_list: Container[TypeOptionValue],
        option_name_for_report: Optional[str] = None,
        severity: Optional[ReportItemSeverity] = None,
    ):
        """
        allowed_value_list -- list of possible values
        severity -- severity of produced reports, defaults to error
        """
        super().__init__(
            option_name,
            option_name_for_report=option_name_for_report,
            severity=severity,
        )
        self._allowed_value_list = allowed_value_list

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return value in self._allowed_value_list

    def _get_allowed_values(self) -> Any:
        return self._allowed_value_list


class ValueInteger(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not an integer
    """

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return is_integer(value, None, None)

    def _get_allowed_values(self) -> Any:
        return "an integer"


class ValueIntegerInRange(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not an integer such that
    at_least <= value <= at_most
    """

    def __init__(
        self,
        option_name: TypeOptionName,
        at_least: int,
        at_most: int,
        option_name_for_report: Optional[str] = None,
        severity: Optional[ReportItemSeverity] = None,
    ):
        """
        at_least -- minimal allowed value
        at_most -- maximal allowed value
        severity -- severity of produced reports, defaults to error
        """
        super().__init__(
            option_name,
            option_name_for_report=option_name_for_report,
            severity=severity,
        )
        self._at_least = at_least
        self._at_most = at_most

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return is_integer(value, self._at_least, self._at_most)

    def _get_allowed_values(self) -> Any:
        return f"{self._at_least}..{self._at_most}"


class ValueIpAddress(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not an IP address
    """

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return is_ipv4_address(value) or is_ipv6_address(value)

    def _get_allowed_values(self) -> Any:
        return "an IP address"


class ValueNonnegativeInteger(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not an integer greater than -1
    """

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return is_integer(value, 0)

    def _get_allowed_values(self) -> Any:
        return "a non-negative integer"


class ValueNotEmpty(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when a value is empty
    """

    def __init__(
        self,
        option_name: TypeOptionName,
        # TODO Set proper type. ReportItemMessage must be fixed as well.
        value_desc_or_enum: Any,
        option_name_for_report: Optional[str] = None,
        severity: Optional[ReportItemSeverity] = None,
    ):
        """
        value_desc_or_enum -- a list or a description of possible values
        severity -- severity of produced reports, defaults to error
        """
        super().__init__(
            option_name,
            option_name_for_report=option_name_for_report,
            severity=severity,
        )
        self._value_desc_or_enum = value_desc_or_enum
        self._value_cannot_be_empty = True

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return not is_empty_string(value)

    def _get_allowed_values(self) -> Any:
        return self._value_desc_or_enum


class ValuePcmkBoolean(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not a pacemaker boolean value
    """

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return is_boolean(value)

    def _get_allowed_values(self) -> Any:
        bool_values = format_list(list(BOOLEAN_VALUES))
        return f"a pacemaker boolean value: {bool_values}"


class ValuePcmkDatespecPart(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not a valid Pacemaker
    Datespec part:
      * int or int1-int2
      * int in specified range
      * int2 > int1
    """

    def __init__(
        self,
        option_name: TypeOptionName,
        at_least: Optional[int],
        at_most: Optional[int],
        option_name_for_report: Optional[str] = None,
        severity: Optional[ReportItemSeverity] = None,
    ):
        """
        at_least -- minimal allowed value
        at_most -- maximal allowed value
        severity -- severity of produced reports, defaults to error
        """
        super().__init__(
            option_name,
            option_name_for_report=option_name_for_report,
            severity=severity,
        )
        self._at_least = at_least
        self._at_most = at_most

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return is_pcmk_datespec_part(value, self._at_least, self._at_most)

    def _get_allowed_values(self) -> Any:
        if self._at_least is None or self._at_most is None:
            return "an integer or integer-integer"
        return (
            f"{self._at_least}..{self._at_most} or "
            f"{self._at_least}..{self._at_most-1}-{self._at_least+1}..{self._at_most}"
        )


class ValuePcmkPercentage(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not a non-negative integer
    followed by '%' character.
    """

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return bool(value) and value[-1] == "%" and is_integer(value[:-1], 0)

    def _get_allowed_values(self) -> Any:
        return (
            "a non-negative integer followed by '%' (e.g. 0%, 50%, 200%, ...)"
        )


class ValuePcmkInteger(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not an integer or
    INFINITY/-INFINITY
    """

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return is_score(value)

    def _get_allowed_values(self) -> Any:
        return f"an integer or {SCORE_INFINITY} or -{SCORE_INFINITY}"


class ValuePcmkPositiveInteger(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not a positive integer or
    INFINITY
    """

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return value in [SCORE_INFINITY, f"+{SCORE_INFINITY}"] or is_integer(
            value, 1
        )

    def _get_allowed_values(self) -> Any:
        return f"a positive integer or {SCORE_INFINITY}"


class ValuePortNumber(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not a TCP or UDP port number
    """

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return is_port_number(value)

    def _get_allowed_values(self) -> Any:
        return "a port number (1..65535)"


class ValuePortRange(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not a TCP or UDP port range
    """

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return matches_regexp(value, "^[0-9]+-[0-9]+$") and all(
            is_port_number(part) for part in value.split("-", 1)
        )

    def _get_allowed_values(self) -> Any:
        return "port-port"


class ValuePositiveInteger(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not an integer greater than 0
    """

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return is_integer(value, 1)

    def _get_allowed_values(self) -> Any:
        return "a positive integer"


class ValueScore(ValueValidator):
    """
    Report INVALID_SCORE if the value is not a valid CIB score
    """

    def _validate_value(self, value: ValuePair) -> ReportItemList:
        report_list = []
        if not is_score(value.normalized):
            report_list.append(
                ReportItem.error(reports.messages.InvalidScore(value.original))
            )
        return report_list


class ValueTimeIntervalOrDuration(ValuePredicateBase):
    """
    Time interval in number+units or ISO8601 duration (e.g. 1, 2s, 3m, 4h,
    PT1H2M3S, ...)
    """

    def __init__(
        self,
        runner: CommandRunner,
        option_name: TypeOptionName,
        option_name_for_report: Optional[str] = None,
        severity: Optional[ReportItemSeverity] = None,
    ):
        super().__init__(
            option_name,
            option_name_for_report=option_name_for_report,
            severity=severity,
        )
        self.runner = runner

    def _is_valid(self, value: TypeOptionValue) -> bool:
        if value.startswith("P"):
            return is_duration(self.runner, value)
        return timeout_to_seconds(value) is not None

    def _get_allowed_values(self) -> Any:
        return "time interval (e.g. 1, 2s, 3m, 4h, PT1H2M3S, ...)"


class ValueTimeInterval(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not a time interval
    """

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return timeout_to_seconds(value) is not None

    def _get_allowed_values(self) -> Any:
        return "time interval (e.g. 1, 2s, 3m, 4h, ...)"


class ValueVersion(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not a version number
    """

    def _is_valid(self, value: TypeOptionValue) -> bool:
        return matches_regexp(value, r"^\d+(\.\d+)*$")

    def _get_allowed_values(self) -> Any:
        return "a version number (e.g. 1, 1.2, 1.23.45, ...)"


### predicates


def is_empty_string(value: TypeOptionValue) -> bool:
    """
    Check if the specified value is an empty string

    value -- value to check
    """
    return isinstance(value, str) and not value


def is_float(
    value: Union[str, int, float],
) -> bool:
    """
    Check if the specified value is a float number

    value -- value to check
    """
    if value is None:
        return False
    if isinstance(value, str) and not _FLOAT_RE.fullmatch(value):
        return False
    try:
        float(value)
    except ValueError:
        return False
    return True


def is_ipv4_address(value: TypeOptionValue) -> bool:
    """
    Check if the specified value is an IPv4 address

    string value -- value to check
    """
    try:
        # ip_address accepts both strings and integers. We check for "." to
        # make sure it is a string representation of an IP.
        if "." in value:
            ipaddress.IPv4Address(value)
            return True
        return False
    except (TypeError, ValueError):
        # not an IP address
        return False


def is_ipv6_address(value: TypeOptionValue) -> bool:
    """
    Check if the specified value is an IPv6 address

    string value -- value to check
    """
    try:
        # ip_address accepts both strings and integers. We check for ":" to
        # make sure it is a string representation of an IP.
        if ":" in value:
            ipaddress.IPv6Address(value)
            return True
        return False
    except (TypeError, ValueError):
        # not an IP address
        return False


def is_pcmk_datespec_part(
    value: str,
    at_least: Optional[int] = None,
    at_most: Optional[int] = None,
) -> bool:
    """
    Check if the value is a valid Pacemaker Datespec part:
      * int or int1-int2
      * int in specified range
      * int2 > int1
    """
    match = _PCMK_DATESPEC_PART_RE.fullmatch(value)
    if not match:
        return False
    if not is_integer(match["since"], at_least, at_most):
        return False
    if match["until"] is not None:
        if not is_integer(match["until"], at_least, at_most):
            return False
        if int(match["since"]) >= int(match["until"]):
            return False
    return True


def matches_regexp(value: TypeOptionValue, regexp: Union[str, Pattern]) -> bool:
    """
    Check if the specified value matches the specified regular expression

    value -- value to check
    regexp -- regexp pattern to match the value against
    """
    if not hasattr(regexp, "match"):
        regexp = re.compile(regexp)
    return cast(Pattern, regexp).match(value) is not None


### complex


class _ValidateAddRemoveBase:
    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        add_item_list: StringCollection,
        remove_item_list: StringCollection,
        current_item_list: StringCollection,
        container_type: reports.types.AddRemoveContainerType,
        item_type: reports.types.AddRemoveItemType,
        container_id: str,
        adjacent_item_id: Optional[str] = None,
        container_can_be_empty: bool = False,
        severity: Optional[ReportItemSeverity] = None,
    ):
        """
        Validate if items can be added or removed to or from a container.

        add_item_list -- items to be added
        remove_item_list -- items to be removed
        current_item_list -- items currently in the container
        container_type -- container type
        item_type -- item type
        container_id -- id of the container
        adjacent_item_id -- an adjacent item in the container
        container_can_be_empty -- flag to decide if container can be left empty
        severity -- severity of produced reports, defaults to error
        """
        # pylint: disable=too-many-arguments
        self._add_item_list = add_item_list
        self._remove_item_list = remove_item_list
        self._current_item_list = current_item_list
        self._container_type = container_type
        self._item_type = item_type
        self._container_id = container_id
        self._adjacent_item_id = adjacent_item_id
        self._container_can_be_empty = container_can_be_empty
        self._severity = (
            ReportItemSeverity.error() if severity is None else severity
        )

    def validate_add_or_remove_specified(self) -> ReportItemList:
        report_list: ReportItemList = []
        if not self._add_item_list and not self._remove_item_list:
            report_list.append(
                ReportItem(
                    self._severity,
                    reports.messages.AddRemoveItemsNotSpecified(
                        self._container_type,
                        self._item_type,
                        self._container_id,
                    ),
                )
            )
        return report_list

    @staticmethod
    def _get_duplicate_items(item_list: StringIterable) -> Set[str]:
        return {item for item, count in Counter(item_list).items() if count > 1}

    def validate_no_duplicate_items(self) -> ReportItemList:
        report_list: ReportItemList = []
        duplicate_items_list = self._get_duplicate_items(
            self._add_item_list
        ) | self._get_duplicate_items(self._remove_item_list)
        if duplicate_items_list:
            report_list.append(
                ReportItem(
                    self._severity,
                    reports.messages.AddRemoveItemsDuplication(
                        self._container_type,
                        self._item_type,
                        self._container_id,
                        sorted(duplicate_items_list),
                    ),
                )
            )
        return report_list

    def validate_add_items_not_yet_present(self) -> ReportItemList:
        report_list: ReportItemList = []
        already_present = set(self._add_item_list).intersection(
            self._current_item_list
        )
        # report only if an adjacent id is not defined, because we want to allow
        # to move items when adjacent_item_id is specified
        if self._adjacent_item_id is None and already_present:
            report_list.append(
                ReportItem.error(
                    reports.messages.AddRemoveCannotAddItemsAlreadyInTheContainer(
                        self._container_type,
                        self._item_type,
                        self._container_id,
                        sorted(already_present),
                    )
                )
            )
        return report_list

    def validate_remove_items_present(self) -> ReportItemList:
        report_list: ReportItemList = []
        missing_items = set(self._remove_item_list).difference(
            self._current_item_list
        )
        if missing_items:
            report_list.append(
                ReportItem(
                    self._severity,
                    reports.messages.AddRemoveCannotRemoveItemsNotInTheContainer(
                        self._container_type,
                        self._item_type,
                        self._container_id,
                        sorted(missing_items),
                    ),
                )
            )
        return report_list

    def validate_item_not_both_added_and_removed(self) -> ReportItemList:
        report_list: ReportItemList = []
        common_items = set(self._add_item_list) & set(self._remove_item_list)
        if common_items:
            report_list.append(
                ReportItem.error(
                    reports.messages.AddRemoveCannotAddAndRemoveItemsAtTheSameTime(
                        self._container_type,
                        self._item_type,
                        self._container_id,
                        sorted(common_items),
                    )
                )
            )
        return report_list

    def validate_container_wont_be_empty(self) -> ReportItemList:
        report_list: ReportItemList = []
        if not self._container_can_be_empty and not self._add_item_list:
            remaining_items = set(self._current_item_list).difference(
                self._remove_item_list
            )
            if not remaining_items:
                report_list.append(
                    ReportItem.error(
                        reports.messages.AddRemoveCannotRemoveAllItemsFromTheContainer(
                            self._container_type,
                            self._item_type,
                            self._container_id,
                            list(self._current_item_list),
                        )
                    )
                )
        return report_list

    def validate_adjacent(self) -> ReportItemList:
        report_list: ReportItemList = []
        if not self._adjacent_item_id:
            return report_list

        if self._adjacent_item_id not in self._current_item_list:
            report_list.append(
                ReportItem.error(
                    reports.messages.AddRemoveAdjacentItemNotInTheContainer(
                        self._container_type,
                        self._item_type,
                        self._container_id,
                        self._adjacent_item_id,
                    )
                )
            )
        if self._adjacent_item_id in self._add_item_list:
            report_list.append(
                ReportItem.error(
                    reports.messages.AddRemoveCannotPutItemNextToItself(
                        self._container_type,
                        self._item_type,
                        self._container_id,
                        self._adjacent_item_id,
                    )
                )
            )
        if not self._add_item_list:
            report_list.append(
                ReportItem.error(
                    reports.messages.AddRemoveCannotSpecifyAdjacentItemWithoutItemsToAdd(
                        self._container_type,
                        self._item_type,
                        self._container_id,
                        self._adjacent_item_id,
                    )
                )
            )
        return report_list


def validate_add_remove_items(
    add_item_list: StringCollection,
    remove_item_list: StringCollection,
    current_item_list: StringCollection,
    container_type: reports.types.AddRemoveContainerType,
    item_type: reports.types.AddRemoveItemType,
    container_id: str,
    adjacent_item_id: Optional[str] = None,
    container_can_be_empty: bool = False,
) -> ReportItemList:
    """
    Validate if items can be added or removed to or from a container.

    add_item_list -- items to be added
    remove_item_list -- items to be removed
    current_item_list -- items currently in the container
    container_type -- container type
    item_type -- item type
    container_id -- id of the container
    adjacent_item_id -- an adjacent item in the container
    container_can_be_empty -- flag to decide if container can be left empty
    """
    validator = _ValidateAddRemoveBase(
        add_item_list,
        remove_item_list,
        current_item_list,
        container_type,
        item_type,
        container_id,
        adjacent_item_id=adjacent_item_id,
        container_can_be_empty=container_can_be_empty,
    )
    return (
        validator.validate_add_or_remove_specified()
        + validator.validate_no_duplicate_items()
        + validator.validate_add_items_not_yet_present()
        + validator.validate_remove_items_present()
        + validator.validate_item_not_both_added_and_removed()
        + validator.validate_container_wont_be_empty()
        + validator.validate_adjacent()
    )


def validate_set_unset_items(
    add_item_list: StringCollection,
    remove_item_list: StringCollection,
    current_item_list: StringCollection,
    container_type: reports.types.AddRemoveContainerType,
    item_type: reports.types.AddRemoveItemType,
    container_id: str,
    severity: Optional[ReportItemSeverity] = None,
) -> ReportItemList:
    """
    Validate if items can be set or unset to or from a dict of options.

    add_item_list -- items to be added
    remove_item_list -- items to be removed
    current_item_list -- items currently in the container
    container_type -- container type
    item_type -- item type
    container_id -- id of the container
    severity -- severity of produced reports, defaults to error
    """
    validator = _ValidateAddRemoveBase(
        add_item_list,
        remove_item_list,
        current_item_list,
        container_type,
        item_type,
        container_id,
        adjacent_item_id=None,
        container_can_be_empty=True,
        severity=severity,
    )
    return (
        validator.validate_add_or_remove_specified()
        + validator.validate_no_duplicate_items()
        + validator.validate_remove_items_present()
        + validator.validate_item_not_both_added_and_removed()
    )
