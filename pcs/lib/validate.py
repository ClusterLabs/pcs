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
from collections import namedtuple
import ipaddress
import re

from pcs.common import reports
from pcs.common.reports import (
    ReportItem,
    ReportItemList,
    ReportItemSeverity,
)
from pcs.lib.corosync import constants as corosync_constants
from pcs.lib.pacemaker.values import (
    timeout_to_seconds,
    validate_id,
)

_INTEGER_RE = re.compile(r"^[+-]?[0-9]+$")

### normalization

class ValuePair(namedtuple("ValuePair", "original normalized")):
    """
    Storage for the original value and its normalized form
    """
    @staticmethod
    def get(val):
        return val if isinstance(val, ValuePair) else ValuePair(val, val)

def values_to_pairs(option_dict, normalize):
    """
    Return a dict derived from option_dict where every value is instance of
    ValuePair.

    dict option_dict contains values that should be paired with the normalized
        form
    callable normalize should take key and value and return normalized form.
        Function option_value_normalization can be good base for create such
        callable.
    """
    option_dict_with_pairs = {}
    for key, value in option_dict.items():
        if not isinstance(value, ValuePair):
            value = ValuePair(
                original=value,
                normalized=normalize(key, value),
            )
        option_dict_with_pairs[key] = value
    return option_dict_with_pairs

def pairs_to_values(option_dict):
    """
    Take a dict which has OptionValuePairs as its values and return dict with
    normalized forms as its values. It is reverse function to
    values_to_pairs.

    dict option_dict contains OptionValuePairs as its values
    """
    raw_option_dict = {}
    for key, value in option_dict.items():
        if isinstance(value, ValuePair):
            value = value.normalized
        raw_option_dict[key] = value
    return raw_option_dict

def option_value_normalization(normalization_map):
    """
    Return function that takes key and value and return the normalized form.

    dict normalization_map has on each key function that takes value and return
        its normalized form.
    """
    def normalize(key, value):
        return(
            value if key not in normalization_map
            else normalization_map[key](value)
        )
    return normalize

### generic validators

class ValidatorInterface():
    """
    Base interface of all validators
    """
    def validate(self, option_dict):
        raise NotImplementedError()

class CompoundValidator(ValidatorInterface):
    """
    Base abstract class for compound validators
    """
    def __init__(self, validator_list):
        self._validator_list = validator_list

    def validate(self, option_dict):
        raise NotImplementedError()

class ValidatorAll(CompoundValidator):
    """
    Run all validators and return all their reports
    """
    def validate(self, option_dict):
        report_list = []
        for validator in self._validator_list:
            report_list.extend(validator.validate(option_dict))
        return report_list

class ValidatorFirstError(CompoundValidator):
    """
    Run validators in sequence, return reports once one reports an error
    """
    def validate(self, option_dict):
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
    def __init__(self, option_name_list, option_type=None):
        """
        iterable option_name_list -- names of the options to check
        string option_type -- describes a type of the options for reporting
        """
        self._option_name_list = option_name_list
        self._option_type = option_type

    def validate(self, option_dict):
        raise NotImplementedError()

class CorosyncOption(KeyValidator):
    """
    Report INVALID_USERDEFINED_OPTIONS when the option_dict contains names not
    suitable for corosync.conf
    """
    def __init__(self, option_type=None):
        super().__init__(None, option_type=option_type)

    def validate(self, option_dict):
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
                ReportItem.error(
                    reports.messages.InvalidUserdefinedOptions(
                        sorted(not_valid_options),
                        self._option_type,
                        "a-z A-Z 0-9 /_-",
                    )
                )
            ]
        return []

class DependsOnOption(KeyValidator):
    """
    Report REQUIRED_OPTION_IS_MISSING when the option_dict contains
    option_name_list options and does not contain the prerequisite_option
    """
    def __init__(
        self, option_name_list, prerequisite_name, option_type=None,
        prerequisite_type=None
    ):
        """
        string prerequisite_name -- name of the prerequisite options
        string prerequisite_type -- describes the prerequisite for reporting
        """
        super().__init__(option_name_list, option_type=option_type)
        self._prerequisite_name = prerequisite_name
        self._prerequisite_type = prerequisite_type

    def validate(self, option_dict):
        return [
            ReportItem.error(
                reports.messages.PrerequisiteOptionIsMissing(
                    option_name,
                    self._prerequisite_name,
                    self._option_type,
                    self._prerequisite_type,
                )
            )
            for option_name in self._option_name_list
            if (
                option_name in option_dict
                and
                self._prerequisite_name not in option_dict
            )
        ]

class IsRequiredAll(KeyValidator):
    """
    Report REQUIRED_OPTIONS_ARE_MISSING with all option_name_list options
    missing in option_dict
    """
    def validate(self, option_dict):
        missing = set(self._option_name_list) - set(option_dict.keys())
        if missing:
            return [ReportItem.error(
                reports.messages.RequiredOptionsAreMissing(
                    sorted(missing),
                    self._option_type,
                )
            )]
        return []

