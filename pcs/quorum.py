from typing import Any

from pcs import (
    stonith,
    utils,
)
from pcs.cli.cluster_property.output import PropertyConfigurationFacade
from pcs.cli.common import parse_args
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    ArgsByKeywords,
    Argv,
    InputModifiers,
    KeyValueParser,
)
from pcs.cli.common.tools import print_to_stderr
from pcs.cli.reports import process_library_reports
from pcs.common.str_tools import (
    format_list,
    indent,
)
from pcs.common.types import StringSequence
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pacemaker.values import is_false


def quorum_config_cmd(lib, argv, modifiers):
    """
    Options:
      * --corosync_conf - mocked corosync configuration file
    """
    modifiers.ensure_only_supported("--corosync_conf")
    if argv:
        raise CmdLineInputError()
    lines = quorum_config_to_str(lib.quorum.get_config())
    if lines:
        print("\n".join(lines))


def quorum_config_to_str(config):
    """
    Commandline options: no options
    """
    lines = []

    if "options" in config and config["options"]:
        lines.append("Options:")
        lines.extend(
            indent(
                [
                    "{n}: {v}".format(n=name, v=value)
                    for name, value in sorted(config["options"].items())
                ]
            )
        )

    if "device" in config and config["device"]:
        lines.append("Device:")
        lines.extend(
            indent(
                [
                    "{n}: {v}".format(n=name, v=value)
                    for name, value in sorted(
                        config["device"].get("generic_options", {}).items()
                    )
                ]
            )
        )

        model_settings = [
            "Model: {m}".format(m=config["device"].get("model", ""))
        ]
        model_settings.extend(
            indent(
                [
                    "{n}: {v}".format(n=name, v=value)
                    for name, value in sorted(
                        config["device"].get("model_options", {}).items()
                    )
                ]
            )
        )
        lines.extend(indent(model_settings))

        heuristics_options = config["device"].get("heuristics_options", {})
        if heuristics_options:
            heuristics_settings = ["Heuristics:"]
            heuristics_settings.extend(
                indent(
                    [
                        "{n}: {v}".format(n=name, v=value)
                        for name, value in sorted(heuristics_options.items())
                    ]
                )
            )
            lines.extend(indent(heuristics_settings))

    return lines


def quorum_expected_votes_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        raise CmdLineInputError()
    lib.quorum.set_expected_votes_live(argv[0])


def quorum_status_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    print(lib.quorum.status_text())


def quorum_update_cmd(lib, argv, modifiers):
    """
    Options:
      * --skip-offline - skip offline nodes
      * --force - force changes
      * --corosync_conf - mocked corosync configuration file
      * --request-timeout - HTTP timeout, has effect only if --corosync_conf is
        not specified
    """
    modifiers.ensure_only_supported(
        "--skip-offline", "--force", "--corosync_conf", "--request-timeout"
    )
    options = KeyValueParser(argv).get_unique()
    if not options:
        raise CmdLineInputError()

    lib.quorum.set_options(
        options,
        skip_offline_nodes=modifiers.get("--skip-offline"),
        force=modifiers.get("--force"),
    )


def _parse_quorum_device_groups(arg_list: Argv) -> ArgsByKeywords:
    keyword_list = ["model", "heuristics"]
    groups = parse_args.group_by_keywords(
        arg_list, set(keyword_list), implicit_first_keyword="generic"
    )
    groups.ensure_unique_keywords()
    for keyword in keyword_list:
        if not groups.has_keyword(keyword):
            continue
        if not groups.get_args_flat(keyword):
            raise CmdLineInputError(f"No {keyword} options specified")
    return groups


def quorum_device_add_cmd(lib, argv, modifiers):
    """
    Options:
      * --force - allow unknown model or options
      * --skip-offline - skip offline nodes
      * --request-timeout - HTTP timeout, has effect only if --corosync_conf is
        not specified
      * --corosync_conf - mocked corosync configuration file
    """
    modifiers.ensure_only_supported(
        "--force", "--skip-offline", "--request-timeout", "--corosync_conf"
    )
    groups = _parse_quorum_device_groups(argv)
    model_and_model_options = groups.get_args_flat("model")
    # we expect "model" keyword once, followed by the actual model value
    if not model_and_model_options or "=" in model_and_model_options[0]:
        raise CmdLineInputError()

    generic_options = KeyValueParser(
        groups.get_args_flat("generic")
    ).get_unique()
    model = model_and_model_options[0]
    model_options = KeyValueParser(model_and_model_options[1:]).get_unique()
    heuristics_options = KeyValueParser(
        groups.get_args_flat("heuristics")
    ).get_unique()

    if "model" in generic_options:
        raise CmdLineInputError("Model cannot be specified in generic options")

    lib.quorum.add_device(
        model,
        model_options,
        generic_options,
        heuristics_options,
        force_model=modifiers.get("--force"),
        force_options=modifiers.get("--force"),
        skip_offline_nodes=modifiers.get("--skip-offline"),
    )


def quorum_device_remove_cmd(lib, argv, modifiers):
    """
    Options:
      * --skip-offline - skip offline nodes
      * --corosync_conf - mocked corosync configuration file
      * --request-timeout - HTTP timeout, has effect only if --corosync_conf is
        not specified
    """
    modifiers.ensure_only_supported(
        "--skip-offline", "--request-timeout", "--corosync_conf"
    )
    if argv:
        raise CmdLineInputError()

    lib.quorum.remove_device(skip_offline_nodes=modifiers.get("--skip-offline"))


