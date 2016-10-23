from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging
import sys
from collections import namedtuple

from pcs.cli.common import middleware
from pcs.cli.common.reports import (
    LibraryReportProcessorToConsole,
    process_library_reports
)
from pcs.lib.commands import (
    acl,
    alert,
    booth,
    qdevice,
    quorum,
    resource_agent,
    sbd,
    stonith_agent,
)
from pcs.lib.commands.constraint import (
    colocation as constraint_colocation,
    order as constraint_order,
    ticket as constraint_ticket
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryEnvError


_CACHE = {}

def wrapper(dictionary):
    return namedtuple('wrapper', dictionary.keys())(**dictionary)

def cli_env_to_lib_env(cli_env):
    return LibraryEnvironment(
        logging.getLogger("old_cli"),
        LibraryReportProcessorToConsole(cli_env.debug),
        cli_env.user,
        cli_env.groups,
        cli_env.cib_data,
        cli_env.corosync_conf_data,
        booth=cli_env.booth,
        auth_tokens_getter=cli_env.auth_tokens_getter,
        cluster_conf_data=cli_env.cluster_conf_data,
    )

def lib_env_to_cli_env(lib_env, cli_env):
    if not lib_env.is_cib_live:
        cli_env.cib_data = lib_env._get_cib_xml()
        cli_env.cib_upgraded = lib_env.cib_upgraded
    if not lib_env.is_corosync_conf_live:
        cli_env.corosync_conf_data = lib_env.get_corosync_conf_data()
    if not lib_env.is_cluster_conf_live:
        cli_env.cluster_conf_data = lib_env.get_cluster_conf_data()

    #TODO
    #now we know: if is in cli_env booth is in lib_env as well
    #when we communicate with the library over the network we will need extra
    #sanitization here
    #this applies generally, not only for booth
    #corosync_conf and cib suffers with this problem as well but in this cases
    #it is dangerously hidden: when inconsistency between cli and lib
    #environment inconsitency occurs, original content is put to file (which is
    #wrong)
    if cli_env.booth:
        cli_env.booth["modified_env"] = lib_env.booth.export()

    return cli_env

def bind(cli_env, run_with_middleware, run_library_command):
    def run(cli_env, *args, **kwargs):
        lib_env = cli_env_to_lib_env(cli_env)

        lib_call_result = run_library_command(lib_env, *args, **kwargs)

        #midlewares needs finish its work and they see only cli_env
        #so we need reflect some changes to cli_env
        lib_env_to_cli_env(lib_env, cli_env)

        return lib_call_result

    def decorated_run(*args, **kwargs):
        try:
            return run_with_middleware(run, cli_env, *args, **kwargs)
        except LibraryEnvError as e:
            process_library_reports(e.unprocessed)
            #TODO we use explicit exit here - process_library_reports stil has
            #possibility to not exit - it will need deeper rethinking
            sys.exit(1)

    return decorated_run

def bind_all(env, run_with_middleware, dictionary):
    return wrapper(dict(
        (exposed_fn, bind(env, run_with_middleware, library_fn))
        for exposed_fn, library_fn in dictionary.items()
    ))

def get_module(env, middleware_factory, name):
    if name not in _CACHE:
        _CACHE[name] = load_module(env, middleware_factory, name)
    return _CACHE[name]


def load_module(env, middleware_factory, name):
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
            }
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
            }
        )

    if name == "booth":
        return bind_all(
            env,
            middleware.build(
                middleware_factory.booth_conf,
                middleware_factory.cib
            ),
            {
                "config_setup": booth.config_setup,
                "config_destroy": booth.config_destroy,
                "config_text": booth.config_text,
                "config_ticket_add": booth.config_ticket_add,
                "config_ticket_remove": booth.config_ticket_remove,
                "create_in_cluster": booth.create_in_cluster,
                "remove_from_cluster": booth.remove_from_cluster,
                "restart": booth.restart,
                "config_sync": booth.config_sync,
                "enable": booth.enable_booth,
                "disable": booth.disable_booth,
                "start": booth.start_booth,
                "stop": booth.stop_booth,
                "pull": booth.pull_config,
                "status": booth.get_status,
                "ticket_grant": booth.ticket_grant,
                "ticket_revoke": booth.ticket_revoke,
            }
        )

    if name == 'constraint_colocation':
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                'set': constraint_colocation.create_with_set,
                'show': constraint_colocation.show,
            }
        )

    if name == 'constraint_order':
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                'set': constraint_order.create_with_set,
                'show': constraint_order.show,
            }
        )

    if name == 'constraint_ticket':
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                'set': constraint_ticket.create_with_set,
                'show': constraint_ticket.show,
                'add': constraint_ticket.create,
                'remove': constraint_ticket.remove,
            }
        )

    if name == "qdevice":
        return bind_all(
            env,
            middleware.build(),
            {
                "status": qdevice.qdevice_status_text,
                "setup": qdevice.qdevice_setup,
                "destroy": qdevice.qdevice_destroy,
                "start": qdevice.qdevice_start,
                "stop": qdevice.qdevice_stop,
                "kill": qdevice.qdevice_kill,
                "enable": qdevice.qdevice_enable,
                "disable": qdevice.qdevice_disable,
                # following commands are internal use only, called from pcsd
                "client_net_setup": qdevice.client_net_setup,
                "client_net_import_certificate":
                    qdevice.client_net_import_certificate,
                "client_net_destroy": qdevice.client_net_destroy,
                "sign_net_cert_request":
                    qdevice.qdevice_net_sign_certificate_request,
            }
        )

    if name == "quorum":
        return bind_all(
            env,
            middleware.build(middleware_factory.corosync_conf_existing),
            {
                "add_device": quorum.add_device,
                "get_config": quorum.get_config,
                "remove_device": quorum.remove_device,
                "set_expected_votes_live": quorum.set_expected_votes_live,
                "set_options": quorum.set_options,
                "status": quorum.status_text,
                "status_device": quorum.status_device_text,
                "update_device": quorum.update_device,
            }
        )

    if name == "resource_agent":
        return bind_all(
            env,
            middleware.build(),
            {
                "describe_agent": resource_agent.describe_agent,
                "list_agents": resource_agent.list_agents,
                "list_agents_for_standard_and_provider":
                    resource_agent.list_agents_for_standard_and_provider,
                "list_ocf_providers": resource_agent.list_ocf_providers,
                "list_standards": resource_agent.list_standards,
            }
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
            }
        )

    if name == "stonith_agent":
        return bind_all(
            env,
            middleware.build(),
            {
                "describe_agent": stonith_agent.describe_agent,
                "list_agents": stonith_agent.list_agents,
            }
        )

    raise Exception("No library part '{0}'".format(name))

class Library(object):
    def __init__(self, env, middleware_factory):
        self.env = env
        self.middleware_factory = middleware_factory

    def __getattr__(self, name):
        return get_module(self.env, self.middleware_factory, name)
