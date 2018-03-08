from pcs.common import report_codes
from pcs.lib import reports, validate
from pcs.lib.corosync import constants
from pcs.lib.errors import ReportItemSeverity

_QDEVICE_NET_REQUIRED_OPTIONS = (
    "algorithm",
    "host",
)
_QDEVICE_NET_OPTIONAL_OPTIONS = (
    "connect_timeout",
    "force_ip_version",
    "port",
    "tie_breaker",
)


def create(cluster_name, nodes, transport):
    report_items = []
    return report_items

def create_link_list(transport, link_list):
    report_items = []
    return report_items

def create_transport_udp(options):
    report_items = []
    return report_items

def create_transport_knet(generic_options, compression_options, crypto_options):
    report_items = []
    return report_items

def create_totem(options):
    report_items = []
    return report_items

def create_quorum(options):
    report_items = []
    return report_items

def update_quorum_options(options, has_qdevice):
    """
    Validate modifying quorum options, return list of report items

    dict options -- quorum options to set
    bool has_qdevice -- is a qdevice set in corosync.conf?
    """
    allowed_bool = ("0", "1")
    report_items = []
    validators = [
        validate.value_empty_or_valid(
            "auto_tie_breaker",
            validate.value_in(
                "auto_tie_breaker",
                allowed_bool
            )
        ),
        validate.value_empty_or_valid(
            "last_man_standing",
            validate.value_in(
                "last_man_standing",
                allowed_bool
            )
        ),
        validate.value_empty_or_valid(
            "last_man_standing_window",
            validate.value_positive_integer(
                "last_man_standing_window"
            )
        ),
        validate.value_empty_or_valid(
            "wait_for_all",
            validate.value_in(
                "wait_for_all",
                allowed_bool
            )
        ),
    ]
    report_items = (
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in(
            constants.QUORUM_OPTIONS,
            options.keys(),
            "quorum",
        )
    )
    if has_qdevice:
        qdevice_incompatible_options = [
            name for name in options
            if name in constants.QUORUM_OPTIONS_INCOMPATIBLE_WITH_QDEVICE
        ]
        if qdevice_incompatible_options:
            report_items.append(
                reports.corosync_options_incompatible_with_qdevice(
                    qdevice_incompatible_options
                )
            )
    return report_items

def add_quorum_device(
    model, model_options, generic_options, heuristics_options, node_ids,
    force_model=False, force_options=False
):
    """
    Validate adding a quorum device

    string model -- quorum device model
    dict model_options -- model specific options
    dict generic_options -- generic quorum device options
    dict heuristics_options -- heuristics options
    list node_ids -- list of existing node ids
    bool force_model -- continue even if the model is not valid
    bool force_options -- turn forceable errors into warnings
    """
    report_items = []

    model_validators = {
        "net": lambda: _qdevice_add_model_net_options(
            model_options,
            node_ids,
            force_options
        ),
    }
    if model in model_validators:
        report_items += model_validators[model]()
    else:
        report_items += validate.run_collection_of_option_validators(
            {"model": model},
            [
                validate.value_in(
                    "model",
                    list(model_validators.keys()),
                    **validate.allow_extra_values(
                        report_codes.FORCE_QDEVICE_MODEL, force_model
                    )
                )
            ]
        )
    return (
        report_items
        +
        _qdevice_add_generic_options(generic_options, force_options)
        +
        _qdevice_add_heuristics_options(heuristics_options, force_options)
    )

def update_quorum_device(
    model, model_options, generic_options, heuristics_options, node_ids,
    force_options=False
):
    """
    Validate updating a quorum device

    string model -- quorum device model
    dict model_options -- model specific options
    dict generic_options -- generic quorum device options
    dict heuristics_options -- heuristics options
    list node_ids -- list of existing node ids
    bool force_options -- turn forceable errors into warnings
    """
    report_items = []

    model_validators = {
        "net": lambda: _qdevice_update_model_net_options(
            model_options,
            node_ids,
            force_options
        ),
    }
    if model in model_validators:
        report_items += model_validators[model]()
    return (
        report_items
        +
        _qdevice_update_generic_options(generic_options, force_options)
        +
        _qdevice_update_heuristics_options(
            heuristics_options,
            force_options
        )
    )

def _qdevice_add_generic_options(options, force_options=False):
    """
    Validate quorum device generic options when adding a quorum device

    dict options -- generic options
    bool force_options -- turn forceable errors into warnings
    """
    validators = _get_qdevice_generic_options_validators(
        force_options=force_options
    )
    report_items = validate.run_collection_of_option_validators(
        options,
        validators
    )
    report_items.extend(
        _validate_qdevice_generic_options_names(
            options,
            force_options=force_options
        )
    )
    return report_items

