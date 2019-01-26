import sys
import json

from pcs import (
    usage,
    utils,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.routing import create_router


def set_property(lib, argv, modifiers):
    """
    Options:
      * --force - allow unknown options
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("--force", "-f")
    if not argv:
        raise CmdLineInputError()

    prop_def_dict = utils.get_cluster_properties_definition()
    failed = False
    forced = modifiers.get("--force")
    properties = {}
    for arg in argv:
        args = arg.split('=')
        if len(args) != 2:
            utils.err("invalid property format: '{0}'".format(arg), False)
            failed = True
        elif not args[0]:
            utils.err("empty property name: '{0}'".format(arg), False)
            failed = True
        elif forced or args[1].strip() == "":
            properties[args[0]] = args[1]
        else:
            try:
                if utils.is_valid_cluster_property(
                    prop_def_dict, args[0], args[1]
                ):
                    properties[args[0]] = args[1]
                else:
                    utils.err(
                        "invalid value of property: '{0}', (use --force to "
                        "override)".format(arg),
                        False
                    )
                    failed = True
            except utils.UnknownPropertyException:
                utils.err(
                    "unknown cluster property: '{0}', (use --force to "
                    "override)".format(args[0]),
                    False
                )
                failed = True

    if failed:
        sys.exit(1)

    cib_dom = utils.get_cib_dom()
    for prop, value in properties.items():
        utils.set_cib_property(prop, value, cib_dom)
    utils.replace_cib_configuration(cib_dom)


def unset_property(lib, argv, modifiers):
    """
    Options:
      * --force - no error when removing not existing properties
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("--force", "-f")
    if not argv:
        raise CmdLineInputError()

    cib_dom = utils.get_cib_dom()
    for arg in argv:
        utils.set_cib_property(arg, "", cib_dom)
    utils.replace_cib_configuration(cib_dom)

def list_property(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --all - list all properties
      * --defaults - list only default values of properties
    """
    del lib
    modifiers.ensure_only_supported("--defaults", "--all", "-f")
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
            None if print_all else argv[0],
            properties
        )
        if modifiers.get("--all"):
            properties.update(configured_properties)
        else:
            properties = configured_properties

    print("Cluster Properties:")
    for prop, val in sorted(properties.items()):
        print(" {0}: {1}".format(prop, val))

def get_default_properties():
    """
    Commandline options: no options
    """
    parameters = {}
    prop_def_dict = utils.get_cluster_properties_definition()
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
    print(json.dumps(utils.get_cluster_properties_definition()))


property_cmd = create_router(
    {
        "help": lambda _lib, _argv, _modifiers: usage.property(_argv),
        "set": set_property,
        "unset": unset_property,
        "list": list_property,
        "show": list_property,
        "get_cluster_properties_definition":
            print_cluster_properties_definition,
    },
    ["property"],
    default_cmd="list"
)
