from pcs.common.reports import (
    ReportProcessor,
    ReportItemSeverity,
)
from pcs.common.reports import codes as report_codes
from pcs.lib import reports, sbd
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.communication import (
    qdevice as qdevice_com,
    qdevice_net as qdevice_net_com,
)
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.corosync import (
    config_validators as corosync_conf_validators,
    live as corosync_live,
    qdevice_net,
    qdevice_client
)
from pcs.lib.node import get_existing_nodes_names


def get_config(lib_env):
    """
    Extract and return quorum configuration from corosync.conf
    lib_env LibraryEnvironment
    """
    cfg = lib_env.get_corosync_conf()
    device = None
    if cfg.has_quorum_device():
        model, model_options, generic_options, heuristics_options = (
            cfg.get_quorum_device_settings()
        )
        device = {
            "model": model,
            "model_options": model_options,
            "generic_options": generic_options,
            "heuristics_options": heuristics_options,
        }
    return {
        "options": cfg.get_quorum_options(),
        "device": device,
    }


def _check_if_atb_can_be_disabled(
    runner,
    report_processor: ReportProcessor,
    corosync_conf,
    was_enabled,
    force=False,
):
    """
    Check whenever auto_tie_breaker can be changed without affecting SBD.
    Raises LibraryError if change of ATB will affect SBD functionality.

    runner -- CommandRunner
    report_processor -- report processor
    corosync_conf -- corosync conf facade
    was_enabled -- True if ATB was enabled, False otherwise
    force -- force change
    """
    if (
        was_enabled
        and
        not corosync_conf.is_enabled_auto_tie_breaker()
        and
        sbd.is_auto_tie_breaker_needed(runner, corosync_conf)
    ):
        report_processor.report(
            reports.corosync_quorum_atb_cannot_be_disabled_due_to_sbd(
                ReportItemSeverity.WARNING if force
                    else ReportItemSeverity.ERROR
                ,
                None if force else report_codes.FORCE_OPTIONS
        ))
        if report_processor.has_errors:
            raise LibraryError()


def set_options(
    lib_env: LibraryEnvironment,
    options,
    skip_offline_nodes=False,
    force=False,
):
    """
    Set corosync quorum options, distribute and reload corosync.conf if live

    LibraryEnvironment lib_env
    dict options -- quorum options
    bool skip_offline_nodes -- continue even if not all nodes are accessible
    bool force -- force changes
    """
    cfg = lib_env.get_corosync_conf()
    if lib_env.report_processor.report_list(
        corosync_conf_validators.update_quorum_options(
            options,
            cfg.has_quorum_device(),
            cfg.get_quorum_options()
        )
    ).has_errors:
        raise LibraryError()
    cfg.set_quorum_options(options)
    if lib_env.is_corosync_conf_live:
        _check_if_atb_can_be_disabled(
            lib_env.cmd_runner(),
            lib_env.report_processor,
            cfg,
            cfg.is_enabled_auto_tie_breaker(),
            force
        )
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)

def status_text(lib_env):
    """
    Get quorum runtime status in plain text
    """
    try:
        return corosync_live.get_quorum_status_text(lib_env.cmd_runner())
    except corosync_live.QuorumStatusReadException as e:
        raise LibraryError(reports.corosync_quorum_get_status_error(e.reason))

def status_device_text(lib_env, verbose=False):
    """
    Get quorum device client runtime status in plain text
    bool verbose get more detailed output
    """
    return qdevice_client.get_status_text(lib_env.cmd_runner(), verbose)

