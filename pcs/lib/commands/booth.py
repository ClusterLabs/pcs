from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib.booth import configuration
from pcs.common.tools import merge_dicts


def config_setup(env, booth_configuration, overwrite_existing=False):
    """
    create boot configuration
    list site_list contains site adresses of multisite
    list arbitrator_list contains arbitrator adresses of multisite
    """

    configuration.validate_participants(
        booth_configuration["sites"],
        booth_configuration["arbitrators"]
    )
    env.booth.create_config(
        configuration.build(merge_dicts(
            booth_configuration,
            {"authfile": env.booth.key_path}
        )),
        configuration.generate_key(),
        overwrite_existing
    )

def config_show(env):
    """
    return configuration as tuple of sites list and arbitrators list
    """
    return configuration.parse(env.booth.get_config_content())

def config_ticket_add(env, ticket_name):
    """
    add ticket to booth configuration
    """
    booth_configuration = configuration.add_ticket(
        config_show(env),
        ticket_name
    )
    env.booth.push_config(configuration.build(booth_configuration))

def config_ticket_remove(env, ticket_name):
    """
    remove ticket from booth configuration
    """
    booth_configuration = configuration.remove_ticket(
        config_show(env),
        ticket_name
    )
    env.booth.push_config(configuration.build(booth_configuration))