def _qdevice_update_generic_options(options, force_options=False):
    """
    Validate quorum device generic options when updating a quorum device

    dict options -- generic options
    bool force_options -- turn forceable errors into warnings
    """
    validators = _get_qdevice_generic_options_validators(
        allow_empty_values=True,
        force_options=force_options
    )
    report_items = validate.run_collection_of_option_validators(
        options,
        validators
    )
    report_items.extend(
        _validate_qdevice_generic_options_names(
            options,
            force_options=force_options
        )
    )
    return report_items

def _qdevice_add_heuristics_options(options, force_options=False):
    """
    Validate quorum device heuristics options when adding a quorum device

    dict options -- heuristics options
    bool force_options -- turn forceable errors into warnings
    """
    options_nonexec, options_exec = _split_heuristics_exec_options(options)
    validators = _get_qdevice_heuristics_options_validators(
        force_options=force_options
    )
    exec_options_reports, valid_exec_options = (
        _validate_heuristics_exec_option_names(options_exec)
    )
    for option in valid_exec_options:
        validators.append(
            validate.value_not_empty(option, "a command to be run")
        )
    return (
        validate.run_collection_of_option_validators(options, validators)
        +
        _validate_heuristics_noexec_option_names(
            options_nonexec,
            force_options=force_options
        )
        +
        exec_options_reports
    )

def _qdevice_update_heuristics_options(options, force_options=False):
    """
    Validate quorum device heuristics options when updating a quorum device

    dict options -- heuristics options
    bool force_options -- turn forceable errors into warnings
    """
    options_nonexec, options_exec = _split_heuristics_exec_options(options)
    validators = _get_qdevice_heuristics_options_validators(
        allow_empty_values=True,
        force_options=force_options
    )
    # No validation necessary for values of valid exec options - they are
    # either empty (meaning they will be removed) or nonempty strings.
    exec_options_reports, dummy_valid_exec_options = (
        _validate_heuristics_exec_option_names(options_exec)
    )
    return (
        validate.run_collection_of_option_validators(options, validators)
        +
        _validate_heuristics_noexec_option_names(
            options_nonexec,
            force_options=force_options
        )
        +
        exec_options_reports
    )

def _qdevice_add_model_net_options(options, node_ids, force_options=False):
    """
    Validate quorum device model options when adding a quorum device

    dict options -- model options
    list node_ids -- list of existing node ids
    bool force_options -- turn forceable errors into warnings
    """
    allowed_options = (
        _QDEVICE_NET_REQUIRED_OPTIONS + _QDEVICE_NET_OPTIONAL_OPTIONS
    )
    option_type = "quorum device model"
    validators = (
        [
            validate.is_required(option_name, option_type)
            for option_name in _QDEVICE_NET_REQUIRED_OPTIONS
        ]
        +
        _get_qdevice_model_net_options_validators(
            node_ids,
            force_options=force_options
        )
    )
    return (
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in(
            allowed_options,
            options.keys(),
            option_type,
            **validate.allow_extra_names(
                report_codes.FORCE_OPTIONS, force_options
            )
        )
    )

def _qdevice_update_model_net_options(options, node_ids, force_options=False):
    """
    Validate quorum device model options when updating a quorum device

    dict options -- model options
    list node_ids -- list of existing node ids
    bool force_options -- turn forceable errors into warnings
    """
    allowed_options = (
        _QDEVICE_NET_REQUIRED_OPTIONS + _QDEVICE_NET_OPTIONAL_OPTIONS
    )
    option_type = "quorum device model"
    validators = _get_qdevice_model_net_options_validators(
        node_ids,
        allow_empty_values=True,
        force_options=force_options
    )
    return (
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in(
            allowed_options,
            options.keys(),
            option_type,
            **validate.allow_extra_names(
                report_codes.FORCE_OPTIONS, force_options
            )
        )
    )

def _get_qdevice_generic_options_validators(
    allow_empty_values=False, force_options=False
):
    allow_extra_values = validate.allow_extra_values(
        report_codes.FORCE_OPTIONS, force_options
    )
    validators = {
        "sync_timeout": validate.value_positive_integer(
            "sync_timeout",
            **allow_extra_values
        ),
        "timeout": validate.value_positive_integer(
            "timeout",
            **allow_extra_values
        ),
    }
    if not allow_empty_values:
        # make sure to return a list even in python3 so we can call append
        # on it
        return list(validators.values())
    return [
        validate.value_empty_or_valid(option_name, validator)
        for option_name, validator in validators.items()
    ]

def _validate_qdevice_generic_options_names(options, force_options=False):
    option_type = "quorum device"
    allowed_options = [
        "sync_timeout",
        "timeout",
    ]
    report_items = []
    # In corosync.conf, generic options contain the "model" option. We treat
    # that option separately in pcs so we must not allow it to be passed in
    # generic options. That's why a standard validate.names_in cannot be used
    # in here.
    model_found = False
    invalid_options = []
    for name in options:
        if name not in allowed_options:
            if name == "model":
                model_found = True
            else:
                invalid_options.append(name)
    if model_found:
        report_items.append(
            reports.invalid_options(
                ["model"],
                allowed_options,
                option_type,
            )
        )
    if invalid_options:
        report_items.append(
            reports.invalid_options(
                invalid_options,
                allowed_options,
                option_type,
                severity=(
                    ReportItemSeverity.WARNING if force_options
                    else ReportItemSeverity.ERROR
                ),
                forceable=(
                    None if force_options else report_codes.FORCE_OPTIONS
                )
            )
        )
    return report_items

