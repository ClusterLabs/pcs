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
