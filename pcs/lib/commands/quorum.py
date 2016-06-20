from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib import reports
from pcs.lib.errors import LibraryError
from pcs.lib.corosync import qdevice_net, qdevice_client
from pcs.lib.external import (
    NodeCommunicationException,
    node_communicator_exception_to_report_item,
    parallel_nodes_communication_helper,
)


def get_config(lib_env):
    """
    Extract and return quorum configuration from corosync.conf
    lib_env LibraryEnvironment
    """
    __ensure_not_cman(lib_env)
    cfg = lib_env.get_corosync_conf()
    device = None
    if cfg.has_quorum_device():
        model, model_options, generic_options = cfg.get_quorum_device_settings()
        device = {
            "model": model,
            "model_options": model_options,
            "generic_options": generic_options,
        }
    return {
        "options": cfg.get_quorum_options(),
        "device": device,
    }

def set_options(lib_env, options, skip_offline_nodes=False):
    """
    Set corosync quorum options, distribute and reload corosync.conf if live
    lib_env LibraryEnvironment
    options quorum options (dict)
    skip_offline_nodes continue even if not all nodes are accessible
    """
    __ensure_not_cman(lib_env)
    cfg = lib_env.get_corosync_conf()
    cfg.set_quorum_options(lib_env.report_processor, options)
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)

def add_device(
    lib_env, model, model_options, generic_options, force_model=False,
    force_options=False, skip_offline_nodes=False
):
    """
    Add quorum device to cluster, distribute and reload configs if live
    model quorum device model
    model_options model specific options dict
    generic_options generic quorum device options dict
    force_model continue even if the model is not valid
    force_options continue even if options are not valid
    skip_offline_nodes continue even if not all nodes are accessible
    """
    __ensure_not_cman(lib_env)

    cfg = lib_env.get_corosync_conf()
    # Try adding qdevice to corosync.conf. This validates all the options and
    # makes sure qdevice is not defined in corosync.conf yet.
    cfg.add_quorum_device(
        lib_env.report_processor,
        model,
        model_options,
        generic_options,
        force_model,
        force_options
    )

    # First setup certificates for qdevice, then send corosync.conf to nodes.
    # If anything fails, nodes will not have corosync.conf with qdevice in it,
    # so there is no effect on the cluster.
    if lib_env.is_corosync_conf_live:
        # do model specific configuration
        # if model is not known to pcs and was forced, do not configure antyhing
        # else but corosync.conf, as we do not know what to do anyways
        if model == "net":
            _add_device_model_net(
                lib_env,
                # we are sure it's there, it was validated in add_quorum_device
                model_options["host"],
                cfg.get_cluster_name(),
                cfg.get_nodes(),
                skip_offline_nodes
            )

        # Since cluster is not running, we do not start qdevice service. We know
        # it isn't running because qdevice cannot be added to a running cluster,
        # and that is ensured by cfg.need_stopped_cluster and
        # lib_env.push_corosync_conf.
        lib_env.report_processor.process(
            reports.service_enable_started("corosync-qdevice")
        )
        communicator = lib_env.node_communicator()
        parallel_nodes_communication_helper(
            qdevice_client.remote_client_enable,
            [
                [(lib_env.report_processor, communicator, node), {}]
                for node in cfg.get_nodes()
            ],
            lib_env.report_processor,
            skip_offline_nodes
        )

    # everything set up, it's safe to tell the nodes to use qdevice
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)

