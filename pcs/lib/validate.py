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

from pcs.lib import reports
from pcs.lib.pacemaker.values import (
    timeout_to_seconds,
    validate_id,
)

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
            reports.prerequisite_option_is_missing(
                option_name,
                self._prerequisite_name,
                self._option_type,
                self._prerequisite_type
            )
            for option_name in self._option_name_list
            if (
                option_name in option_dict
                and
                self._prerequisite_name not in option_dict
            )
        ]

def depends_on_option(
    option_name, prerequisite_option, option_type="", prerequisite_type=""
):
    # TODO remove
    """
    Get a validator reporting REQUIRED_OPTION_IS_MISSING when the option_dict
    does not contain the prerequisite_option and contains the option_name.

    string option_name -- name of the option to check
    string prerequisite_option -- name of the option which is a prerequisite
    string option_type -- describes a type of the option for reporting purposes
    """
    def validate(option_dict):
        if (
            option_name in option_dict
            and
            prerequisite_option not in option_dict
        ):
            return [reports.prerequisite_option_is_missing(
                option_name,
                prerequisite_option,
                option_type,
                prerequisite_type
            )]
        return []
    return validate

class IsRequiredAll(KeyValidator):
    """
    Report REQUIRED_OPTIONS_ARE_MISSING with all option_name_list options
    missing in option_dict
    """
    def validate(self, option_dict):
        missing = set(self._option_name_list) - set(option_dict.keys())
        if missing:
            return [reports.required_options_are_missing(
                missing,
                self._option_type,
            )]
        return []

def is_required(option_name, option_type=""):
    # TODO remove
    """
    Return a the function that takes option_dict and returns report list
    (with REQUIRED_OPTIONS_IS_MISSING when option_dict does not contain
    option_name).

    string option_name is name of option of option_dict that will be tested
    string option_type describes type of option for reporting purposes
    """
    def validate(option_dict):
        if option_name not in option_dict:
            return [reports.required_options_are_missing(
                [option_name],
                option_type,
            )]
        return []
    return validate

class IsRequiredSome(KeyValidator):
    """
    Report REQUIRED_OPTIONS_ARE_MISSING when the option_dict does not contain
    at least one item from the option_name_list
    """
    def validate(self, option_dict):
        found = set(self._option_name_list) & set(option_dict.keys())
        if not found:
            return [reports.required_option_of_alternatives_is_missing(
                self._option_name_list,
                self._option_type,
            )]
        return []

def is_required_some_of(option_name_list, option_type=""):
    # TODO remove
    """
    Get a validator reporting REQUIRED_OPTION_IS_MISSING report when the
    option_dict does not contain at least one item from the option_name_list.

    iterable option_name_list -- names of options of the option_dict to test
    string option_type -- describes a type of the option for reporting purposes
    """
    def validate(option_dict):
        found_names = set.intersection(
            set(option_dict.keys()),
            set(option_name_list)
        )
        if not found_names:
            return [reports.required_option_of_alternatives_is_missing(
                sorted(option_name_list),
                option_type,
            )]
        return []
    return validate

class MutuallyExclusive(KeyValidator):
    """
    Report MUTUALLY_EXCLUSIVE_OPTIONS when there is more than one of
    mutually_exclusive_names in option_dict.
    """
    def validate(self, option_dict):
        found = set(self._option_name_list) & set(option_dict.keys())
        if len(found) > 1:
            return [reports.mutually_exclusive_options(
                found,
                self._option_type,
            )]
        return []