def _split_heuristics_exec_options(options):
    options_exec = dict()
    options_nonexec = dict()
    for name, value in options.items():
        if name.startswith("exec_"):
            options_exec[name] = value
        else:
            options_nonexec[name] = value
    return options_nonexec, options_exec

def _get_qdevice_heuristics_options_validators(
    allow_empty_values=False, force_options=False
):
    allow_extra_values = validate.allow_extra_values(
        report_codes.FORCE_OPTIONS, force_options
    )
    validators = {
        "mode": validate.value_in(
            "mode",
            ("off", "on", "sync"),
            **allow_extra_values
        ),
        "interval": validate.value_positive_integer(
            "interval",
            **allow_extra_values
        ),
        "sync_timeout": validate.value_positive_integer(
            "sync_timeout",
            **allow_extra_values
        ),
        "timeout": validate.value_positive_integer(
            "timeout",
            **allow_extra_values
        ),
    }
    if not allow_empty_values:
        # make sure to return a list even in python3 so we can call append
        # on it
        return list(validators.values())
    return [
        validate.value_empty_or_valid(option_name, validator)
        for option_name, validator in validators.items()
    ]

def _validate_heuristics_exec_option_names(options_exec):
    # We must be strict and do not allow to override this validation,
    # otherwise setting a cratfed exec_NAME could be misused for setting
    # arbitrary corosync.conf settings.
    regexp = constants.QUORUM_DEVICE_HEURISTICS_EXEC_NAME_RE
    report_list = []
    valid_options = []
    not_valid_options = []
    for name in options_exec:
        if regexp.match(name) is None:
            not_valid_options.append(name)
        else:
            valid_options.append(name)
    if not_valid_options:
        report_list.append(
            reports.invalid_userdefined_options(
                not_valid_options,
                "exec_NAME cannot contain '.:{}#' and whitespace characters",
                "heuristics",
                severity=ReportItemSeverity.ERROR,
                forceable=None
            )
        )
    return report_list, valid_options

def _validate_heuristics_noexec_option_names(
    options_nonexec, force_options=False
):
    allowed_options = [
        "interval",
        "mode",
        "sync_timeout",
        "timeout",
    ]
    return validate.names_in(
        allowed_options,
        options_nonexec.keys(),
        "heuristics",
        report_codes.FORCE_OPTIONS,
        allow_extra_names=force_options,
        allowed_option_patterns=["exec_NAME"]
    )

def _get_qdevice_model_net_options_validators(
    node_ids, allow_empty_values=False, force_options=False
):
    allow_extra_values = validate.allow_extra_values(
        report_codes.FORCE_OPTIONS, force_options
    )
    validators = {
        "connect_timeout": validate.value_integer_in_range(
            "connect_timeout",
            1000,
            2*60*1000,
            **allow_extra_values
        ),
        "force_ip_version": validate.value_in(
            "force_ip_version",
            ("0", "4", "6"),
            **allow_extra_values
        ),
        "port": validate.value_port_number(
            "port",
            **allow_extra_values
        ),
        "tie_breaker": validate.value_in(
            "tie_breaker",
            ["lowest", "highest"] + node_ids,
            **allow_extra_values
        ),
    }
    if not allow_empty_values:
        return (
            [
                validate.value_not_empty("host", "a qdevice host address"),
                _validate_qdevice_net_algorithm(**allow_extra_values)
            ]
            +
            # explicitely convert to a list for python 3
            list(validators.values())
        )
    return (
        [
            validate.value_not_empty("host", "a qdevice host address"),
            _validate_qdevice_net_algorithm(**allow_extra_values)
        ]
        +
        [
            validate.value_empty_or_valid(option_name, validator)
            for option_name, validator in validators.items()
        ]
    )

def _validate_qdevice_net_algorithm(
    code_to_allow_extra_values=None, allow_extra_values=False
):
    @validate._if_option_exists("algorithm")
    def validate_func(option_dict):
        allowed_algorithms = (
            "ffsplit",
            "lms",
        )
        value = validate.ValuePair.get(option_dict["algorithm"])
        if validate.is_empty_string(value.normalized):
            return [
                reports.invalid_option_value(
                    "algorithm",
                    value.original,
                    allowed_algorithms
                )
            ]
        return validate.value_in(
            "algorithm",
            allowed_algorithms,
            code_to_allow_extra_values=code_to_allow_extra_values,
            allow_extra_values=allow_extra_values
        )(option_dict)
    return validate_func
