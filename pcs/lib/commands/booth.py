from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common.tools import merge_dicts
from pcs.lib.booth import configuration, resource
from pcs.lib.booth.env import get_config_file_name
from pcs.lib.cib.tools import get_resources


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
    env.booth.create_key(configuration.generate_key(), overwrite_existing)
    env.booth.create_config(
        configuration.build(
            merge_dicts(booth_configuration, {"authfile": env.booth.key_path})
        ),
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

def create_in_cluster(env, name, ip, resource_create, resource_group):
    #TODO resource_create and resource_group is provisional hack until resources
    #are not moved to lib
    cib = env.get_cib()

    booth_config_file_path = get_config_file_name(name)
    resource.validate_no_booth_resource_using_config(
        get_resources(cib),
        booth_config_file_path
    )

    resource.get_creator(resource_create, resource_group)(
        get_resources(cib),
        name,
        ip,
        booth_config_file_path,
    )
