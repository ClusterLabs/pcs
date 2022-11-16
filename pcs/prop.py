import json

from pcs import utils
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.reports.output import warn
from pcs.lib.commands import cluster_property


def list_property_deprecated(lib, argv, modifiers):
    warn(
        "This command is deprecated and will be removed. "
        "Please use 'pcs property config' instead.",
        stderr=True,
    )
    return list_property(lib, argv, modifiers)


def list_property(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --all - list all properties
      * --defaults - list only default values of properties
    """
    # pylint: disable=too-many-branches
    del lib
    modifiers.ensure_only_supported(
        "--defaults",
        "--all",
        "-f",
        # The hint is defined to print error messages which point users to the
        # changes section in pcs manpage.
        # To be removed in the next significant version.
        hint_syntax_changed=modifiers.is_specified("--node"),
    )
    if len(argv) > 1:
        raise CmdLineInputError()
    print_all = len(argv) == 0

    if modifiers.is_specified("--all") and modifiers.is_specified("--defaults"):
        utils.err("you cannot specify both --all and --defaults")

    if modifiers.get("--all") or modifiers.get("--defaults"):
        if not print_all:
            utils.err(
                "you cannot specify a property when using --all or --defaults"
            )
        properties = get_default_properties()
    else:
        properties = {}

    if not modifiers.get("--defaults"):
        configured_properties = utils.get_set_properties(
            None if print_all else argv[0], properties
        )
        if modifiers.get("--all"):
            properties.update(configured_properties)
        else:
            properties = configured_properties

    if properties:
        print("Cluster Properties:")
        for prop, val in sorted(properties.items()):
            print(" {0}: {1}".format(prop, val))
    else:
        properties = get_default_properties()
        print("Cluster Properties:")
        if not print_all:
            if argv[0] in properties:
                print(" {0}: {1}".format(argv[0], properties[argv[0]]))


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
