import json
from typing import (
    Any,
    Optional,
)

import pcs.lib.pacemaker.live as lib_pacemaker
from pcs import utils
from pcs.cli.cluster_property.output import PropertyConfigurationFacade
from pcs.cli.common.errors import (
    ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE,
    CmdLineInputError,
)
from pcs.cli.common.parse_args import (
    OUTPUT_FORMAT_OPTION,
    Argv,
    InputModifiers,
    KeyValueParser,
    ModifierValueType,
)


def node_attribute_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file (in lib wrapper)
      * --force - no error if attribute to delete doesn't exist
      * --name - specify attribute name for filter
      * --output-format - supported formats: text, cmd, json
    """
    del lib
    modifiers.ensure_only_supported(
        "-f", "--force", "--name", output_format_supported=True
    )
    if len(argv) < 2 or modifiers.is_specified_any(
        ["--name", OUTPUT_FORMAT_OPTION]
    ):
        raise CmdLineInputError()
    attribute_set_cmd(argv.pop(0), argv)


def node_utilization_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file (in lib wrapper)
      * --name - specify attribute name for filter
      * --output-format - supported formats: text, cmd, json
    """
    modifiers.ensure_only_supported(
        "-f", "--name", output_format_supported=True
    )
    if len(argv) < 2 or modifiers.is_specified_any(
        ["--name", OUTPUT_FORMAT_OPTION]
    ):
        raise CmdLineInputError()
    utils.print_warning_if_utilization_attrs_has_no_effect(
        PropertyConfigurationFacade.from_properties_dtos(
            lib.cluster_property.get_properties(),
            lib.cluster_property.get_properties_metadata(),
        )
    )
    set_node_utilization(argv.pop(0), argv)


def node_maintenance_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers, enable: bool
) -> None:
    """
    Options:
      * -f - CIB file (in lib wrapper)
      * --wait - wait for node to change state
      * --all - all cluster nodes
    """
    modifiers.ensure_only_supported("-f", "--wait", "--all")
    if argv and modifiers.get("--all"):
        raise CmdLineInputError(ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE)
    wait = modifiers.get("--wait")
    if modifiers.get("--all"):
        lib.node.maintenance_unmaintenance_all(enable, wait)
    elif argv:
        lib.node.maintenance_unmaintenance_list(enable, argv, wait)
    else:
        # -f cannot be used when editing local node
        lib.node.maintenance_unmaintenance_local(enable, wait)


def node_standby_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers, enable: bool
) -> None:
    """
    Options:
      * -f - CIB file (in lib wrapper)
      * --wait - wait for node to change state
      * --all - all cluster nodes
    """
    modifiers.ensure_only_supported("-f", "--wait", "--all")
    if argv and modifiers.get("--all"):
        raise CmdLineInputError(ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE)
    wait = modifiers.get("--wait")
    if modifiers.get("--all"):
        lib.node.standby_unstandby_all(enable, wait)
    elif argv:
        lib.node.standby_unstandby_list(enable, argv, wait)
    else:
        # -f cannot be used when editing local node
        lib.node.standby_unstandby_local(enable, wait)


def set_node_utilization(node: str, argv: Argv) -> None:
    """
    Commandline options:
      * -f - CIB file
    """
    nvpair_dict = KeyValueParser(argv).get_unique()
    if not nvpair_dict:
        return
    only_removing = True
    for value in nvpair_dict.values():
        if value != "":
            only_removing = False
            break

    cib = utils.get_cib_dom()
    node_el = utils.dom_get_node(cib, node)
    if node_el is None:
        if utils.usefile:
            utils.err(f"Unable to find a node: {node}")

        for attrs in utils.getNodeAttributesFromPacemaker():
            if attrs.name == node and attrs.type == "remote":
                node_attrs = attrs
                break
        else:
            utils.err(f"Unable to find a node: {node}")

        nodes_section_list = cib.getElementsByTagName("nodes")
        if not nodes_section_list:
            utils.err("Unable to get nodes section of cib")

        if only_removing:
            # Do not create new node if we are only removing values from it.
            return

        dom = nodes_section_list[0].ownerDocument
        node_el = dom.createElement("node")
        node_el.setAttribute("id", node_attrs.id)
        node_el.setAttribute("type", node_attrs.type)
        node_el.setAttribute("uname", node_attrs.name)
        nodes_section_list[0].appendChild(node_el)

    utils.dom_update_utilization(node_el, nvpair_dict, "nodes-")
    utils.replace_cib_configuration(cib)


def print_node_utilization(
    filter_node: Optional[str] = None,
    filter_name: ModifierValueType = None,
) -> None:
    """
    Commandline options:
      * -f - CIB file
    """
    cib = utils.get_cib_dom()

    node_element_list = cib.getElementsByTagName("node")

    if (
        filter_node
        and filter_node
        not in [
            node_element.getAttribute("uname")
            for node_element in node_element_list
        ]
        and (
            utils.usefile
            or filter_node
            not in [
                node_attrs.name
                for node_attrs in utils.getNodeAttributesFromPacemaker()
            ]
        )
    ):
        utils.err(f"Unable to find a node: {filter_node}")

    utilization = {}
    for node_el in node_element_list:
        node = node_el.getAttribute("uname")
        if filter_node is not None and node != filter_node:
            continue
        util_str = utils.get_utilization_str(node_el, filter_name)
        if util_str:
            utilization[node] = util_str
    print("Node Utilization:")
    for node in sorted(utilization):
        print(f" {node}: {utilization[node]}")


def node_pacemaker_status(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Internal pcs-pcsd command
    """
    del lib
    del argv
    del modifiers
    print(json.dumps(lib_pacemaker.get_local_node_status(utils.cmd_runner())))


def attribute_show_cmd(
    filter_node: Optional[str] = None,
    filter_attr: ModifierValueType = None,
) -> None:
    """
    Commandline options:
      * -f - CIB file (in lib wrapper)
    """
    node_attributes = utils.get_node_attributes(
        filter_node=filter_node, filter_attr=filter_attr
    )
    print("Node Attributes:")
    attribute_print(node_attributes)


def attribute_set_cmd(node: str, argv: Argv) -> None:
    """
    Commandline options:
      * -f - CIB file
      * --force - no error if attribute to delete doesn't exist
    """
    for name, value in KeyValueParser(argv).get_unique().items():
        utils.set_node_attribute(name, value, node)


def attribute_print(node_attributes):
    """
    Commandline options: no options
    """
    for node in sorted(node_attributes.keys()):
        line_parts = [" " + node + ":"]
        for name, value in sorted(node_attributes[node].items()):
            line_parts.append(f"{name}={value}")
        print(" ".join(line_parts))
