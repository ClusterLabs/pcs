import logging
from collections import namedtuple

from pcs import settings
from pcs.cli.common import middleware
from pcs.lib.commands import (
    acl,
    alert,
    booth,
    cib_options,
    cluster,
    cluster_property,
    dr,
    fencing_topology,
    node,
    pcsd,
    qdevice,
    quorum,
    remote_node,
    resource,
    resource_agent,
    sbd,
    scsi,
    services,
    status,
    stonith,
    stonith_agent,
    tag,
)
from pcs.lib.commands.constraint import colocation as constraint_colocation
from pcs.lib.commands.constraint import common as constraint_common
from pcs.lib.commands.constraint import order as constraint_order
from pcs.lib.commands.constraint import ticket as constraint_ticket
from pcs.lib.env import LibraryEnvironment


def wrapper(dictionary):
    return namedtuple("wrapper", dictionary.keys())(**dictionary)


def cli_env_to_lib_env(cli_env):
    return LibraryEnvironment(
        logging.getLogger("pcs"),
        cli_env.report_processor,
        cli_env.user,
        cli_env.groups,
        cli_env.cib_data,
        cli_env.corosync_conf_data,
        booth_files_data=cli_env.booth,
        known_hosts_getter=cli_env.known_hosts_getter,
        request_timeout=cli_env.request_timeout,
    )


def lib_env_to_cli_env(lib_env, cli_env):
    if not lib_env.is_cib_live:
        cli_env.cib_data = lib_env.final_mocked_cib_content
    if not lib_env.is_corosync_conf_live:
        cli_env.corosync_conf_data = lib_env.get_corosync_conf_data()

    # TODO
    # We expect that when there is booth set up in cli_env then there is booth
    # set up in lib_env as well. The code works like that now. Once we start
    # communicate over the network, we must do extra checks in here to make
    # sure what the status really is.
    # this applies generally, not only for booth
    # corosync_conf and cib suffers with this problem as well but in this cases
    # it is dangerously hidden: when inconsistency between cli and lib
    # environment occurs, original content is put to file (which is wrong)
    if cli_env.booth:
        cli_env.booth["modified_env"] = lib_env.get_booth_env(name="").export()

    return cli_env


def bind(cli_env, run_with_middleware, run_library_command):
    def run(cli_env, *args, **kwargs):
        lib_env = cli_env_to_lib_env(cli_env)

        lib_call_result = run_library_command(lib_env, *args, **kwargs)

        # midlewares needs finish its work and they see only cli_env
        # so we need reflect some changes to cli_env
        lib_env_to_cli_env(lib_env, cli_env)

        return lib_call_result

    def decorated_run(*args, **kwargs):
        return run_with_middleware(run, cli_env, *args, **kwargs)

    return decorated_run


def bind_all(env, run_with_middleware, dictionary):
    return wrapper(
        dict(
            (exposed_fn, bind(env, run_with_middleware, library_fn))
            for exposed_fn, library_fn in dictionary.items()
        )
    )