def quorum_device_status_cmd(lib, argv, modifiers):
    """
    Options:
      * --full - more detailed output
    """
    modifiers.ensure_only_supported("--full")
    if argv:
        raise CmdLineInputError()
    print(lib.quorum.status_device_text(modifiers.get("--full")))


def quorum_device_update_cmd(lib, argv, modifiers):
    """
    Options:
      * --force - allow unknown options
      * --skip-offline - skip offline nodes
      * --corosync_conf - mocked corosync configuration file
      * --request-timeout - HTTP timeout, has effect only if --corosync_conf is
        not specified
    """
    modifiers.ensure_only_supported(
        "--force", "--skip-offline", "--request-timeout", "--corosync_conf"
    )
    groups = _parse_quorum_device_groups(argv)
    if groups.is_empty():
        raise CmdLineInputError()
    generic_options = KeyValueParser(
        groups.get_args_flat("generic")
    ).get_unique()
    model_options = KeyValueParser(groups.get_args_flat("model")).get_unique()
    heuristics_options = KeyValueParser(
        groups.get_args_flat("heuristics")
    ).get_unique()

    if "model" in generic_options:
        raise CmdLineInputError("Model cannot be specified in generic options")

    lib.quorum.update_device(
        model_options,
        generic_options,
        heuristics_options,
        force_options=modifiers.get("--force"),
        skip_offline_nodes=modifiers.get("--skip-offline"),
    )


def quorum_device_heuristics_remove_cmd(lib, argv, modifiers):
    """
    Options:
      * --skip-offline - skip offline nodes
      * --corosync_conf - mocked corosync configuration file
      * --request-timeout - HTTP timeout, has effect only if --corosync_conf is
        not specified
    """
    modifiers.ensure_only_supported(
        "--skip-offline", "--corosync_conf", "--request-timeout"
    )
    if argv:
        raise CmdLineInputError()
    lib.quorum.remove_device_heuristics(
        skip_offline_nodes=modifiers.get("--skip-offline"),
    )


# TODO switch to new architecture, move to lib
def quorum_unblock_cmd(lib, argv, modifiers):
    """
    Options:
      * --force - no error when removing non existing property and no warning
        about this action
    """
    modifiers.ensure_only_supported("--force")
    if argv:
        raise CmdLineInputError()

    output, retval = utils.run(
        ["corosync-cmapctl", "-g", "runtime.votequorum.wait_for_all_status"]
    )
    if (retval == 1 and "Error CS_ERR_NOT_EXIST" in output) or (
        retval == 0 and output.rsplit("=", maxsplit=1)[-1].strip() != "1"
    ):
        utils.err("cluster is not waiting for nodes to establish quorum")
    if retval != 0:
        utils.err("unable to check quorum status")

    all_nodes, report_list = get_existing_nodes_names(
        utils.get_corosync_conf_facade()
    )
    if report_list:
        process_library_reports(report_list)

    unjoined_nodes = set(all_nodes) - set(utils.getCorosyncActiveNodes())
    if not unjoined_nodes:
        utils.err("no unjoined nodes found")
    if not utils.get_continue_confirmation_or_force(
        f"If node(s) {format_list(unjoined_nodes)} are not powered off or they "
        "do have access to shared resources, data corruption and/or cluster "
        "failure may occur",
        modifiers.get("--force"),
    ):
        return
    for node in unjoined_nodes:
        # pass --force so no warning will be displayed
        stonith.stonith_confirm(
            lib, [node], parse_args.InputModifiers({"--force": ""})
        )

    output, retval = utils.run(
        ["corosync-cmapctl", "-s", "quorum.cancel_wait_for_all", "u8", "1"]
    )
    if retval != 0:
        utils.err("unable to cancel waiting for nodes")
    print_to_stderr("Quorum unblocked")

    properties_facade = PropertyConfigurationFacade.from_properties_config(
        lib.cluster_property.get_properties(),
    )
    startup_fencing = properties_facade.get_property_value(
        "startup-fencing", ""
    )
    lib.cluster_property.set_properties(
        {
            "startup-fencing": (
                "false" if not is_false(startup_fencing) else "true"
            )
        }
    )
    lib.cluster_property.set_properties({"startup-fencing": startup_fencing})
    print_to_stderr("Waiting for nodes canceled")


def check_local_qnetd_certs_cmd(
    lib: Any, argv: StringSequence, modifiers: InputModifiers
):
    modifiers.ensure_only_supported()
    if not argv or len(argv) != 2 or not argv[0] or not argv[1]:
        raise CmdLineInputError(
            "Expected arguments: <qnetd_host> <cluster_name>"
        )
    qnetd_host = argv[0]
    cluster_name = argv[1]
    result = lib.quorum.device_net_certificate_check_local(
        qnetd_host, cluster_name
    )
    if result:
        print("certificate present")
    else:
        print("certificate missing")


def setup_local_qnetd_certs_cmd(
    lib: Any, argv: StringSequence, modifiers: InputModifiers
):
    modifiers.ensure_only_supported()
    if not argv or len(argv) != 2 or not argv[0] or not argv[1]:
        raise CmdLineInputError(
            "Expected arguments: <qnetd_host> <cluster_name>"
        )
    qnetd_host = argv[0]
    cluster_name = argv[1]
    lib.quorum.device_net_certificate_setup_local(qnetd_host, cluster_name)
