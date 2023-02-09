from pcs import (
    prop,
    usage,
)
from pcs.cli import cluster_property
from pcs.cli.common.routing import create_router

property_cmd = create_router(
    {
        "help": lambda _lib, _argv, _modifiers: print(usage.property(_argv)),
        "set": cluster_property.set_property,
        "unset": cluster_property.unset_property,
        # TODO remove, deprecated command
        # replaced with 'config'
        "list": cluster_property.list_property_deprecated,
        # TODO remove, deprecated command
        # replaced with 'config'
        "show": cluster_property.list_property_deprecated,
        "config": cluster_property.config,
        "get_cluster_properties_definition": (
            prop.print_cluster_properties_definition
        ),
    },
    ["property"],
    default_cmd="config",
)
