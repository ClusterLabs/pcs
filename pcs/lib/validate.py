"""
Module contains list of functions that should be useful for validation.
Example of use (how things play together):
    >>> option_dict = {"some_option": "A"}
    >>> validators = [
    ...     is_required("name"),
    ...     value_in("some_option", ["B", "C"])
    ... ]
    >>> report_list = run_collection_of_option_validators(
    ...     option_dict,
    ...     validators
    ... )
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

Sometimes we need to validate the normalized value but in report we need the
original value. For this purposes is ValuePair and helpers like values_to_pairs
and pairs_to_values.

TODO provide parameters to provide forceable error/warning for functions that
     does not support it
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from collections import namedtuple
import re

from pcs.common.tools import is_string
from pcs.lib import reports
from pcs.lib.pacemaker.values import validate_id


### normalization

class ValuePair(namedtuple("ValuePair", "original normalized")):
    """
    Storage for the original value and its normalized form
    """

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

### keys validators

def depends_on_option(
    option_name, prerequisite_option, option_type="", prerequisite_type=""
):
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

def is_required(option_name, option_type=""):
    """
    Return a the function that takes option_dict and returns report list
    (with REQUIRED_OPTION_IS_MISSING when option_dict does not contain
    option_name).

    string option_name is name of option of option_dict that will be tested
    string option_type describes type of option for reporting purposes
    """
    def validate(option_dict):
        if option_name not in option_dict:
            return [reports.required_option_is_missing(
                [option_name],
                option_type,
            )]
        return []
    return validate

def is_required_some_of(option_name_list, option_type=""):
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
        if len(found_names) < 1:
            return [reports.required_option_of_alternatives_is_missing(
                sorted(option_name_list),
                option_type,
            )]
        return []
    return validate

def mutually_exclusive(mutually_exclusive_names, option_type="option"):
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

def names_in(
    allowed_name_list, name_list, option_type="option",
    code_to_allow_extra_names=None, allow_extra_names=False
):
    """
    Return a list with report INVALID_OPTION when in name_list is a name that is
    not in allowed_name_list.

    list allowed_name_list contains names which are valid
    list name_list contains names for validation
    string option_type describes type of option for reporting purposes
    string code_to_allow_extra_names is code for forcing invalid names. If it is
        empty report INVALID_OPTION is non-forceable error. If it is not empty
        report INVALID_OPTION is forceable error or warning.
    bool allow_extra_names is flag that complements code_to_allow_extra_names
        and determines wheter is report INVALID_OPTION forceable error or
        warning.
    """
    invalid_names = set(name_list) - set(allowed_name_list)
    if not invalid_names:
        return []

    create_report = reports.get_problem_creator(
        code_to_allow_extra_names,
        allow_extra_names
    )
    return [create_report(
        reports.invalid_option,
        sorted(invalid_names),
        sorted(allowed_name_list),
        option_type,
    )]

### values validators

def value_cond(
    option_name, predicate, value_type_or_enum, option_name_for_report=None,
    code_to_allow_extra_values=None, allow_extra_values=False
):
    """
    Return a validation  function that takes option_dict and returns report list
    (with INVALID_OPTION_VALUE when option_name is not in allowed_values).

    string option_name is name of option of option_dict that will be tested
    function predicate takes one parameter, normalized value
    list or string value_type_or_enum list of possible values or string
        description of value type
    string option_name_for_report is substitued by option name if is None
    string code_to_allow_extra_values is code for forcing invalid names. If it
        is empty report INVALID_OPTION is non-forceable error. If it is not
        empty report INVALID_OPTION is forceable error or warning.
    bool allow_extra_values is flag that complements code_to_allow_extra_values
        and determines wheter is report INVALID_OPTION forceable error or
        warning.
    """
    def validate(option_dict):
        if option_name not in option_dict:
            return []

        value = option_dict[option_name]
        if not isinstance(value, ValuePair):
            value = ValuePair(value, value)

        if not predicate(value.normalized):
            create_report = reports.get_problem_creator(
                code_to_allow_extra_values,
                allow_extra_values
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

def value_empty_or_valid(option_name, validator):
    """
    Get a validator running the specified validator if the value is not empty

    string option_name -- name of the option to check
    function validator -- validator to run when the value is not an empty string
    """
    def validate(option_dict):
        if option_name not in option_dict:
            return []

        value = option_dict[option_name]
        if not isinstance(value, ValuePair):
            value = ValuePair(value, value)

        if is_empty_string(value.normalized):
            return []

        return validator(option_dict)
    return validate

def value_id(option_name, option_name_for_report=None, id_provider=None):
    """
    Get a validator reporting ID errors and optionally booking IDs along the way

    string option_name -- name of the option to check
    string option_name_for_report -- substitued by the option_name if not set
    IdProvider id_provider -- used to check id uniqueness if set
    """
    def validate(option_dict):
        if option_name not in option_dict:
            return []

        value = option_dict[option_name]
        if not isinstance(value, ValuePair):
            value = ValuePair(value, value)

        report_list = []
        validate_id(value.normalized, option_name_for_report, report_list)
        if id_provider is not None and not report_list:
            report_list.extend(
                id_provider.book_ids(value.normalized)
            )
        return report_list
    return validate

def value_in(
    option_name, allowed_values, option_name_for_report=None,
    code_to_allow_extra_values=None, allow_extra_values=False
):
    """
    Special case of value_cond function.returned function checks whenever value
    is included allowed_values. If not list of ReportItem will be returned.

    option_name -- string, name of option to check
    allowed_values -- list of strings, list of possible values
    option_name_for_report -- string, it is substitued by option name if is None
    code_to_allow_extra_values -- string, code for forcing invalid names. If it
        is empty report INVALID_OPTION is non-forceable error. If it is not
        empty report INVALID_OPTION is forceable error or warning.
    allow_extra_values -- bool, flag that complements code_to_allow_extra_values
        and determines wheter is report INVALID_OPTION forceable error or
        warning.
    """
    return value_cond(
        option_name,
        lambda normalized_value: normalized_value in allowed_values,
        allowed_values,
        option_name_for_report=option_name_for_report,
        code_to_allow_extra_values=code_to_allow_extra_values,
        allow_extra_values=allow_extra_values,
    )

def value_nonnegative_integer(
    option_name, option_name_for_report=None,
    code_to_allow_extra_values=None, allow_extra_values=False
):
    """
    Get a validator reporting INVALID_OPTION_VALUE when the value is not
    an integer greater than -1

    string option_name -- name of the option to check
    string option_name_for_report -- substitued by the option_name if not set
    string code_to_allow_extra_values -- create a report forceable by this code
    bool allow_extra_values -- create a warning instead of an error if True
    """
    return value_cond(
        option_name,
        lambda value: is_integer(value, 0),
        "a non-negative integer",
        option_name_for_report=option_name_for_report,
        code_to_allow_extra_values=code_to_allow_extra_values,
        allow_extra_values=allow_extra_values,
    )

def value_not_empty(
    option_name, value_type_or_enum, option_name_for_report=None,
    code_to_allow_extra_values=None, allow_extra_values=False
):
    """
    Get a validator reporting INVALID_OPTION_VALUE when the value is empty

    string option_name -- name of the option to check
    string option_name_for_report -- substitued by the option_name if not set
    string code_to_allow_extra_values -- create a report forceable by this code
    bool allow_extra_values -- create a warning instead of an error if True
    """
    return value_cond(
        option_name,
        lambda value: not is_empty_string(value),
        value_type_or_enum,
        option_name_for_report=option_name_for_report,
        code_to_allow_extra_values=code_to_allow_extra_values,
        allow_extra_values=allow_extra_values,
    )

def value_port_number(
    option_name, option_name_for_report=None,
    code_to_allow_extra_values=None, allow_extra_values=False
):
    """
    Get a validator reporting INVALID_OPTION_VALUE when the value is not a TCP
    or UDP port number

    string option_name -- name of the option to check
    string option_name_for_report -- substitued by the option_name if not set
    string code_to_allow_extra_values -- create a report forceable by this code
    bool allow_extra_values -- create a warning instead of an error if True
    """
    return value_cond(
        option_name,
        is_port_number,
        "a port number (1-65535)",
        option_name_for_report=option_name_for_report,
        code_to_allow_extra_values=code_to_allow_extra_values,
        allow_extra_values=allow_extra_values,
    )

def value_port_range(
    option_name, option_name_for_report=None,
    code_to_allow_extra_values=None, allow_extra_values=False
):
    """
    Get a validator reporting INVALID_OPTION_VALUE when the value is not a TCP
    or UDP port range

    string option_name -- name of the option to check
    string option_name_for_report -- substitued by the option_name if not set
    string code_to_allow_extra_values -- create a report forceable by this code
    bool allow_extra_values -- create a warning instead of an error if True
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
        allow_extra_values=allow_extra_values,
    )

def value_positive_integer(
    option_name, option_name_for_report=None,
    code_to_allow_extra_values=None, allow_extra_values=False
):
    """
    Get a validator reporting INVALID_OPTION_VALUE when the value is not
    an integer greater than zero

    string option_name -- name of the option to check
    string option_name_for_report -- substitued by the option_name if not set
    string code_to_allow_extra_values -- create a report forceable by this code
    bool allow_extra_values -- create a warning instead of an error if True
    """
    return value_cond(
        option_name,
        lambda value: is_integer(value, 1),
        "a positive integer",
        option_name_for_report=option_name_for_report,
        code_to_allow_extra_values=code_to_allow_extra_values,
        allow_extra_values=allow_extra_values,
    )

### tools and predicates

def run_collection_of_option_validators(option_dict, validator_list):
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
    return is_string(value) and not value

def is_integer(value, at_least=None, at_most=None):
    """
    Check if the specified value is an integer, optionally check a range

    mixed value -- string, int or float, value to check
    """
    try:
        if isinstance(value, float):
            return False
        value_int = int(value)
        if at_least is not None and value_int < at_least:
            return False
        if at_most is not None and value_int > at_most:
            return False
    except ValueError:
        return False
    return True

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