def mutually_exclusive(mutually_exclusive_names, option_type="option"):
    # TODO remove
    """
    Return a list with report MUTUALLY_EXCLUSIVE_OPTIONS when in option_dict
    appears more than one of mutually_exclusive_names.

    list|set mutually_exclusive_names contains option names that cannot appear
        together
    string option_type describes type of option for reporting purposes
    """
    def validate(option_dict):
        found_names = set.intersection(
            set(option_dict.keys()),
            set(mutually_exclusive_names)
        )
        if len(found_names) > 1:
            return [reports.mutually_exclusive_options(
                sorted(found_names),
                option_type,
            )]
        return []
    return validate

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

        create_report = reports.get_problem_creator(
            self._code_for_warning,
            self._produce_warning
        )
        if invalid_names:
            report_list.append(create_report(
                reports.invalid_options,
                invalid_names,
                self._option_name_list,
                self._option_type,
                allowed_option_patterns=self._allowed_option_patterns,
            ))
        if banned_names:
            report_list.append(reports.invalid_options(
                banned_names,
                self._option_name_list,
                self._option_type,
            ))
        return report_list

def names_in(
    allowed_name_list, name_list, option_type="option",
    code_to_allow_extra_names=None, extra_names_allowed=False,
    allowed_option_patterns=None, banned_name_list=None,
):
    # TODO remove
    """
    Return a list with report INVALID_OPTIONS when in name_list is a name that
    is not in allowed_name_list.

    list allowed_name_list contains names which are valid
    list name_list contains names for validation
    string option_type describes type of option for reporting purposes
    string code_to_allow_extra_names is code for forcing invalid names. If it is
        empty report INVALID_OPTIONS is non-forceable error. If it is not empty
        report INVALID_OPTIONS is forceable error or warning.
    bool extra_names_allowed is flag that complements code_to_allow_extra_names
        and determines wheter is report INVALID_OPTIONS forceable error or
        warning.
    mixed allowed_option_patterns -- option patterns to be added to a report
    list banned_name_list -- list of options which cannot be forced
    """
    name_set = set(name_list)
    banned_set = set(banned_name_list or [])
    banned_names = set()
    if not (code_to_allow_extra_names is None and not extra_names_allowed):
        banned_names = name_set & banned_set
    invalid_names = name_set - set(allowed_name_list) - banned_names

    report_list = []

    create_report = reports.get_problem_creator(
        code_to_allow_extra_names,
        extra_names_allowed
    )
    if invalid_names:
        report_list.append(create_report(
            reports.invalid_options,
            sorted(invalid_names),
            sorted(allowed_name_list),
            option_type,
            allowed_option_patterns=sorted(allowed_option_patterns or [])
        ))
    if banned_names:
        report_list.append(reports.invalid_options(
            sorted(banned_names),
            sorted(allowed_name_list),
            option_type,
        ))
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

    def _validate_value(self, value):
        if not self._is_valid(value.normalized):
            create_report = reports.get_problem_creator(
                self._code_for_warning,
                self._produce_warning
            )
            return [create_report(
                reports.invalid_option_value,
                (
                    self._option_name_for_report
                    if self._option_name_for_report is not None
                    else self._option_name
                ),
                value.original,
                self._get_allowed_values(),
            )]

        return []

    def _is_valid(self, value):
        raise NotImplementedError()

    def _get_allowed_values(self):
        raise NotImplementedError()

def value_cond(
    option_name, predicate, value_type_or_enum, option_name_for_report=None,
    code_to_allow_extra_values=None, extra_values_allowed=False
):
    # TODO remove
    """
    Return a validation  function that takes option_dict and returns report list
    (with INVALID_OPTION_VALUE when option_name is not in allowed_values).

    string option_name is name of option of option_dict that will be tested
    function predicate takes one parameter, normalized value
    list or string value_type_or_enum list of possible values or string
        description of value type
    string option_name_for_report is substitued by option name if is None
    string code_to_allow_extra_values is code for forcing invalid names. If it
        is empty report INVALID_OPTION_VALUE is non-forceable error. If it is
        not empty report INVALID_OPTION_VALUE is forceable error or warning.
    bool extra_values_allowed flag that complements code_to_allow_extra_values
        and determines wheter is report INVALID_OPTION_VALUE forceable error or
        warning.
    """
    @_if_option_exists(option_name)
    def validate(option_dict):
        value = ValuePair.get(option_dict[option_name])

        if not predicate(value.normalized):
            create_report = reports.get_problem_creator(
                code_to_allow_extra_values,
                extra_values_allowed
            )
            return [create_report(
                reports.invalid_option_value,
                option_name_for_report if option_name_for_report is not None
                    else option_name
                ,
                value.original,
                value_type_or_enum,
            )]

        return []
    return validate

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