class IsRequiredSome(KeyValidator):
    """
    Report REQUIRED_OPTIONS_ARE_MISSING when the option_dict does not contain
    at least one item from the option_name_list
    """
    def validate(self, option_dict):
        found = set(self._option_name_list) & set(option_dict.keys())
        if not found:
            return [
                ReportItem.error(
                    reports.messages.RequiredOptionOfAlternativesIsMissing(
                        self._option_name_list,
                        self._option_type,
                    )
                )
            ]
        return []

class MutuallyExclusive(KeyValidator):
    """
    Report MUTUALLY_EXCLUSIVE_OPTIONS when there is more than one of
    mutually_exclusive_names in option_dict.
    """
    def validate(self, option_dict):
        found = set(self._option_name_list) & set(option_dict.keys())
        if len(found) > 1:
            return [
                ReportItem.error(
                    reports.messages.MutuallyExclusiveOptions(
                        sorted(found),
                        self._option_type,
                    )
                )
            ]
        return []

class NamesIn(KeyValidator):
    """
    Report INVALID_OPTIONS for option_dict keys not in option_name_list
    """
    def __init__(
        self, option_name_list, option_type=None,
        allowed_option_patterns=None, banned_name_list=None,
        code_for_warning=None, produce_warning=False,
    ):
        """
        mixed allowed_option_patterns -- option patterns to be added to a report
        list banned_name_list -- list of options which cannot be forced
        string code_for_warning -- which code makes this produce warnings
        bool produce_warning -- False produces an error, True a warning
        """
        super().__init__(option_name_list, option_type=option_type)
        self._allowed_option_patterns = allowed_option_patterns or []
        self._banned_name_set = set(banned_name_list or [])
        self._code_for_warning = code_for_warning
        self._produce_warning = produce_warning

    def validate(self, option_dict):
        name_set = set(option_dict.keys())
        banned_names = set()
        if not (self._code_for_warning is None and not self._produce_warning):
            banned_names = name_set & self._banned_name_set
        invalid_names = name_set - set(self._option_name_list) - banned_names

        report_list = []
        if invalid_names:
            report_list.append(
                ReportItem(
                    severity=reports.item.get_severity(
                        self._code_for_warning,
                        self._produce_warning,
                    ),
                    message=reports.messages.InvalidOptions(
                        sorted(invalid_names),
                        sorted(self._option_name_list),
                        self._option_type,
                        allowed_patterns=sorted(self._allowed_option_patterns),
                    )
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
    def __init__(self, option_name, option_name_for_report=None):
        """
        srring option_name -- name of the option to check
        string option_name_for_report -- optional option_name override
        """
        self._option_name = option_name
        self._option_name_for_report = option_name_for_report
        self.empty_string_valid = False

    def validate(self, option_dict):
        if self._option_name not in option_dict:
            return []
        value = ValuePair.get(option_dict[self._option_name])
        if self.empty_string_valid and is_empty_string(value.normalized):
            return []
        return self._validate_value(value)

    def _get_option_name_for_report(self):
        return (
            self._option_name_for_report
                if self._option_name_for_report is not None
                else self._option_name
        )

    def _validate_value(self, value):
        raise NotImplementedError()

class ValuePredicateBase(ValueValidator):
    """
    Base class for simple predicate validators
    """
    def __init__(
        self, option_name, option_name_for_report=None,
        code_for_warning=None, produce_warning=False,
    ):
        """
        string code_for_warning -- which code makes this produce warnings
        bool produce_warning -- False produces an error, True a warning
        """
        super().__init__(
            option_name,
            option_name_for_report=option_name_for_report
        )
        self._code_for_warning = code_for_warning
        self._produce_warning = produce_warning
        self._value_cannot_be_empty = False
        self._forbidden_characters = None

    def _validate_value(self, value):
        if not self._is_valid(value.normalized):
            return [
                ReportItem(
                    severity=reports.item.get_severity(
                        self._code_for_warning,
                        self._produce_warning,
                    ),
                    message=reports.messages.InvalidOptionValue(
                        self._get_option_name_for_report(),
                        value.original,
                        self._get_allowed_values(),
                        cannot_be_empty=self._value_cannot_be_empty,
                        forbidden_characters=self._forbidden_characters,
                    )
                )
            ]

        return []

    def _is_valid(self, value):
        raise NotImplementedError()

    def _get_allowed_values(self):
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
    def _validate_value(self, value):
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
                        forbidden_characters="{}\\n\\r"
                    )
                )
            ]
        return []

class ValueId(ValueValidator):
    """
    Report ID errors and optionally book IDs along the way
    """
    def __init__(
        self, option_name, option_name_for_report=None, id_provider=None
    ):
        """
        IdProvider id_provider -- checks id uniqueness and books ids if set
        """
        super().__init__(
            option_name,
            option_name_for_report=option_name_for_report
        )
        self._id_provider = id_provider

    def _validate_value(self, value):
        report_list = []
        validate_id(value.normalized, self._option_name_for_report, report_list)
        if self._id_provider is not None and not report_list:
            report_list.extend(
                self._id_provider.book_ids(value.normalized)
            )
        return report_list