def add_device(
    lib_env: LibraryEnvironment, model, model_options, generic_options,
    heuristics_options, force_model=False, force_options=False,
    skip_offline_nodes=False,
):
    # pylint: disable=too-many-locals
    """
    Add a quorum device to a cluster, distribute and reload configs if live

    string model -- quorum device model
    dict model_options -- model specific options
    dict generic_options -- generic quorum device options
    dict heuristics_options -- heuristics options
    bool force_model -- continue even if the model is not valid
    bool force_options -- continue even if options are not valid
    bool skip_offline_nodes -- continue even if not all nodes are accessible
    """
    cfg = lib_env.get_corosync_conf()
    if cfg.has_quorum_device():
        raise LibraryError(reports.qdevice_already_defined())

    report_processor = lib_env.report_processor
    report_processor.report_list(
        corosync_conf_validators.add_quorum_device(
            model,
            model_options,
            generic_options,
            heuristics_options,
            [node.nodeid for node in cfg.get_nodes()],
            force_model=force_model,
            force_options=force_options
        )
    )

    if lib_env.is_corosync_conf_live:
        cluster_nodes_names, report_list = get_existing_nodes_names(
            cfg,
            # Pcs is unable to communicate with nodes missing names. It cannot
            # send new corosync.conf to them. That might break the cluster.
            # Hence we error out.
            error_on_missing_name=True
        )
        report_processor.report_list(report_list)

    if report_processor.has_errors:
        raise LibraryError()

    cfg.add_quorum_device(
        model,
        model_options,
        generic_options,
        heuristics_options,
    )
    if cfg.is_quorum_device_heuristics_enabled_with_no_exec():
        lib_env.report_processor.report(
            reports.corosync_quorum_heuristics_enabled_with_no_exec()
        )

    # First setup certificates for qdevice, then send corosync.conf to nodes.
    # If anything fails, nodes will not have corosync.conf with qdevice in it,
    # so there is no effect on the cluster.
    if lib_env.is_corosync_conf_live:
        target_factory = lib_env.get_node_target_factory()
        target_list = target_factory.get_target_list(
            cluster_nodes_names, skip_non_existing=skip_offline_nodes,
        )
        # Do model specific configuration.
        # If the model is not known to pcs and was forced, do not configure
        # anything else than corosync.conf, as we do not know what to do
        # anyway.
        if model == "net":
            qdevice_net.set_up_client_certificates(
                lib_env.cmd_runner(),
                lib_env.report_processor,
                lib_env.communicator_factory,
                # We are sure the "host" key is there, it has been validated
                # above.
                target_factory.get_target_from_hostname(model_options["host"]),
                cfg.get_cluster_name(),
                target_list,
                skip_offline_nodes
            )

        lib_env.report_processor.report(
            reports.service_enable_started("corosync-qdevice")
        )
        com_cmd = qdevice_com.Enable(
            lib_env.report_processor, skip_offline_nodes
        )
        com_cmd.set_targets(target_list)
        run_and_raise(lib_env.get_node_communicator(), com_cmd)

    # everything set up, it's safe to tell the nodes to use qdevice
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)

    # Now, when corosync.conf has been reloaded, we can start qdevice service.
    if lib_env.is_corosync_conf_live:
        lib_env.report_processor.report(
            reports.service_start_started("corosync-qdevice")
        )
        com_cmd_start = qdevice_com.Start(
            lib_env.report_processor, skip_offline_nodes
        )
        com_cmd_start.set_targets(target_list)
        run_and_raise(lib_env.get_node_communicator(), com_cmd_start)

def update_device(
    lib_env: LibraryEnvironment,
    model_options,
    generic_options,
    heuristics_options,
    force_options=False,
    skip_offline_nodes=False,
):
    """
    Change quorum device settings, distribute and reload configs if live

    dict model_options -- model specific options
    dict generic_options -- generic quorum device options
    dict heuristics_options -- heuristics options
    bool force_options -- continue even if options are not valid
    bool skip_offline_nodes -- continue even if not all nodes are accessible
    """
    cfg = lib_env.get_corosync_conf()
    if not cfg.has_quorum_device():
        raise LibraryError(reports.qdevice_not_defined())
    if lib_env.report_processor.report_list(
        corosync_conf_validators.update_quorum_device(
            cfg.get_quorum_device_model(),
            model_options,
            generic_options,
            heuristics_options,
            [node.nodeid for node in cfg.get_nodes()],
            force_options=force_options
        )
    ).has_errors:
        raise LibraryError()
    cfg.update_quorum_device(
        model_options,
        generic_options,
        heuristics_options
    )
    if cfg.is_quorum_device_heuristics_enabled_with_no_exec():
        lib_env.report_processor.report(
            reports.corosync_quorum_heuristics_enabled_with_no_exec()
        )
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)

