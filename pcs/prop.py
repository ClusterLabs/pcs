from pcs import utils
from pcs.lib.commands import cluster_property


def get_default_properties():
    """
    Commandline options: no options
    """
    parameters = {}
    lib_env = utils.get_lib_env()
    prop_def_dict = cluster_property.get_cluster_properties_definition_legacy(
        lib_env
    )
    for name, prop in prop_def_dict.items():
        parameters[name] = prop["default"]
    return parameters


def print_cluster_properties_definition(lib, argv, modifiers):
    """
    Options: no options
    """
    del lib
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    lib_env = utils.get_lib_env()
    prop_def_dict = cluster_property.get_cluster_properties_definition_legacy(
        lib_env
    )
    print(json.dumps(prop_def_dict))