class ValueIn(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when a value is not in a set of allowed values
    """
    def __init__(
        self, option_name, allowed_value_list, option_name_for_report=None,
        code_for_warning=None, produce_warning=False,
    ):
        """
        list of string allowed_value_list -- list of possible values
        """
        super().__init__(
            option_name,
            option_name_for_report=option_name_for_report,
            code_for_warning=code_for_warning,
            produce_warning=produce_warning,
        )
        self._allowed_value_list = allowed_value_list

    def _is_valid(self, value):
        return value in self._allowed_value_list

    def _get_allowed_values(self):
        return self._allowed_value_list

class ValueIntegerInRange(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not an integer such that
    at_least <= value <= at_most
    """
    def __init__(
        self, option_name, at_least, at_most, option_name_for_report=None,
        code_for_warning=None, produce_warning=False,
    ):
        """
        int at_least -- minimal allowed value
        int at_most -- maximal allowed value
        """
        super().__init__(
            option_name,
            option_name_for_report=option_name_for_report,
            code_for_warning=code_for_warning,
            produce_warning=produce_warning,
        )
        self._at_least = at_least
        self._at_most = at_most

    def _is_valid(self, value):
        return is_integer(value, self._at_least, self._at_most)

    def _get_allowed_values(self):
        return f"{self._at_least}..{self._at_most}"

class ValueIpAddress(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not an IP address
    """
    def _is_valid(self, value):
        return is_ipv4_address(value) or is_ipv6_address(value)

    def _get_allowed_values(self):
        return "an IP address"

class ValueNonnegativeInteger(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not an integer greater than -1
    """
    def _is_valid(self, value):
        return is_integer(value, 0)

    def _get_allowed_values(self):
        return "a non-negative integer"

class ValueNotEmpty(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when a value is empty
    """
    def __init__(
        self, option_name, value_desc_or_enum, option_name_for_report=None,
        code_for_warning=None, produce_warning=False,
    ):
        """
        mexed value_desc_or_enum -- a list or a description of possible values
        """
        super().__init__(
            option_name,
            option_name_for_report=option_name_for_report,
            code_for_warning=code_for_warning,
            produce_warning=produce_warning,
        )
        self._value_desc_or_enum = value_desc_or_enum
        self._value_cannot_be_empty = True

    def _is_valid(self, value):
        return not is_empty_string(value)

    def _get_allowed_values(self):
        return self._value_desc_or_enum

class ValuePortNumber(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not a TCP or UDP port number
    """
    def _is_valid(self, value):
        return is_port_number(value)

    def _get_allowed_values(self):
        return "a port number (1..65535)"

class ValuePortRange(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not a TCP or UDP port range
    """
    def _is_valid(self, value):
        return (
            matches_regexp(value, "^[0-9]+-[0-9]+$")
            and
            all([is_port_number(part) for part in value.split("-", 1)])
        )

    def _get_allowed_values(self):
        return "port-port"

class ValuePositiveInteger(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not an integer greater than 0
    """
    def _is_valid(self, value):
        return is_integer(value, 1)

    def _get_allowed_values(self):
        return "a positive integer"

class ValueTimeInterval(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not a time interval
    """
    def _is_valid(self, value):
        return timeout_to_seconds(value) is not None

    def _get_allowed_values(self):
        return "time interval (e.g. 1, 2s, 3m, 4h, ...)"

### predicates

def is_empty_string(value):
    """
    Check if the specified value is an empty string

    mixed value -- value to check
    """
    return isinstance(value, str) and not value

def is_integer(value, at_least=None, at_most=None):
    """
    Check if the specified value is an integer, optionally check a range

    mixed value -- string, int or float, value to check
    """
    try:
        if value is None or isinstance(value, float):
            return False
        if isinstance(value, str) and not _INTEGER_RE.fullmatch(value):
            return False
        value_int = int(value)
        if at_least is not None and value_int < at_least:
            return False
        if at_most is not None and value_int > at_most:
            return False
    except ValueError:
        return False
    return True

def is_ipv4_address(value):
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

def is_ipv6_address(value):
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

def is_port_number(value):
    """
    Check if the specified value is a TCP or UDP port number

    mixed value -- string, int or float, value to check
    """
    return is_integer(value, 1, 65535)

def matches_regexp(value, regexp):
    """
    Check if the specified value matches the specified regular expression

    mixed value -- string, int or float, value to check
    mixed regexp -- string or RegularExpression to match the value against
    """
    if not hasattr(regexp, "match"):
        regexp = re.compile(regexp)
    return regexp.match(value) is not None

### tools

def set_warning(code_for_warning, produce_warning):
    """
    A usefull shortcut for calling validators

    string code_for_warning -- code to force an error
    bool produce_warning -- report warnings instead of errors
    """
    return {
        "code_for_warning": code_for_warning,
        "produce_warning": produce_warning,
    }