def remove_device_heuristics(lib_env, skip_offline_nodes=False):
    """
    Stop using quorum device heuristics, distribute and reload configs if live

    bool skip_offline_nodes -- continue even if not all nodes are accessible
    """
    cfg = lib_env.get_corosync_conf()
    if not cfg.has_quorum_device():
        raise LibraryError(reports.qdevice_not_defined())
    cfg.remove_quorum_device_heuristics()
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)

def remove_device(lib_env: LibraryEnvironment, skip_offline_nodes=False):
    """
    Stop using quorum device, distribute and reload configs if live
    skip_offline_nodes continue even if not all nodes are accessible
    """
    cfg = lib_env.get_corosync_conf()
    if not cfg.has_quorum_device():
        raise LibraryError(reports.qdevice_not_defined())
    model = cfg.get_quorum_device_model()
    cfg.remove_quorum_device()

    if lib_env.is_corosync_conf_live:
        report_processor = lib_env.report_processor
        # get nodes for communication
        cluster_nodes_names, report_list = get_existing_nodes_names(
            cfg,
            # Pcs is unable to communicate with nodes missing names. It cannot
            # send new corosync.conf to them. That might break the cluster.
            # Hence we error out.
            error_on_missing_name=True
        )
        if report_processor.report_list(report_list).has_errors:
            raise LibraryError()
        target_list = lib_env.get_node_target_factory().get_target_list(
            cluster_nodes_names, skip_non_existing=skip_offline_nodes,
        )
        # fix quorum options for SBD to work properly
        if sbd.atb_has_to_be_enabled(lib_env.cmd_runner(), cfg):
            lib_env.report_processor.report(
                reports.corosync_quorum_atb_will_be_enabled_due_to_sbd()
            )
            cfg.set_quorum_options({"auto_tie_breaker": "1"})

        # disable qdevice
        lib_env.report_processor.report(
            reports.service_disable_started("corosync-qdevice")
        )
        com_cmd_disable = qdevice_com.Disable(
            lib_env.report_processor, skip_offline_nodes
        )
        com_cmd_disable.set_targets(target_list)
        run_and_raise(lib_env.get_node_communicator(), com_cmd_disable)
        # stop qdevice
        lib_env.report_processor.report(
            reports.service_stop_started("corosync-qdevice")
        )
        com_cmd_stop = qdevice_com.Stop(
            lib_env.report_processor, skip_offline_nodes
        )
        com_cmd_stop.set_targets(target_list)
        run_and_raise(lib_env.get_node_communicator(), com_cmd_stop)
        # handle model specific configuration
        if model == "net":
            lib_env.report_processor.report(
                reports.qdevice_certificate_removal_started()
            )
            com_cmd_client_destroy = qdevice_net_com.ClientDestroy(
                lib_env.report_processor, skip_offline_nodes
            )
            com_cmd_client_destroy.set_targets(target_list)
            run_and_raise(
                lib_env.get_node_communicator(), com_cmd_client_destroy
            )

    lib_env.push_corosync_conf(cfg, skip_offline_nodes)

def set_expected_votes_live(lib_env, expected_votes):
    """
    set expected votes in live cluster to specified value
    numeric expected_votes desired value of expected votes
    """
    try:
        votes_int = int(expected_votes)
        if votes_int < 1:
            raise ValueError()
    except ValueError:
        raise LibraryError(reports.invalid_option_value(
            "expected votes",
            expected_votes,
            "positive integer"
        ))

    corosync_live.set_expected_votes(lib_env.cmd_runner(), votes_int)
