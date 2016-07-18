from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib.booth import configuration


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
        configuration.build(booth_configuration),
        overwrite_existing
    )

def config_show(env):
    """
    return configuration as tuple of sites list and arbitrators list
    """
    return configuration.parse(env.booth.get_config_content())