def value_id(option_name, option_name_for_report=None, id_provider=None):
    # TODO remove
    """
    Get a validator reporting ID errors and optionally booking IDs along the way

    string option_name -- name of the option to check
    string option_name_for_report -- substitued by the option_name if not set
    IdProvider id_provider -- used to check id uniqueness if set
    """
    @_if_option_exists(option_name)
    def validate(option_dict):
        value = ValuePair.get(option_dict[option_name])
        report_list = []
        validate_id(value.normalized, option_name_for_report, report_list)
        if id_provider is not None and not report_list:
            report_list.extend(
                id_provider.book_ids(value.normalized)
            )
        return report_list
    return validate

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

def value_in(
    option_name, allowed_values, option_name_for_report=None,
    code_to_allow_extra_values=None, extra_values_allowed=False
):
    # TODO remove
    """
    Special case of value_cond function.returned function checks whenever value
    is included allowed_values. If not list of ReportItem will be returned.

    option_name -- string, name of option to check
    allowed_values -- list of strings, list of possible values
    option_name_for_report -- string, it is substitued by option name if is None
    code_to_allow_extra_values -- string, code for forcing invalid names. If it
        is empty report INVALID_OPTION_VALUE is non-forceable error. If it is
        not empty report INVALID_OPTION_VALUE is forceable error or warning.
    extra_values_allowed -- bool flag complementing code_to_allow_extra_values
        and determines wheter is report INVALID_OPTION_VALUE forceable error or
        warning.
    """
    return value_cond(
        option_name,
        lambda normalized_value: normalized_value in allowed_values,
        allowed_values,
        option_name_for_report=option_name_for_report,
        code_to_allow_extra_values=code_to_allow_extra_values,
        extra_values_allowed=extra_values_allowed,
    )

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

def value_integer_in_range(
    option_name, at_least, at_most, option_name_for_report=None,
    code_to_allow_extra_values=None, extra_values_allowed=False
):
    # TODO remove
    """
    Get a validator reporting INVALID_OPTION_VALUE when the value is not an
    integer such that at_least <= value <= at_most

    string option_name -- name of the option to check
    int at_least -- minimal allowed value
    int at_most -- maximal allowed value
    string option_name_for_report -- substitued by the option_name if not set
    string code_to_allow_extra_values -- create a report forceable by this code
    bool extra_values_allowed -- create a warning instead of an error if True
    """
    return value_cond(
        option_name,
        lambda value: is_integer(value, at_least, at_most),
        "{min}..{max}".format(min=at_least, max=at_most),
        option_name_for_report=option_name_for_report,
        code_to_allow_extra_values=code_to_allow_extra_values,
        extra_values_allowed=extra_values_allowed,
    )

