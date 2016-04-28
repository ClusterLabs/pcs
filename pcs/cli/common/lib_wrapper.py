from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from collections import namedtuple
import logging

from pcs.lib.commands.constraint import colocation as constraint_colocation
from pcs.lib.commands.constraint import order as constraint_order
from pcs.lib.commands.constraint import ticket as constraint_ticket

from pcs.lib.env import LibraryEnvironment

_CACHE = {}

def wrapper(dictionary):
    return namedtuple('wrapper', dictionary.keys())(**dictionary)

def cli_env_to_lib_env(cli_env):
    return LibraryEnvironment(
        logging.getLogger("old_cli"),
        cli_env.user,
        cli_env.groups,
        cli_env.cib_data,
        cli_env.corosync_conf_data,
        cli_env.auth_tokens_getter,
    )

def bind(cli_env, run_library_command):
    def run(*args, **kwargs):
        lib_env = cli_env_to_lib_env(cli_env)

        lib_call_result = run_library_command(lib_env, *args, **kwargs)

        #midlewares needs finish its work and they see only cli_env
        #so we need reflect some changes to cli_env
        if not lib_env.is_cib_live:
            cli_env.cib_data = lib_env.get_cib_xml()

        return lib_call_result
    return run

def bind_all(env, dictionary):
    return wrapper(dict(
        (exposed_fn, bind(env, library_fn))
        for exposed_fn, library_fn in dictionary.items()
    ))

def get_module(env, name):
    if name not in _CACHE:
        _CACHE[name] = load_module(env, name)
    return _CACHE[name]

def load_module(env, name):
    if name == 'constraint_order':
        return bind_all(env, {
            'set': constraint_order.create_with_set,
            'show': constraint_order.show,
        })

    if name == 'constraint_colocation':
        return bind_all(env, {
            'set': constraint_colocation.create_with_set,
            'show': constraint_colocation.show,
        })

    if name == 'constraint_ticket':
        return bind_all(env, {
            'set': constraint_ticket.create_with_set,
            'show': constraint_ticket.show,
            'add': constraint_ticket.create,
        })

class Library(object):
    def __init__(self, env):
        self.env = env

    def __getattr__(self, name):
        return get_module(self.env, name)