def load_module(env, middleware_factory, name):
    # pylint: disable=too-many-return-statements, too-many-branches
    if name == "acl":
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                "create_role": acl.create_role,
                "remove_role": acl.remove_role,
                "assign_role_not_specific": acl.assign_role_not_specific,
                "assign_role_to_target": acl.assign_role_to_target,
                "assign_role_to_group": acl.assign_role_to_group,
                "unassign_role_not_specific": acl.unassign_role_not_specific,
                "unassign_role_from_target": acl.unassign_role_from_target,
                "unassign_role_from_group": acl.unassign_role_from_group,
                "create_target": acl.create_target,
                "create_group": acl.create_group,
                "remove_target": acl.remove_target,
                "remove_group": acl.remove_group,
                "add_permission": acl.add_permission,
                "remove_permission": acl.remove_permission,
                "get_config": acl.get_config,
            },
        )

    if name == "alert":
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                "create_alert": alert.create_alert,
                "update_alert": alert.update_alert,
                "remove_alert": alert.remove_alert,
                "add_recipient": alert.add_recipient,
                "update_recipient": alert.update_recipient,
                "remove_recipient": alert.remove_recipient,
                "get_all_alerts": alert.get_all_alerts,
            },
        )

    if name == "booth":
        bindings = {
            "config_setup": booth.config_setup,
            "config_destroy": booth.config_destroy,
            "config_text": booth.config_text,
            "config_ticket_add": booth.config_ticket_add,
            "config_ticket_remove": booth.config_ticket_remove,
            "create_in_cluster": booth.create_in_cluster,
            "remove_from_cluster": booth.remove_from_cluster,
            "restart": booth.restart,
            "config_sync": booth.config_sync,
            "enable_booth": booth.enable_booth,
            "disable_booth": booth.disable_booth,
            "start_booth": booth.start_booth,
            "stop_booth": booth.stop_booth,
            "pull_config": booth.pull_config,
            "get_status": booth.get_status,
            "ticket_grant": booth.ticket_grant,
            "ticket_revoke": booth.ticket_revoke,
        }
        if settings.booth_enable_authfile_set_enabled:
            bindings[
                "config_set_enable_authfile"
            ] = booth.config_set_enable_authfile
        if settings.booth_enable_authfile_unset_enabled:
            bindings[
                "config_unset_enable_authfile"
            ] = booth.config_unset_enable_authfile
        return bind_all(
            env,
            middleware.build(
                middleware_factory.booth_conf, middleware_factory.cib
            ),
            bindings,
        )

    if name == "cluster":
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                "add_link": cluster.add_link,
                "add_nodes": cluster.add_nodes,
                "corosync_authkey_change": cluster.corosync_authkey_change,
                "config_update": cluster.config_update,
                "config_update_local": cluster.config_update_local,
                "get_corosync_conf_struct": cluster.get_corosync_conf_struct,
                "node_clear": cluster.node_clear,
                "remove_links": cluster.remove_links,
                "remove_nodes": cluster.remove_nodes,
                "remove_nodes_from_cib": cluster.remove_nodes_from_cib,
                "setup": cluster.setup,
                "setup_local": cluster.setup_local,
                "update_link": cluster.update_link,
                "verify": cluster.verify,
                "generate_cluster_uuid": cluster.generate_cluster_uuid,
                "generate_cluster_uuid_local": cluster.generate_cluster_uuid_local,
            },
        )

    if name == "dr":
        return bind_all(
            env,
            middleware.build(middleware_factory.corosync_conf_existing),
            {
                "get_config": dr.get_config,
                "destroy": dr.destroy,
                "set_recovery_site": dr.set_recovery_site,
                "status_all_sites_plaintext": dr.status_all_sites_plaintext,
            },
        )

    if name == "remote_node":
        return bind_all(
            env,
            middleware.build(
                middleware_factory.cib,
                middleware_factory.corosync_conf_existing,
            ),
            {
                "node_add_remote": remote_node.node_add_remote,
                "node_add_guest": remote_node.node_add_guest,
                "node_remove_remote": remote_node.node_remove_remote,
                "node_remove_guest": remote_node.node_remove_guest,
            },
        )

    if name == "constraint_colocation":
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                "create_with_set": constraint_colocation.create_with_set,
            },
        )

    if name == "constraint_order":
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                "create_with_set": constraint_order.create_with_set,
            },
        )

    if name == "constraint_ticket":
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                "create_with_set": constraint_ticket.create_with_set,
                "create": constraint_ticket.create,
                "remove": constraint_ticket.remove,
            },
        )

    if name == "constraint":
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                "get_config": constraint_common.get_config,
            },
        )

    if name == "fencing_topology":
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                "add_level": fencing_topology.add_level,
                "get_config": fencing_topology.get_config,
                "remove_all_levels": fencing_topology.remove_all_levels,
                "remove_levels_by_params": (
                    fencing_topology.remove_levels_by_params
                ),
                "verify": fencing_topology.verify,
            },
        )

    if name == "node":
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                "maintenance_unmaintenance_all": (
                    node.maintenance_unmaintenance_all
                ),
                "maintenance_unmaintenance_list": (
                    node.maintenance_unmaintenance_list
                ),
                "maintenance_unmaintenance_local": (
                    node.maintenance_unmaintenance_local
                ),
                "standby_unstandby_all": node.standby_unstandby_all,
                "standby_unstandby_list": node.standby_unstandby_list,
                "standby_unstandby_local": node.standby_unstandby_local,
            },
        )

    if name == "pcsd":
        return bind_all(
            env,
            middleware.build(),
            {"synchronize_ssl_certificate": pcsd.synchronize_ssl_certificate},
        )

    if name == "qdevice":
        return bind_all(
            env,
            middleware.build(),
            {
                "qdevice_status_text": qdevice.qdevice_status_text,
                "qdevice_setup": qdevice.qdevice_setup,
                "qdevice_destroy": qdevice.qdevice_destroy,
                "qdevice_start": qdevice.qdevice_start,
                "qdevice_stop": qdevice.qdevice_stop,
                "qdevice_kill": qdevice.qdevice_kill,
                "qdevice_enable": qdevice.qdevice_enable,
                "qdevice_disable": qdevice.qdevice_disable,
                # following commands are internal use only, called from pcsd
                "client_net_setup": qdevice.client_net_setup,
                "client_net_import_certificate": (
                    qdevice.client_net_import_certificate
                ),
                "client_net_destroy": qdevice.client_net_destroy,
                "qdevice_net_sign_certificate_request": (
                    qdevice.qdevice_net_sign_certificate_request
                ),
            },
        )

    if name == "quorum":
        return bind_all(
            env,
            middleware.build(middleware_factory.corosync_conf_existing),
            {
                "add_device": quorum.add_device,
                "get_config": quorum.get_config,
                "remove_device": quorum.remove_device,
                "remove_device_heuristics": quorum.remove_device_heuristics,
                "set_expected_votes_live": quorum.set_expected_votes_live,
                "set_options": quorum.set_options,
                "status_text": quorum.status_text,
                "status_device_text": quorum.status_device_text,
                "update_device": quorum.update_device,
                # used by ha_cluster system role
                "device_net_certificate_check_local": quorum.device_net_certificate_check_local,
                "device_net_certificate_setup_local": quorum.device_net_certificate_setup_local,
            },
        )

    if name == "resource_agent":
        return bind_all(
            env,
            middleware.build(),
            {
                "describe_agent": resource_agent.describe_agent,
                "get_agent_default_operations": resource_agent.get_agent_default_operations,
                "get_agent_metadata": resource_agent.get_agent_metadata,
                "get_agents_list": resource_agent.get_agents_list,
                "get_structured_agent_name": resource_agent.get_structured_agent_name,
                "list_agents_for_standard_and_provider": (
                    resource_agent.list_agents_for_standard_and_provider
                ),
                "list_agents": resource_agent.list_agents,
                "list_ocf_providers": resource_agent.list_ocf_providers,
                "list_standards": resource_agent.list_standards,
            },
        )

    if name == "resource":
        return bind_all(
            env,
            middleware.build(
                middleware_factory.cib,
                middleware_factory.corosync_conf_existing,
            ),
            {
                "ban": resource.ban,
                "bundle_create": resource.bundle_create,
                "bundle_reset": resource.bundle_reset,
                "bundle_update": resource.bundle_update,
                "create": resource.create,
                "create_as_clone": resource.create_as_clone,
                "create_in_group": resource.create_in_group,
                "create_into_bundle": resource.create_into_bundle,
                "disable": resource.disable,
                "disable_safe": resource.disable_safe,
                "disable_simulate": resource.disable_simulate,
                "enable": resource.enable,
                "get_configured_resources": resource.get_configured_resources,
                "get_failcounts": resource.get_failcounts,
                "group_add": resource.group_add,
                "is_any_resource_except_stonith": resource.is_any_resource_except_stonith,
                "is_any_stonith": resource.is_any_stonith,
                "manage": resource.manage,
                "move": resource.move,
                "move_autoclean": resource.move_autoclean,
                "get_resource_relations_tree": (
                    resource.get_resource_relations_tree
                ),
                "unmanage": resource.unmanage,
                "unmove_unban": resource.unmove_unban,
            },
        )

    if name == "cib_options":
        return bind_all(
            env,
            middleware.build(
                middleware_factory.cib,
            ),
            {
                "operation_defaults_config": cib_options.operation_defaults_config,
                "operation_defaults_create": cib_options.operation_defaults_create,
                "operation_defaults_remove": cib_options.operation_defaults_remove,
                "operation_defaults_update": cib_options.operation_defaults_update,
                "resource_defaults_config": cib_options.resource_defaults_config,
                "resource_defaults_create": cib_options.resource_defaults_create,
                "resource_defaults_remove": cib_options.resource_defaults_remove,
                "resource_defaults_update": cib_options.resource_defaults_update,
            },
        )

    if name == "status":
        return bind_all(
            env,
            middleware.build(
                middleware_factory.cib,
                middleware_factory.corosync_conf_existing,
            ),
            {
                "pacemaker_status_xml": status.pacemaker_status_xml,
                "full_cluster_status_plaintext": (
                    status.full_cluster_status_plaintext
                ),
            },
        )

    if name == "stonith":
        return bind_all(
            env,
            middleware.build(
                middleware_factory.cib,
                middleware_factory.corosync_conf_existing,
            ),
            {
                "create": stonith.create,
                "create_in_group": stonith.create_in_group,
                "history_get_text": stonith.history_get_text,
                "history_cleanup": stonith.history_cleanup,
                "history_update": stonith.history_update,
                "update_scsi_devices": stonith.update_scsi_devices,
                "update_scsi_devices_add_remove": stonith.update_scsi_devices_add_remove,
            },
        )

    if name == "sbd":
        return bind_all(
            env,
            middleware.build(),
            {
                "enable_sbd": sbd.enable_sbd,
                "disable_sbd": sbd.disable_sbd,
                "get_cluster_sbd_status": sbd.get_cluster_sbd_status,
                "get_cluster_sbd_config": sbd.get_cluster_sbd_config,
                "get_local_sbd_config": sbd.get_local_sbd_config,
                "initialize_block_devices": sbd.initialize_block_devices,
                "get_local_devices_info": sbd.get_local_devices_info,
                "set_message": sbd.set_message,
                "get_local_available_watchdogs": (
                    sbd.get_local_available_watchdogs
                ),
                "test_local_watchdog": sbd.test_local_watchdog,
            },
        )

    if name == "services":
        return bind_all(
            env,
            middleware.build(),
            {
                "start_service": services.start_service,
                "stop_service": services.stop_service,
                "enable_service": services.enable_service,
                "disable_service": services.disable_service,
                "get_services_info": services.get_services_info,
            },
        )
    if name == "scsi":
        return bind_all(
            env,
            middleware.build(),
            {
                "unfence_node": scsi.unfence_node,
                "unfence_node_mpath": scsi.unfence_node_mpath,
            },
        )

    if name == "stonith_agent":
        return bind_all(
            env,
            middleware.build(),
            {
                "describe_agent": stonith_agent.describe_agent,
                "list_agents": stonith_agent.list_agents,
            },
        )

    if name == "tag":
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                "config": tag.config,
                "create": tag.create,
                "remove": tag.remove,
                "update": tag.update,
            },
        )

    if name == "cluster_property":
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                "set_properties": cluster_property.set_properties,
                "get_properties": cluster_property.get_properties,
                "get_properties_metadata": cluster_property.get_properties_metadata,
                "get_cluster_properties_definition_legacy": cluster_property.get_cluster_properties_definition_legacy,
            },
        )

    raise Exception("No library part '{0}'".format(name))


class Library:
    # pylint: disable=too-few-public-methods
    def __init__(self, env, middleware_factory):
        self.env = env
        self.middleware_factory = middleware_factory

    def __getattr__(self, name):
        return load_module(self.env, self.middleware_factory, name)
