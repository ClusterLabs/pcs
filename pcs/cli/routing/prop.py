from pcs import usage
from pcs.cli.cluster_property import command as cluster_property
from pcs.cli.common.routing import create_router

property_cmd = create_router(
    {
        "help": lambda _lib, _argv, _modifiers: print(
            usage.property_usage(_argv)
        ),
        "set": cluster_property.set_property,
        "unset": cluster_property.unset_property,
        # TODO remove, deprecated command
        # replaced with 'config'
        "list": cluster_property.list_property_deprecated,
        # TODO remove, deprecated command
        # replaced with 'config'
        "show": cluster_property.list_property_deprecated,
        "config": cluster_property.config,
        "defaults": cluster_property.defaults,
        "describe": cluster_property.describe,
        "get_cluster_properties_definition": (
            cluster_property.print_cluster_properties_definition_legacy
        ),
    },
    ["property"],
    default_cmd="config",
)
