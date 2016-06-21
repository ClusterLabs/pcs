from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from collections import namedtuple
from functools import partial
import logging

from pcs.cli.common import middleware

#from pcs.lib import commands does not work: "commands" is package
from pcs.lib.commands.constraint import colocation as constraint_colocation
from pcs.lib.commands.constraint import order as constraint_order
from pcs.lib.commands.constraint import ticket as constraint_ticket
from pcs.lib.commands import (
    quorum,
    qdevice,
    sbd,
)
from pcs.cli.common.reports import (
    LibraryReportProcessorToConsole as LibraryReportProcessorToConsole,
)

from pcs.lib.env import LibraryEnvironment

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
        cli_env.auth_tokens_getter,
    )

def lib_env_to_cli_env(lib_env, cli_env):
    if not lib_env.is_cib_live:
        cli_env.cib_data = lib_env._get_cib_xml()
        cli_env.cib_upgraded = lib_env.cib_upgraded
    if not lib_env.is_corosync_conf_live:
        cli_env.corosync_conf_data = lib_env.get_corosync_conf_data()
    return cli_env

def bind(cli_env, run_with_middleware, run_library_command):
    def run(cli_env, *args, **kwargs):
        lib_env = cli_env_to_lib_env(cli_env)

        lib_call_result = run_library_command(lib_env, *args, **kwargs)

        #midlewares needs finish its work and they see only cli_env
        #so we need reflect some changes to cli_env
        lib_env_to_cli_env(lib_env, cli_env)

        return lib_call_result
    return partial(run_with_middleware, run, cli_env)

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
    if name == 'constraint_order':
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                'set': constraint_order.create_with_set,
                'show': constraint_order.show,
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

    if name == 'constraint_ticket':
        return bind_all(
            env,
            middleware.build(middleware_factory.cib),
            {
                'set': constraint_ticket.create_with_set,
                'show': constraint_ticket.show,
                'add': constraint_ticket.create,
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
                "set_options": quorum.set_options,
                "update_device": quorum.update_device,
            }
        )
    if name == "qdevice":
        return bind_all(
            env,
            middleware.build(),
            {
                "setup": qdevice.qdevice_setup,
                "destroy": qdevice.qdevice_destroy,
                "start": qdevice.qdevice_start,
                "stop": qdevice.qdevice_stop,
                "kill": qdevice.qdevice_kill,
                "enable": qdevice.qdevice_enable,
                "disable": qdevice.qdevice_disable,
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

    raise Exception("No library part '{0}'".format(name))

class Library(object):
    def __init__(self, env, middleware_factory):
        self.env = env
        self.middleware_factory = middleware_factory

    def __getattr__(self, name):
        return get_module(self.env, self.middleware_factory, name)
