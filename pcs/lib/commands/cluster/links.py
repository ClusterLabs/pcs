from pcs.common import reports
from pcs.common.reports import codes as report_codes
from pcs.common.reports.item import ReportItem
from pcs.lib.cib.resource.guest_node import find_node_list as get_guest_nodes
from pcs.lib.cib.resource.remote_node import find_node_list as get_remote_nodes
from pcs.lib.commands.cluster.common import ensure_live_env
from pcs.lib.corosync import config_validators
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names


def add_link(
    env: LibraryEnvironment,
    node_addr_map,
    link_options=None,
    force_flags: reports.types.ForceFlags = (),
):
    """
    Add a corosync link to a cluster

    env LibraryEnvironment
    dict node_addr_map -- key: node name, value: node address for the link
    dict link_options -- link options
    force_flags list -- list of flags codes
    """
    ensure_live_env(env)  # raises if env is not live

    link_options = link_options or {}
    force = report_codes.FORCE in force_flags
    skip_offline = report_codes.SKIP_OFFLINE_NODES in force_flags

    report_processor = env.report_processor
    corosync_conf = env.get_corosync_conf()

    # validations

    dummy_cluster_nodes_names, nodes_report_list = get_existing_nodes_names(
        corosync_conf,
        # New link addresses are assigned to nodes based on node names. If
        # there are nodes with no names, we cannot assign them new link
        # addresses. This is a no-go situation.
        error_on_missing_name=True,
    )
    report_processor.report_list(nodes_report_list)

    try:
        cib = env.get_cib()
        cib_nodes = get_remote_nodes(cib) + get_guest_nodes(cib)
    except LibraryError:
        cib_nodes = []
        report_processor.report(
            ReportItem(
                reports.item.get_severity(report_codes.FORCE, force),
                reports.messages.CibLoadErrorGetNodesForValidation(),
            )
        )

    report_processor.report_list(
        config_validators.add_link(
            node_addr_map,
            link_options,
            corosync_conf.get_nodes(),
            cib_nodes,
            [str(num) for num in corosync_conf.get_used_linknumber_list()],
            corosync_conf.get_transport(),
            corosync_conf.get_ip_version(),
            force_unresolvable=force,
        )
    )

    if report_processor.has_errors:
        raise LibraryError()

    # validations done

    corosync_conf.add_link(node_addr_map, link_options)
    env.push_corosync_conf(corosync_conf, skip_offline)


def remove_links(
    env: LibraryEnvironment,
    linknumber_list,
    force_flags: reports.types.ForceFlags = (),
):
    """
    Remove corosync links from a cluster

    env LibraryEnvironment
    iterable linknumber_list -- linknumbers (as strings) of links to be removed
    force_flags list -- list of flags codes
    """
    # TODO library interface should make sure linknumber_list is an iterable of
    # strings. The layer in which the check should be done does not exist yet.
    ensure_live_env(env)  # raises if env is not live

    skip_offline = report_codes.SKIP_OFFLINE_NODES in force_flags

    report_processor = env.report_processor
    corosync_conf = env.get_corosync_conf()

    # validations

    report_processor.report_list(
        config_validators.remove_links(
            linknumber_list,
            [str(num) for num in corosync_conf.get_used_linknumber_list()],
            corosync_conf.get_transport(),
        )
    )

    if report_processor.has_errors:
        raise LibraryError()

    # validations done

    corosync_conf.remove_links(linknumber_list)

    env.push_corosync_conf(corosync_conf, skip_offline)


def update_link(
    env: LibraryEnvironment,
    linknumber,
    node_addr_map=None,
    link_options=None,
    force_flags: reports.types.ForceFlags = (),
):
    """
    Change an existing corosync link

    env LibraryEnvironment
    string linknumber -- the link to be changed
    dict node_addr_map -- key: node name, value: node address for the link
    dict link_options -- link options
    force_flags list -- list of flags codes
    """
    ensure_live_env(env)  # raises if env is not live

    node_addr_map = node_addr_map or {}
    link_options = link_options or {}
    force = report_codes.FORCE in force_flags
    skip_offline = report_codes.SKIP_OFFLINE_NODES in force_flags

    report_processor = env.report_processor
    corosync_conf = env.get_corosync_conf()

    # validations

    dummy_cluster_nodes_names, nodes_report_list = get_existing_nodes_names(
        corosync_conf,
        # Pcs is unable to communicate with nodes missing names. It cannot send
        # new corosync.conf to them. That might break the cluster. Hence we
        # error out.
        # This check is done later as well, when sending corosync.conf to
        # nodes. But we need node names to be present so we can set new
        # addresses to them. We may as well do the check right now.
        error_on_missing_name=True,
    )
    report_processor.report_list(nodes_report_list)

    report_processor.report_list(
        config_validators.update_link(
            linknumber,
            node_addr_map,
            link_options,
            corosync_conf.get_links_options().get(linknumber, {}),
            corosync_conf.get_nodes(),
            # cluster must be stopped for updating a link and then we cannot get
            # nodes from CIB
            [],
            [str(num) for num in corosync_conf.get_used_linknumber_list()],
            corosync_conf.get_transport(),
            corosync_conf.get_ip_version(),
            force_unresolvable=force,
        )
    )

    if report_processor.has_errors:
        raise LibraryError()

    # validations done

    corosync_conf.update_link(linknumber, node_addr_map, link_options)
    env.push_corosync_conf(corosync_conf, skip_offline)