def _add_device_model_net(
    lib_env, qnetd_host, cluster_name, cluster_nodes, skip_offline_nodes
):
    """
    setup cluster nodes for using qdevice model net
    string qnetd_host address of qdevice provider (qnetd host)
    string cluster_name name of the cluster to which qdevice is being added
    NodeAddressesList cluster_nodes list of cluster nodes addresses
    bool skip_offline_nodes continue even if not all nodes are accessible
    """
    communicator = lib_env.node_communicator()
    runner = lib_env.cmd_runner()
    reporter = lib_env.report_processor

    reporter.process(
        reports.qdevice_certificate_distribution_started()
    )
    # get qnetd CA certificate
    try:
        qnetd_ca_cert = qdevice_net.remote_qdevice_get_ca_certificate(
            communicator,
            qnetd_host
        )
    except NodeCommunicationException as e:
        raise LibraryError(
            node_communicator_exception_to_report_item(e)
        )
    # init certificate storage on all nodes
    parallel_nodes_communication_helper(
        qdevice_net.remote_client_setup,
        [
            ((communicator, node, qnetd_ca_cert), {})
            for node in cluster_nodes
        ],
        reporter,
        skip_offline_nodes
    )
    # create client certificate request
    cert_request = qdevice_net.client_generate_certificate_request(
        runner,
        cluster_name
    )
    # sign the request on qnetd host
    try:
        signed_certificate = qdevice_net.remote_sign_certificate_request(
            communicator,
            qnetd_host,
            cert_request,
            cluster_name
        )
    except NodeCommunicationException as e:
        raise LibraryError(
            node_communicator_exception_to_report_item(e)
        )
    # transform the signed certificate to pk12 format which can sent to nodes
    pk12 = qdevice_net.client_cert_request_to_pk12(runner, signed_certificate)
    # distribute final certificate to nodes
    def do_and_report(reporter, communicator, node, pk12):
        qdevice_net.remote_client_import_certificate_and_key(
            communicator, node, pk12
        )
        reporter.process(
            reports.qdevice_certificate_accepted_by_node(node.label)
        )
    parallel_nodes_communication_helper(
        do_and_report,
        [
            ((reporter, communicator, node, pk12), {})
            for node in cluster_nodes
        ],
        reporter,
        skip_offline_nodes
    )

def update_device(
    lib_env, model_options, generic_options, force_options=False,
    skip_offline_nodes=False
):
    """
    Change quorum device settings, distribute and reload configs if live
    model_options model specific options dict
    generic_options generic quorum device options dict
    force_options continue even if options are not valid
    skip_offline_nodes continue even if not all nodes are accessible
    """
    __ensure_not_cman(lib_env)
    cfg = lib_env.get_corosync_conf()
    cfg.update_quorum_device(
        lib_env.report_processor,
        model_options,
        generic_options,
        force_options
    )
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)

def remove_device(lib_env, skip_offline_nodes=False):
    """
    Stop using quorum device, distribute and reload configs if live
    skip_offline_nodes continue even if not all nodes are accessible
    """
    __ensure_not_cman(lib_env)

    cfg = lib_env.get_corosync_conf()
    model, dummy_options, dummy_options = cfg.get_quorum_device_settings()
    cfg.remove_quorum_device()
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)

    if lib_env.is_corosync_conf_live:
        # handle model specific configuration
        if model == "net":
            _remove_device_model_net(
                lib_env,
                cfg.get_nodes(),
                skip_offline_nodes
            )

        # Since cluster is not running, we do not stop qdevice service. We know
        # it isn't running because qdevice cannot be added to a running cluster,
        # and that is ensured by cfg.need_stopped_cluster and
        # lib_env.push_corosync_conf.
        lib_env.report_processor.process(
            reports.service_disable_started("corosync-qdevice")
        )
        communicator = lib_env.node_communicator()
        parallel_nodes_communication_helper(
            qdevice_client.remote_client_disable,
            [
                [(lib_env.report_processor, communicator, node), {}]
                for node in cfg.get_nodes()
            ],
            lib_env.report_processor,
            skip_offline_nodes
        )

def _remove_device_model_net(lib_env, cluster_nodes, skip_offline_nodes):
    """
    remove configuration used by qdevice model net
    NodeAddressesList cluster_nodes list of cluster nodes addresses
    bool skip_offline_nodes continue even if not all nodes are accessible
    """
    reporter = lib_env.report_processor
    communicator = lib_env.node_communicator()

    reporter.process(
        reports.qdevice_certificate_removal_started()
    )
    def do_and_report(reporter, communicator, node):
        qdevice_net.remote_client_destroy(communicator, node)
        reporter.process(
            reports.qdevice_certificate_removed_from_node(node.label)
        )
    parallel_nodes_communication_helper(
        do_and_report,
        [
            [(reporter, communicator, node), {}]
            for node in cluster_nodes
        ],
        lib_env.report_processor,
        skip_offline_nodes
    )

def __ensure_not_cman(lib_env):
    if lib_env.is_corosync_conf_live and lib_env.is_cman_cluster:
        raise LibraryError(reports.cman_unsupported_command())

