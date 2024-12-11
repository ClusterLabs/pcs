from pcs import usage
from pcs.cli.cluster_property import command as cluster_property
from pcs.cli.common.errors import raise_command_replaced
from pcs.cli.common.routing import create_router

property_cmd = create_router(
    {
        "help": lambda _lib, _argv, _modifiers: print(
            usage.property_usage(_argv)
        ),
        "set": cluster_property.set_property,
        "unset": cluster_property.unset_property,
        "list": lambda lib, argv, modifiers: raise_command_replaced(
            ["pcs property config"], pcs_version="0.12"
        ),
        "show": lambda lib, argv, modifiers: raise_command_replaced(
            ["pcs property config"], pcs_version="0.12"
        ),
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