class ValueIpAddress(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not an IP address
    """
    def _is_valid(self, value):
        return is_ipv4_address(value) or is_ipv6_address(value)

    def _get_allowed_values(self):
        return "an IP address"

def value_ip_address(
    option_name, option_name_for_report=None,
    code_to_allow_extra_values=None, extra_values_allowed=False
):
    # TODO remove
    """
    Get a validator reporting INVALID_OPTION_VALUE when the value is not
    an IP address

    string option_name -- name of the option to check
    string option_name_for_report -- substitued by the option_name if not set
    string code_to_allow_extra_values -- create a report forceable by this code
    bool extra_values_allowed -- create a warning instead of an error if True
    """
    return value_cond(
        option_name,
        lambda value: is_ipv4_address(value) or is_ipv6_address(value),
        "an IP address",
        option_name_for_report=option_name_for_report,
        code_to_allow_extra_values=code_to_allow_extra_values,
        extra_values_allowed=extra_values_allowed,
    )

class ValueNonnegativeInteger(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not an integer greater than -1
    """
    def _is_valid(self, value):
        return is_integer(value, 0)

    def _get_allowed_values(self):
        return "a non-negative integer"

def value_nonnegative_integer(
    option_name, option_name_for_report=None,
    code_to_allow_extra_values=None, extra_values_allowed=False
):
    # TODO remove
    """
    Get a validator reporting INVALID_OPTION_VALUE when the value is not
    an integer greater than -1

    string option_name -- name of the option to check
    string option_name_for_report -- substitued by the option_name if not set
    string code_to_allow_extra_values -- create a report forceable by this code
    bool extra_values_allowed -- create a warning instead of an error if True
    """
    return value_cond(
        option_name,
        lambda value: is_integer(value, 0),
        "a non-negative integer",
        option_name_for_report=option_name_for_report,
        code_to_allow_extra_values=code_to_allow_extra_values,
        extra_values_allowed=extra_values_allowed,
    )

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

    def _is_valid(self, value):
        return not is_empty_string(value)

    def _get_allowed_values(self):
        return self._value_desc_or_enum

def value_not_empty(
    option_name, value_type_or_enum, option_name_for_report=None,
    code_to_allow_extra_values=None, extra_values_allowed=False
):
    # TODO remove
    """
    Get a validator reporting INVALID_OPTION_VALUE when the value is empty

    string option_name -- name of the option to check
    string option_name_for_report -- substitued by the option_name if not set
    string code_to_allow_extra_values -- create a report forceable by this code
    bool extra_values_allowed -- create a warning instead of an error if True
    """
    return value_cond(
        option_name,
        lambda value: not is_empty_string(value),
        value_type_or_enum,
        option_name_for_report=option_name_for_report,
        code_to_allow_extra_values=code_to_allow_extra_values,
        extra_values_allowed=extra_values_allowed,
    )

class ValuePortNumber(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not a TCP or UDP port number
    """
    def _is_valid(self, value):
        return is_port_number(value)

    def _get_allowed_values(self):
        return "a port number (1..65535)"

def value_port_number(
    option_name, option_name_for_report=None,
    code_to_allow_extra_values=None, extra_values_allowed=False
):
    # TODO remove
    """
    Get a validator reporting INVALID_OPTION_VALUE when the value is not a TCP
    or UDP port number

    string option_name -- name of the option to check
    string option_name_for_report -- substitued by the option_name if not set
    string code_to_allow_extra_values -- create a report forceable by this code
    bool extra_values_allowed -- create a warning instead of an error if True
    """
    return value_cond(
        option_name,
        is_port_number,
        "a port number (1-65535)",
        option_name_for_report=option_name_for_report,
        code_to_allow_extra_values=code_to_allow_extra_values,
        extra_values_allowed=extra_values_allowed,
    )

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

def value_port_range(
    option_name, option_name_for_report=None,
    code_to_allow_extra_values=None, extra_values_allowed=False
):
    # TODO remove
    """
    Get a validator reporting INVALID_OPTION_VALUE when the value is not a TCP
    or UDP port range

    string option_name -- name of the option to check
    string option_name_for_report -- substitued by the option_name if not set
    string code_to_allow_extra_values -- create a report forceable by this code
    bool extra_values_allowed -- create a warning instead of an error if True
    """
    return value_cond(
        option_name,
        lambda value: (
            matches_regexp(value, "^[0-9]+-[0-9]+$")
            and
            all([is_port_number(part) for part in value.split("-", 1)])
        ),
        "port-port",
        option_name_for_report=option_name_for_report,
        code_to_allow_extra_values=code_to_allow_extra_values,
        extra_values_allowed=extra_values_allowed,
    )

class ValuePositiveInteger(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not an integer greater than 0
    """
    def _is_valid(self, value):
        return is_integer(value, 1)

    def _get_allowed_values(self):
        return "a positive integer"

def value_positive_integer(
    option_name, option_name_for_report=None,
    code_to_allow_extra_values=None, extra_values_allowed=False
):
    # TODO remove
    """
    Get a validator reporting INVALID_OPTION_VALUE when the value is not
    an integer greater than zero

    string option_name -- name of the option to check
    string option_name_for_report -- substitued by the option_name if not set
    string code_to_allow_extra_values -- create a report forceable by this code
    bool extra_values_allowed -- create a warning instead of an error if True
    """
    return value_cond(
        option_name,
        lambda value: is_integer(value, 1),
        "a positive integer",
        option_name_for_report=option_name_for_report,
        code_to_allow_extra_values=code_to_allow_extra_values,
        extra_values_allowed=extra_values_allowed,
    )

class ValueTimeInterval(ValuePredicateBase):
    """
    Report INVALID_OPTION_VALUE when the value is not a time interval
    """
    def _is_valid(self, value):
        return timeout_to_seconds(value) is not None

    def _get_allowed_values(self):
        return "time interval (e.g. 1, 2s, 3m, 4h, ...)"

def value_time_interval(option_name, option_name_for_report=None):
    # TODO remove
    return value_cond(
        option_name,
        lambda normalized_value:
            timeout_to_seconds(normalized_value) is not None
        ,
        "time interval (e.g. 1, 2s, 3m, 4h, ...)",
        option_name_for_report=option_name_for_report,
    )

def value_empty_or_valid(option_name, validator):
    # TODO remove
    """
    Get a validator running the specified validator if the value is not empty

    string option_name -- name of the option to check
    function validator -- validator to run when the value is not an empty string
    """
    @_if_option_exists(option_name)
    def validate(option_dict):
        value = ValuePair.get(option_dict[option_name])
        return (
            [] if is_empty_string(value.normalized)
            else validator(option_dict)
        )
    return validate

### predicates

def run_collection_of_option_validators(option_dict, validator_list):
    # TODO remove
    """
    Return a list with reports (ReportItems) about problems inside items of
    option_dict.

    dict option_dict is source of values to validate according to specification
    list validator_list contains callables that takes option_dict and returns
        list of reports
    """
    report_list = []
    for validate in validator_list:
        report_list.extend(validate(option_dict))
    return report_list

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
    except ValueError:
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
    except ValueError:
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

def allow_extra_values(code_to_allow, allow):
    # TODO remove
    """
    A usefull shortcut for calling validators

    string code_to_allow -- code to force an error
    bool allow -- make extra values emit a warning
    """
    return {
        "code_to_allow_extra_values": code_to_allow,
        "extra_values_allowed": allow,
    }

def allow_extra_names(code_to_allow, allow):
    # TODO remove
    """
    A usefull shortcut for calling validators

    string code_to_allow -- code to force an error
    bool allow -- make extra names emit a warning
    """
    return {
        "code_to_allow_extra_names": code_to_allow,
        "extra_names_allowed": allow,
    }

def wrap_with_empty_or_valid(validators_dict, wrap=True):
    # TODO remove
    """
    Turn a dict of validators to a list, wrapping them with value_empty_or_valid

    dict validators_dict -- key: option name, value: option validator
    bool wrap -- set to False to get the original validators
    """
    if not wrap:
        # return a list so we can call its append / extend methods
        return list(validators_dict.values())
    return [
        value_empty_or_valid(option_name, validator)
        for option_name, validator in validators_dict.items()
    ]

def _if_option_exists(option_name):
    # TODO remove
    def params_wrapper(validate_func):
        def prepare(option_dict):
            if option_name not in option_dict:
                return []
            return validate_func(option_dict)
        return prepare
    return params_wrapper
