from __future__ import (
    absolute_import,
    division,
    print_function,
)

import math
import os
import subprocess
import re
import sys
import socket
import tempfile
import datetime
import json
import time
import xml.dom.minidom
try:
    # python2
    from commands import getstatusoutput
except ImportError:
    # python3
    from subprocess import getstatusoutput

try:
    # python2
    from urlparse import urlparse
except ImportError:
    # python3
    from urllib.parse import urlparse

from pcs import (
    constraint,
    node,
    pcsd,
    quorum,
    resource,
    settings,
    status,
    usage,
    utils,
)
from pcs.utils import parallel_for_nodes
from pcs.common import report_codes
from pcs.cli.common.errors import (
    CmdLineInputError,
    ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE,
)
from pcs.cli.common.reports import process_library_reports, build_report_message
import pcs.cli.cluster.command as cluster_command
from pcs.lib import (
    sbd as lib_sbd,
    reports as lib_reports,
)
from pcs.lib.booth import sync as booth_sync
from pcs.lib.commands.remote_node import _share_authkey, _destroy_pcmk_remote_env
from pcs.lib.commands.quorum import _add_device_model_net
from pcs.lib.communication.corosync import CheckCorosyncOffline
from pcs.lib.communication.nodes import DistributeFiles
from pcs.lib.communication.sbd import (
    CheckSbd,
    SetSbdConfig,
    EnableSbdService,
    DisableSbdService,
)
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.corosync import (
    config_parser as corosync_conf_utils,
    qdevice_net,
)
from pcs.cli.common.console_report import warn, error
from pcs.lib.corosync.config_facade import ConfigFacade as corosync_conf_facade
from pcs.lib.errors import (
    LibraryError,
    ReportItemSeverity,
)
from pcs.lib.external import (
    disable_service,
    is_systemctl,
    NodeCommandUnsuccessfulException,
    NodeCommunicationException,
    node_communicator_exception_to_report_item,
)
from pcs.lib.env_tools import get_nodes
from pcs.lib.node import NodeAddresses
from pcs.lib import node_communication_format
import pcs.lib.pacemaker.live as lib_pacemaker
from pcs.lib.tools import (
    environment_file_to_dict,
    generate_binary_key,
    generate_key,
)

def cluster_cmd(argv):
    if len(argv) == 0:
        usage.cluster()
        exit(1)

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.cluster([" ".join(argv)] if argv else [])
    elif (sub_cmd == "setup"):
        if "--name" in utils.pcs_options:
            cluster_setup([utils.pcs_options["--name"]] + argv)
        else:
            utils.err(
                "A cluster name (--name <name>) is required to setup a cluster"
            )
    elif (sub_cmd == "sync"):
        sync_nodes(utils.getNodesFromCorosyncConf(),utils.getCorosyncConf())
    elif (sub_cmd == "status"):
        status.cluster_status(argv)
    elif (sub_cmd == "pcsd-status"):
        status.cluster_pcsd_status(argv)
    elif (sub_cmd == "certkey"):
        cluster_certkey(argv)
    elif (sub_cmd == "auth"):
        cluster_auth(argv)
    elif (sub_cmd == "token"):
        cluster_token(argv)
    elif (sub_cmd == "token-nodes"):
        cluster_token_nodes(argv)
    elif (sub_cmd == "start"):
        if "--all" in utils.pcs_options:
            if argv:
                utils.err(ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE)
            start_cluster_all()
        else:
            start_cluster(argv)
    elif (sub_cmd == "stop"):
        if "--all" in utils.pcs_options:
            if argv:
                utils.err(ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE)
            stop_cluster_all()
        else:
            stop_cluster(argv)
    elif (sub_cmd == "kill"):
        kill_cluster(argv)
    elif (sub_cmd == "standby"):
        try:
            node.node_standby_cmd(
                utils.get_library_wrapper(),
                argv,
                utils.get_modifiers(),
                True
            )
        except LibraryError as e:
            utils.process_library_reports(e.args)
        except CmdLineInputError as e:
            utils.exit_on_cmdline_input_errror(e, "node", "standby")
    elif (sub_cmd == "unstandby"):
        try:
            node.node_standby_cmd(
                utils.get_library_wrapper(),
                argv,
                utils.get_modifiers(),
                False
            )
        except LibraryError as e:
            utils.process_library_reports(e.args)
        except CmdLineInputError as e:
            utils.exit_on_cmdline_input_errror(e, "node", "unstandby")
    elif (sub_cmd == "enable"):
        if "--all" in utils.pcs_options:
            if argv:
                utils.err(ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE)
            enable_cluster_all()
        else:
            enable_cluster(argv)
    elif (sub_cmd == "disable"):
        if "--all" in utils.pcs_options:
            if argv:
                utils.err(ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE)
            disable_cluster_all()
        else:
            disable_cluster(argv)
    elif (sub_cmd == "remote-node"):
        try:
            cluster_remote_node(argv)
        except LibraryError as e:
            utils.process_library_reports(e.args)
    elif (sub_cmd == "cib"):
        get_cib(argv)
    elif (sub_cmd == "cib-push"):
        cluster_push(argv)
    elif (sub_cmd == "cib-upgrade"):
        utils.cluster_upgrade()
    elif (sub_cmd == "edit"):
        cluster_edit(argv)
    elif (sub_cmd == "node"):
        if not argv:
            usage.cluster(["node"])
            sys.exit(1)

        remote_node_command_map = {
            "add-remote": cluster_command.node_add_remote,
            "add-guest": cluster_command.node_add_guest,
            "remove-remote": cluster_command.create_node_remove_remote(
                resource.resource_remove
            ),
            "remove-guest": cluster_command.node_remove_guest,
            "clear": cluster_command.node_clear,
        }
        if argv[0] in remote_node_command_map:
            try:
                remote_node_command_map[argv[0]](
                    utils.get_library_wrapper(),
                    argv[1:],
                    utils.get_modifiers()
                )
            except LibraryError as e:
                process_library_reports(e.args)
            except CmdLineInputError as e:
                utils.exit_on_cmdline_input_errror(
                    e, "cluster", "node " + argv[0]
                )
        else:
            cluster_node(argv)
    elif (sub_cmd == "localnode"):
        cluster_localnode(argv)
    elif (sub_cmd == "uidgid"):
        cluster_uidgid(argv)
    elif (sub_cmd == "corosync"):
        cluster_get_corosync_conf(argv)
    elif (sub_cmd == "reload"):
        cluster_reload(argv)
    elif (sub_cmd == "destroy"):
        cluster_destroy(argv)
    elif (sub_cmd == "verify"):
        cluster_verify(argv)
    elif (sub_cmd == "report"):
        cluster_report(argv)
    elif (sub_cmd == "quorum"):
        if argv and argv[0] == "unblock":
            quorum.quorum_unblock_cmd(argv[1:])
        else:
            usage.cluster()
            sys.exit(1)
    else:
        usage.cluster()
        sys.exit(1)

def sync_nodes(nodes,config):
    for node in nodes:
        utils.setCorosyncConfig(node,config)

def cluster_auth(argv):
    if len(argv) == 0:
        auth_nodes(utils.getNodesFromCorosyncConf())
    else:
        auth_nodes(argv)

def cluster_token(argv):
    if len(argv) > 1:
        utils.err("Must specify only one node")
    elif len(argv) == 0:
        utils.err("Must specify a node to get authorization token from")

    node = argv[0]
    tokens = utils.readTokens()
    if node in tokens:
        print(tokens[node])
    else:
        utils.err("No authorization token for: %s" % (node))

def cluster_token_nodes(argv):
    print("\n".join(sorted(utils.readTokens().keys())))

def auth_nodes(nodes):
    if "-u" in utils.pcs_options:
        username = utils.pcs_options["-u"]
    else:
        username = None

    if "-p" in utils.pcs_options:
        password = utils.pcs_options["-p"]
    else:
        password = None

    nodes_dict = parse_nodes_with_ports(nodes)
    need_auth = "--force" in utils.pcs_options or (username or password)
    if not need_auth:
        for node in nodes_dict.keys():
            status = utils.checkAuthorization(node)
            if status[0] == 3:
                need_auth = True
                break
            mutually_authorized = False
            if status[0] == 0:
                try:
                    auth_status = json.loads(status[1])
                    if auth_status["success"]:
                        if set(nodes_dict.keys()).issubset(
                            set(auth_status["node_list"])
                        ):
                            mutually_authorized = True
                except (ValueError, KeyError):
                    pass
            if not mutually_authorized:
                need_auth = True
                break

    if need_auth:
        if username == None:
            username = utils.get_terminal_input('Username: ')
        if password == None:
            password = utils.get_terminal_password()

        utils.auth_nodes_do(
            nodes_dict, username, password, '--force' in utils.pcs_options,
            '--local' in utils.pcs_options
        )
    else:
        for node in nodes_dict.keys():
            print(node + ": Already authorized")


def parse_nodes_with_ports(node_list):
    result = {}
    for node in node_list:
        if node.count(":") > 1 and not node.startswith("["):
            # if IPv6 without port put it in parentheses
            node = "[{0}]".format(node)
        # adding protocol so urlparse will parse hostname/ip and port correctly
        url = urlparse("http://{0}".format(node))
        if url.hostname in result and result[url.hostname] != url.port:
            raise CmdLineInputError(
                "Node '{0}' defined twice with different ports".format(
                    url.hostname
                )
            )
        result[url.hostname] = url.port
    return result


def cluster_certkey(argv):
    return pcsd.pcsd_certkey(argv)


def cluster_setup(argv):
    modifiers = utils.get_modifiers()
    allowed_encryption_values = ["0", "1"]
    if modifiers["encryption"] not in allowed_encryption_values:
        process_library_reports([
            lib_reports.invalid_option_value(
                "--encryption",
                modifiers["encryption"],
                allowed_encryption_values,
                severity=ReportItemSeverity.ERROR,
                forceable=None
            )
        ])
    if len(argv) < 2:
        usage.cluster(["setup"])
        sys.exit(1)

    is_rhel6 = utils.is_rhel6()
    cluster_name = argv[0]
    wait = False
    wait_timeout = None
    if "--start" in utils.pcs_options and "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout(False)
        wait = True

    # get nodes' addresses
    udpu_rrp = False
    node_list = []
    primary_addr_list = []
    all_addr_list = []
    for node in argv[1:]:
        addr_list = utils.parse_multiring_node(node)
        primary_addr_list.append(addr_list[0])
        all_addr_list.append(addr_list[0])
        node_options = {
            "ring0_addr": addr_list[0],
        }
        if addr_list[1]:
            udpu_rrp = True
            all_addr_list.append(addr_list[1])
            node_options["ring1_addr"] = addr_list[1]
        node_list.append(node_options)
    # special case of ring1 address on cman
    if is_rhel6 and not udpu_rrp and "--addr1" in utils.pcs_options:
        for node in node_list:
            node["ring1_addr"] = utils.pcs_options["--addr1"]

    # verify addresses
    if udpu_rrp:
        for node_options in node_list:
            if "ring1_addr" not in node_options:
                utils.err(
                    "if one node is configured for RRP, "
                    + "all nodes must be configured for RRP"
                )

    nodes_unresolvable = False
    for node_addr in all_addr_list:
        try:
            socket.getaddrinfo(node_addr, None)
        except socket.error:
            print("Warning: Unable to resolve hostname: {0}".format(node_addr))
            nodes_unresolvable = True
    if nodes_unresolvable and "--force" not in utils.pcs_options:
        utils.err("Unable to resolve all hostnames, use --force to override")

    # parse, validate and complete options
    if is_rhel6:
        options, messages = cluster_setup_parse_options_cman(
            utils.pcs_options,
            "--force" in utils.pcs_options
        )
    else:
        options, messages = cluster_setup_parse_options_corosync(
            utils.pcs_options,
            "--force" in utils.pcs_options
        )
    if udpu_rrp and "rrp_mode" not in options["transport_options"]:
        options["transport_options"]["rrp_mode"] = "passive"
    if messages:
        process_library_reports(messages)

    # prepare config file
    if is_rhel6:
        config, messages = cluster_setup_create_cluster_conf(
            cluster_name,
            node_list,
            options["transport_options"],
            options["totem_options"]
        )
    else:
        config, messages = cluster_setup_create_corosync_conf(
            cluster_name,
            node_list,
            options["transport_options"],
            options["totem_options"],
            options["quorum_options"],
            modifiers["encryption"] == "1"
        )
    if messages:
        process_library_reports(messages)

    # setup on the local node
    if "--local" in utils.pcs_options:
        # Config path can be overriden by --corosync_conf or --cluster_conf
        # command line options. If it is overriden we do not touch any cluster
        # which may be set up on the local node.
        if is_rhel6:
            config_path = settings.cluster_conf_file
        else:
            config_path = settings.corosync_conf_file
        config_path_overriden = (
            (is_rhel6 and "--cluster_conf" in utils.pcs_options)
            or
            (not is_rhel6 and "--corosync_conf" in utils.pcs_options)
        )

        # verify and ensure no cluster is set up on the host
        if "--force" not in utils.pcs_options and os.path.exists(config_path):
            utils.err("{0} already exists, use --force to overwrite".format(
                config_path
            ))
        if not config_path_overriden:
            cib_path = os.path.join(settings.cib_dir, "cib.xml")
            if "--force" not in utils.pcs_options and os.path.exists(cib_path):
                utils.err("{0} already exists, use --force to overwrite".format(
                    cib_path
                ))
            cluster_destroy([])

        # set up the cluster
        utils.setCorosyncConf(config)
        if "--start" in utils.pcs_options:
            start_cluster([])
        if "--enable" in utils.pcs_options:
            enable_cluster([])
        if wait:
            wait_for_nodes_started([], wait_timeout)

    # setup on remote nodes
    else:
        # verify and ensure no cluster is set up on the nodes
        # checks that nodes are authenticated as well
        lib_env = utils.get_lib_env()
        if "--force" not in utils.pcs_options:
            all_nodes_available = True
            for node in primary_addr_list:
                available, message = utils.canAddNodeToCluster(
                    lib_env.get_node_communicator(),
                    lib_env.get_node_target_factory().get_target(
                        NodeAddresses(node)
                    )
                )
                if not available:
                    all_nodes_available = False
                    utils.err("{0}: {1}".format(node, message), False)
            if not all_nodes_available:
                utils.err(
                    "nodes availability check failed, use --force to override. "
                    + "WARNING: This will destroy existing cluster on the nodes."
                )
        print("Destroying cluster on nodes: {0}...".format(
            ", ".join(primary_addr_list)
        ))
        destroy_cluster(primary_addr_list)
        print()

        try:
            file_definitions = {}
            file_definitions.update(
                node_communication_format.pcmk_authkey_file(generate_key())
            )
            if modifiers["encryption"] == "1":
                file_definitions.update(
                    node_communication_format.corosync_authkey_file(
                        generate_binary_key(random_bytes_count=128)
                    )
                )
            com_cmd = DistributeFiles(
                lib_env.report_processor,
                file_definitions,
                skip_offline_targets=modifiers["skip_offline_nodes"],
                allow_fails=modifiers["force"],
            )
            com_cmd.set_targets(
                lib_env.get_node_target_factory().get_target_list(
                    [NodeAddresses(node) for node in primary_addr_list]
                )
            )
            run_and_raise(lib_env.get_node_communicator(), com_cmd)
        except LibraryError as e: #Theoretically, this should not happen
            utils.process_library_reports(e.args)


        # send local cluster pcsd configs to the new nodes
        print("Sending cluster config files to the nodes...")
        pcsd_data = {
            "nodes": primary_addr_list,
            "force": True,
            "clear_local_cluster_permissions": True,
        }
        err_msgs = []
        output, retval = utils.run_pcsdcli("send_local_configs", pcsd_data)
        if retval == 0 and output["status"] == "ok" and output["data"]:
            try:
                for node in primary_addr_list:
                    node_response = output["data"][node]
                    if node_response["status"] == "notauthorized":
                        err_msgs.append(
                            "Unable to authenticate to " + node
                            + ", try running 'pcs cluster auth'"
                        )
                    if node_response["status"] not in ["ok", "not_supported"]:
                        err_msgs.append(
                            "Unable to set pcsd configs on {0}".format(node)
                        )
            except:
                err_msgs.append("Unable to communicate with pcsd")
        else:
            err_msgs.append("Unable to set pcsd configs")
        for err_msg in err_msgs:
            print("Warning: {0}".format(err_msg))

        # send the cluster config
        for node in primary_addr_list:
            utils.setCorosyncConfig(node, config)

        # start and enable the cluster if requested
        if "--start" in utils.pcs_options:
            print("\nStarting cluster on nodes: {0}...".format(
                ", ".join(primary_addr_list)
            ))
            start_cluster_nodes(primary_addr_list)
        if "--enable" in utils.pcs_options:
            enable_cluster(primary_addr_list)

        # sync certificates as the last step because it restarts pcsd
        print()
        pcsd.pcsd_sync_certs(
            [], exit_after_error=False, async_restart=modifiers["async"]
        )
        if wait:
            print()
            wait_for_nodes_started(primary_addr_list, wait_timeout)

def cluster_setup_parse_options_corosync(options, force=False):
    messages = []
    parsed = {
        "transport_options": {
            "rings_options": [],
        },
        "totem_options": {},
        "quorum_options": {},
    }
    severity = ReportItemSeverity.WARNING if force else ReportItemSeverity.ERROR
    forceable = None if force else report_codes.FORCE_OPTIONS

    transport = "udpu"
    if "--transport" in options:
        transport = options["--transport"]
        allowed_transport = ("udp", "udpu")
        if transport not in allowed_transport:
            messages.append(lib_reports.invalid_option_value(
                "transport",
                transport,
                allowed_transport,
                severity,
                forceable
            ))
    parsed["transport_options"]["transport"] = transport

    if transport == "udpu" and ("--addr0" in options or "--addr1" in options):
        messages.append(lib_reports.rrp_addresses_transport_mismatch())
    rrpmode = None
    if "--rrpmode" in options or "--addr0" in options:
        rrpmode = "passive"
        if "--rrpmode" in options:
            rrpmode = options["--rrpmode"]
        allowed_rrpmode = ("passive", "active")
        if rrpmode not in allowed_rrpmode:
            messages.append(lib_reports.invalid_option_value(
                "RRP mode",
                rrpmode,
                allowed_rrpmode,
                severity,
                forceable
            ))
        if rrpmode == "active":
            messages.append(lib_reports.rrp_active_not_supported(force))
    if rrpmode:
        parsed["transport_options"]["rrp_mode"] = rrpmode

    totem_options_names = {
        "--token": "token",
        "--token_coefficient": "token_coefficient",
        "--join": "join",
        "--consensus": "consensus",
        "--miss_count_const": "miss_count_const",
        "--fail_recv_const": "fail_recv_const",
    }
    for opt_name, parsed_name in totem_options_names.items():
        if opt_name in options:
            parsed["totem_options"][parsed_name] = options[opt_name]

    if transport == "udp":
        interface_ids = []
        if "--addr0" in options:
            interface_ids.append(0)
            if "--addr1" in options:
                interface_ids.append(1)
        for interface in interface_ids:
            ring_options = {}
            ring_options["addr"] = options["--addr{0}".format(interface)]
            if "--broadcast{0}".format(interface) in options:
                ring_options["broadcast"] = True
            else:
                if "--mcast{0}".format(interface) in options:
                    mcastaddr = options["--mcast{0}".format(interface)]
                else:
                    mcastaddr = "239.255.{0}.1".format(interface + 1)
                ring_options["mcastaddr"] = mcastaddr
                if "--mcastport{0}".format(interface) in options:
                    mcastport = options["--mcastport{0}".format(interface)]
                else:
                    mcastport = "5405"
                ring_options["mcastport"] = mcastport
                if "--ttl{0}".format(interface) in options:
                    ring_options["ttl"] = options["--ttl{0}".format(interface)]
            parsed["transport_options"]["rings_options"].append(ring_options)

    if "--ipv6" in options:
        parsed["transport_options"]["ip_version"] = "ipv6"

    quorum_options_names = {
        "--wait_for_all": "wait_for_all",
        "--auto_tie_breaker": "auto_tie_breaker",
        "--last_man_standing": "last_man_standing",
        "--last_man_standing_window": "last_man_standing_window",
    }
    for opt_name, parsed_name in quorum_options_names.items():
        if opt_name in options:
            parsed["quorum_options"][parsed_name] = options[opt_name]
    for opt_name in (
        "--wait_for_all", "--auto_tie_breaker", "--last_man_standing"
    ):
        allowed_values = ("0", "1")
        if opt_name in options and options[opt_name] not in allowed_values:
            messages.append(lib_reports.invalid_option_value(
                opt_name, options[opt_name], allowed_values
            ))

    return parsed, messages

def cluster_setup_parse_options_cman(options, force=False):
    messages = []
    parsed = {
        "transport_options": {
            "rings_options": [],
        },
        "totem_options": {},
    }
    severity = ReportItemSeverity.WARNING if force else ReportItemSeverity.ERROR
    forceable = None if force else report_codes.FORCE_OPTIONS

    broadcast = ("--broadcast0" in options) or ("--broadcast1" in options)
    if broadcast:
        transport = "udpb"
        parsed["transport_options"]["broadcast"] = True
        ring_missing_broadcast = None
        if "--broadcast0" not in options:
            ring_missing_broadcast = "0"
        if "--broadcast1" not in options:
            ring_missing_broadcast = "1"
        if ring_missing_broadcast:
            messages.append(lib_reports.cman_broadcast_all_rings())
    else:
        transport = "udp"
        if "--transport" in options:
            transport = options["--transport"]
            allowed_transport = ("udp", "udpu")
            if transport not in allowed_transport:
                messages.append(lib_reports.invalid_option_value(
                    "transport",
                    transport,
                    allowed_transport,
                    severity,
                    forceable
                ))
    parsed["transport_options"]["transport"] = transport

    if transport == "udpu":
        messages.append(lib_reports.cman_udpu_restart_required())
    if transport == "udpu" and ("--addr0" in options or "--addr1" in options):
        messages.append(lib_reports.rrp_addresses_transport_mismatch())

    rrpmode = None
    if "--rrpmode" in options or "--addr0" in options:
        rrpmode = "passive"
        if "--rrpmode" in options:
            rrpmode = options["--rrpmode"]
        allowed_rrpmode = ("passive", "active")
        if rrpmode not in allowed_rrpmode:
            messages.append(lib_reports.invalid_option_value(
                "RRP mode",
                rrpmode,
                allowed_rrpmode,
                severity,
                forceable
            ))
        if rrpmode == "active":
            messages.append(lib_reports.rrp_active_not_supported(force))
    if rrpmode:
        parsed["transport_options"]["rrp_mode"] = rrpmode

    totem_options_names = {
        "--token": "token",
        "--join": "join",
        "--consensus": "consensus",
        "--miss_count_const": "miss_count_const",
        "--fail_recv_const": "fail_recv_const",
    }
    for opt_name, parsed_name in totem_options_names.items():
        if opt_name in options:
            parsed["totem_options"][parsed_name] = options[opt_name]

    if not broadcast:
        for interface in (0, 1):
            if "--addr{0}".format(interface) not in options:
                continue
            ring_options = {}
            if "--mcast{0}".format(interface) in options:
                mcastaddr = options["--mcast{0}".format(interface)]
            else:
                mcastaddr = "239.255.{0}.1".format(interface + 1)
            ring_options["mcastaddr"] = mcastaddr
            if "--mcastport{0}".format(interface) in options:
                ring_options["mcastport"] = options[
                    "--mcastport{0}".format(interface)
                ]
            if "--ttl{0}".format(interface) in options:
                ring_options["ttl"] = options["--ttl{0}".format(interface)]
            parsed["transport_options"]["rings_options"].append(ring_options)

    ignored_options_names = (
        "--wait_for_all",
        "--auto_tie_breaker",
        "--last_man_standing",
        "--last_man_standing_window",
        "--token_coefficient",
        "--ipv6",
    )
    for opt_name in ignored_options_names:
        if opt_name in options:
            messages.append(lib_reports.cman_ignored_option(opt_name))

    return parsed, messages

def cluster_setup_create_corosync_conf(
    cluster_name, node_list, transport_options, totem_options, quorum_options,
    encrypted
):
    messages = []

    corosync_conf = corosync_conf_utils.Section("")
    totem_section = corosync_conf_utils.Section("totem")
    nodelist_section = corosync_conf_utils.Section("nodelist")
    quorum_section = corosync_conf_utils.Section("quorum")
    logging_section = corosync_conf_utils.Section("logging")
    corosync_conf.add_section(totem_section)
    corosync_conf.add_section(nodelist_section)
    corosync_conf.add_section(quorum_section)
    corosync_conf.add_section(logging_section)

    totem_section.add_attribute("version", "2")
    totem_section.add_attribute("cluster_name", cluster_name)
    if not encrypted:
        totem_section.add_attribute("secauth", "off")

    transport_options_names = (
        "transport",
        "rrp_mode",
        "ip_version",
    )
    for opt_name in transport_options_names:
        if opt_name in transport_options:
            totem_section.add_attribute(opt_name, transport_options[opt_name])

    totem_options_names = (
        "token",
        "token_coefficient",
        "join",
        "consensus",
        "miss_count_const",
        "fail_recv_const",
    )
    for opt_name in totem_options_names:
        if opt_name in totem_options:
            totem_section.add_attribute(opt_name, totem_options[opt_name])

    transport = None
    if "transport" in transport_options:
        transport = transport_options["transport"]
    if transport == "udp":
        if "rings_options" in transport_options:
            for ring_number, ring_options in enumerate(
                transport_options["rings_options"]
            ):
                interface_section = corosync_conf_utils.Section("interface")
                totem_section.add_section(interface_section)
                interface_section.add_attribute("ringnumber", ring_number)
                if "addr" in ring_options:
                    interface_section.add_attribute(
                        "bindnetaddr", ring_options["addr"]
                    )
                if "broadcast" in ring_options and ring_options["broadcast"]:
                    interface_section.add_attribute("broadcast", "yes")
                else:
                    for opt_name in ("mcastaddr", "mcastport", "ttl"):
                        if opt_name in ring_options:
                            interface_section.add_attribute(
                                opt_name,
                                ring_options[opt_name]
                            )

    for node_id, node_options in enumerate(node_list, 1):
        node_section = corosync_conf_utils.Section("node")
        nodelist_section.add_section(node_section)
        for opt_name in ("ring0_addr", "ring1_addr"):
            if opt_name in node_options:
                node_section.add_attribute(opt_name, node_options[opt_name])
        node_section.add_attribute("nodeid", node_id)

    quorum_section.add_attribute("provider", "corosync_votequorum")
    quorum_options_names = (
        "wait_for_all",
        "auto_tie_breaker",
        "last_man_standing",
        "last_man_standing_window",
    )
    for opt_name in quorum_options_names:
        if opt_name in quorum_options:
            quorum_section.add_attribute(opt_name, quorum_options[opt_name])
    auto_tie_breaker = (
        "auto_tie_breaker" in quorum_options
        and
        quorum_options["auto_tie_breaker"] == "1"
    )
    if len(node_list) == 2 and not auto_tie_breaker:
        quorum_section.add_attribute("two_node", "1")

    logging_section.add_attribute("to_logfile", "yes")
    logging_section.add_attribute("logfile", "/var/log/cluster/corosync.log")
    logging_section.add_attribute("to_syslog", "yes")

    return str(corosync_conf), messages

def cluster_setup_create_cluster_conf(
    cluster_name, node_list, transport_options, totem_options
):
    broadcast = (
        "broadcast" in transport_options
        and
        transport_options["broadcast"]
    )

    commands = []
    commands.append({
        "cmd": ["-i", "--createcluster", cluster_name],
        "err": "error creating cluster: {0}".format(cluster_name),
    })
    commands.append({
        "cmd": ["-i", "--addfencedev", "pcmk-redirect", "agent=fence_pcmk"],
        "err": "error creating fence dev: {0}".format(cluster_name),
    })

    cman_opts = []
    if "transport" in transport_options:
        cman_opts.append("transport=" + transport_options["transport"])
    cman_opts.append("broadcast=" + ("yes" if broadcast else "no"))
    if len(node_list) == 2:
        cman_opts.append("two_node=1")
        cman_opts.append("expected_votes=1")
    commands.append({
        "cmd": ["--setcman"] + cman_opts,
        "err": "error setting cman options",
    })

    for node_options in node_list:
        if "ring0_addr" in node_options:
            ring0_addr = node_options["ring0_addr"]
            commands.append({
                "cmd": ["--addnode", ring0_addr],
                "err": "error adding node: {0}".format(ring0_addr),
            })
            if "ring1_addr" in node_options:
                ring1_addr = node_options["ring1_addr"]
                commands.append({
                    "cmd": ["--addalt", ring0_addr, ring1_addr],
                    "err": (
                        "error adding alternative address for node: {0}".format(
                            ring0_addr
                        )
                    ),
                })
            commands.append({
                "cmd": ["-i", "--addmethod", "pcmk-method", ring0_addr],
                "err": "error adding fence method: {0}".format(ring0_addr),
            })
            commands.append({
                "cmd": [
                    "-i", "--addfenceinst", "pcmk-redirect", ring0_addr,
                    "pcmk-method", "port=" + ring0_addr
                ],
                "err": "error adding fence instance: {0}".format(ring0_addr),
            })

    if not broadcast:
        if "rings_options" in transport_options:
            for ring_number, ring_options in enumerate(
                transport_options["rings_options"]
            ):
                mcast_options = []
                if "mcastaddr" in ring_options:
                    mcast_options.append(ring_options["mcastaddr"])
                if "mcastport" in ring_options:
                    mcast_options.append("port=" + ring_options["mcastport"])
                if "ttl" in ring_options:
                    mcast_options.append("ttl=" + ring_options["ttl"])
                if ring_number == 0:
                    cmd_name = "--setmulticast"
                else:
                    cmd_name = "--setaltmulticast"
                commands.append({
                    "cmd": [cmd_name] + mcast_options,
                    "err": "error adding ring{0} settings".format(ring_number),
                })

    totem_options_names = (
        "token",
        "join",
        "consensus",
        "miss_count_const",
        "fail_recv_const",
    )
    totem_cmd_options = []
    for opt_name in totem_options_names:
        if opt_name in totem_options:
            totem_cmd_options.append(
                "{0}={1}".format(opt_name, totem_options[opt_name])
            )
    if "rrp_mode" in transport_options:
        totem_cmd_options.append(
            "rrp_mode={0}".format(transport_options["rrp_mode"])
        )
    if totem_cmd_options:
        commands.append({
            "cmd": ["--settotem"] + totem_cmd_options,
            "err": "error setting totem options",
        })

    messages = []
    conf_temp = tempfile.NamedTemporaryFile(mode="w+", suffix=".pcs")
    conf_path = conf_temp.name
    cmd_prefix = ["ccs", "-f", conf_path]
    for cmd_item in commands:
        output, retval = utils.run(cmd_prefix + cmd_item["cmd"])
        if retval != 0:
            if output:
                messages.append(lib_reports.common_info(output))
            messages.append(lib_reports.common_error(cmd_item["err"]))
            conf_temp.close()
            return "", messages
    conf_temp.seek(0)
    cluster_conf = conf_temp.read()
    conf_temp.close()
    return cluster_conf, messages

def get_local_network():
    args = ["/sbin/ip", "route"]
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    iproute_out = p.stdout.read()
    network_addr = re.search(r"^([0-9\.]+)", iproute_out)
    if network_addr:
        return network_addr.group(1)
    else:
        utils.err("unable to determine network address, is interface up?")

def start_cluster(argv):
    wait = False
    wait_timeout = None
    if "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout(False)
        wait = True

    if len(argv) > 0:
        nodes = set(argv) # unique
        start_cluster_nodes(nodes)
        if wait:
            wait_for_nodes_started(nodes, wait_timeout)
        return

    print("Starting Cluster...")
    service_list = []
    if utils.is_cman_cluster():
#   Verify that CMAN_QUORUM_TIMEOUT is set, if not, then we set it to 0
        retval, output = getstatusoutput('source /etc/sysconfig/cman ; [ -z "$CMAN_QUORUM_TIMEOUT" ]')
        if retval == 0:
            with open("/etc/sysconfig/cman", "a") as cman_conf_file:
                cman_conf_file.write("\nCMAN_QUORUM_TIMEOUT=0\n")

        output, retval = utils.start_service("cman")
        if retval != 0:
            print(output)
            utils.err("unable to start cman")
    else:
        service_list.append("corosync")
        if utils.need_to_handle_qdevice_service():
            service_list.append("corosync-qdevice")
    service_list.append("pacemaker")
    for service in service_list:
        output, retval = utils.start_service(service)
        if retval != 0:
            print(output)
            utils.err("unable to start {0}".format(service))
    if wait:
        wait_for_nodes_started([], wait_timeout)

def start_cluster_all():
    wait = False
    wait_timeout = None
    if "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout(False)
        wait = True

    all_nodes = utils.getNodesFromCorosyncConf()
    start_cluster_nodes(all_nodes)

    if wait:
        wait_for_nodes_started(all_nodes, wait_timeout)

def start_cluster_nodes(nodes):
    # Large clusters take longer time to start up. So we make the timeout longer
    # for each 8 nodes:
    #  1 -  8 nodes: 1 * timeout
    #  9 - 16 nodes: 2 * timeout
    # 17 - 24 nodes: 3 * timeout
    # and so on
    # Users can override this and set their own timeout by specifying
    # the --request-timeout option (see utils.sendHTTPRequest).
    timeout = int(
        settings.default_request_timeout * math.ceil(len(nodes) / 8.0)
    )
    node_errors = parallel_for_nodes(
        utils.startCluster, nodes, quiet=True, timeout=timeout
    )
    if node_errors:
        utils.err(
            "unable to start all nodes\n" + "\n".join(node_errors.values())
        )

def is_node_fully_started(node_status):
    return (
        "online" in node_status and "pending" in node_status
        and
        node_status["online"] and not node_status["pending"]
    )

def wait_for_local_node_started(stop_at, interval):
    try:
        while True:
            time.sleep(interval)
            node_status = lib_pacemaker.get_local_node_status(
                utils.cmd_runner()
            )
            if is_node_fully_started(node_status):
                return 0, "Started"
            if datetime.datetime.now() > stop_at:
                return 1, "Waiting timeout"
    except LibraryError as e:
        return 1, "Unable to get node status: {0}".format(
            "\n".join([build_report_message(item) for item in e.args])
        )

def wait_for_remote_node_started(node, stop_at, interval):
    while True:
        time.sleep(interval)
        code, output = utils.getPacemakerNodeStatus(node)
        # HTTP error, permission denied or unable to auth
        # there is no point in trying again as it won't get magically fixed
        if code in [1, 3, 4]:
            return 1, output
        if code == 0:
            try:
                status = json.loads(output)
                if (is_node_fully_started(status)):
                    return 0, "Started"
            except (ValueError, KeyError):
                # this won't get fixed either
                return 1, "Unable to get node status"
        if datetime.datetime.now() > stop_at:
            return 1, "Waiting timeout"

def wait_for_nodes_started(node_list, timeout=None):
    timeout = 60 * 15 if timeout is None else timeout
    interval = 2
    stop_at = datetime.datetime.now() + datetime.timedelta(seconds=timeout)
    print("Waiting for node(s) to start...")
    if not node_list:
        code, output = wait_for_local_node_started(stop_at, interval)
        if code != 0:
            utils.err(output)
        else:
            print(output)
    else:
        node_errors = parallel_for_nodes(
            wait_for_remote_node_started, node_list, stop_at, interval
        )
        if node_errors:
            utils.err("unable to verify all nodes have started")

def stop_cluster_all():
    stop_cluster_nodes(utils.getNodesFromCorosyncConf())

def stop_cluster_nodes(nodes):
    all_nodes = utils.getNodesFromCorosyncConf()
    unknown_nodes = set(nodes) - set(all_nodes)
    if unknown_nodes:
        utils.err(
            "nodes '%s' do not appear to exist in configuration"
            % "', '".join(unknown_nodes)
        )

    stopping_all = set(nodes) >= set(all_nodes)
    if "--force" not in utils.pcs_options and not stopping_all:
        error_list = []
        for node in nodes:
            retval, data = utils.get_remote_quorumtool_output(node)
            if retval != 0:
                error_list.append(node + ": " + data)
                continue
            # we are sure whether we are on cman cluster or not because only
            # nodes from a local cluster can be stopped (see nodes validation
            # above)
            if utils.is_rhel6():
                quorum_info = utils.parse_cman_quorum_info(data)
            else:
                quorum_info = utils.parse_quorumtool_output(data)
            if quorum_info:
                if not quorum_info["quorate"]:
                    continue
                if utils.is_node_stop_cause_quorum_loss(
                    quorum_info, local=False, node_list=nodes
                ):
                    utils.err(
                        "Stopping the node(s) will cause a loss of the quorum"
                        + ", use --force to override"
                    )
                else:
                    # We have the info, no need to print errors
                    error_list = []
                    break
            if not utils.is_node_offline_by_quorumtool_output(data):
                error_list.append("Unable to get quorum status")
            # else the node seems to be stopped already
        if error_list:
            utils.err(
                "Unable to determine whether stopping the nodes will cause "
                + "a loss of the quorum, use --force to override\n"
                + "\n".join(error_list)
            )

    was_error = False
    node_errors = parallel_for_nodes(
        utils.repeat_if_timeout(utils.stopPacemaker),
        nodes,
        quiet=True
    )
    accessible_nodes = [
        node for node in nodes if node not in node_errors.keys()
    ]
    if node_errors:
        utils.err(
            "unable to stop all nodes\n" + "\n".join(node_errors.values()),
            exit_after_error=not accessible_nodes
        )
        was_error = True

    for node in node_errors:
        print("{0}: Not stopping cluster - node is unreachable".format(node))

    node_errors = parallel_for_nodes(
        utils.stopCorosync,
        accessible_nodes,
        quiet=True
    )
    if node_errors:
        utils.err(
            "unable to stop all nodes\n" + "\n".join(node_errors.values())
        )
    if was_error:
        utils.err("unable to stop all nodes")

def enable_cluster(argv):
    if len(argv) > 0:
        enable_cluster_nodes(argv)
        return

    try:
        utils.enableServices()
    except LibraryError as e:
        process_library_reports(e.args)

def disable_cluster(argv):
    if len(argv) > 0:
        disable_cluster_nodes(argv)
        return

    try:
        utils.disableServices()
    except LibraryError as e:
        process_library_reports(e.args)

def enable_cluster_all():
    enable_cluster_nodes(utils.getNodesFromCorosyncConf())

def disable_cluster_all():
    disable_cluster_nodes(utils.getNodesFromCorosyncConf())

def enable_cluster_nodes(nodes):
    error_list = utils.map_for_error_list(utils.enableCluster, nodes)
    if len(error_list) > 0:
        utils.err("unable to enable all nodes\n" + "\n".join(error_list))

def disable_cluster_nodes(nodes):
    error_list = utils.map_for_error_list(utils.disableCluster, nodes)
    if len(error_list) > 0:
        utils.err("unable to disable all nodes\n" + "\n".join(error_list))

def destroy_cluster(argv, keep_going=False):
    if len(argv) > 0:
        # stop pacemaker and resources while cluster is still quorate
        nodes = argv
        node_errors = parallel_for_nodes(
            utils.repeat_if_timeout(utils.stopPacemaker),
            nodes,
            quiet=True
        )
        # proceed with destroy regardless of errors
        # destroy will stop any remaining cluster daemons
        node_errors = parallel_for_nodes(utils.destroyCluster, nodes, quiet=True)
        if node_errors:
            if keep_going:
                print(
                    "Warning: unable to destroy cluster\n"
                    +
                    "\n".join(node_errors.values())
                )
            else:
                utils.err(
                    "unable to destroy cluster\n"
                    + "\n".join(node_errors.values())
                )

def stop_cluster(argv):
    if len(argv) > 0:
        stop_cluster_nodes(argv)
        return

    if "--force" not in utils.pcs_options:
        if utils.is_rhel6():
            output_status, dummy_retval = utils.run(["cman_tool", "status"])
            output_nodes, dummy_retval = utils.run([
                "cman_tool", "nodes", "-F", "id,type,votes,name"
            ])
            if output_status == output_nodes:
                # when both commands return the same error
                output = output_status
            else:
                output = output_status + "\n---Votes---\n" + output_nodes
            quorum_info = utils.parse_cman_quorum_info(output)
        else:
            output, dummy_retval = utils.run(["corosync-quorumtool", "-p", "-s"])
            # retval is 0 on success if node is not in partition with quorum
            # retval is 1 on error OR on success if node has quorum
            quorum_info = utils.parse_quorumtool_output(output)
        if quorum_info:
            if utils.is_node_stop_cause_quorum_loss(quorum_info, local=True):
                utils.err(
                    "Stopping the node will cause a loss of the quorum"
                    + ", use --force to override"
                )
        elif not utils.is_node_offline_by_quorumtool_output(output):
            utils.err(
                "Unable to determine whether stopping the node will cause "
                + "a loss of the quorum, use --force to override"
            )
        # else the node seems to be stopped already, proceed to be sure

    stop_all = (
        "--pacemaker" not in utils.pcs_options
        and
        "--corosync" not in utils.pcs_options
    )
    if stop_all or "--pacemaker" in utils.pcs_options:
        stop_cluster_pacemaker()
    if stop_all or "--corosync" in utils.pcs_options:
        stop_cluster_corosync()

def stop_cluster_pacemaker():
    print("Stopping Cluster (pacemaker)...")
    if not is_systemctl():
        command = ["service", "pacemaker", "stop"]
        # If --skip-cman is not specified, pacemaker init script will stop cman
        # and corosync as well. That way some of the nodes may stop cman before
        # others stop pacemaker, which leads to quorum loss. We need to keep
        # quorum until all pacemaker resources are stopped as some of them may
        # need quorum to be able to stop.
        if utils.is_cman_cluster():
            command.append("--skip-cman")
    else:
        command = ["systemctl", "stop", "pacemaker"]
    output, retval = utils.run(command)
    if retval != 0:
        print(output)
        utils.err("unable to stop pacemaker")

def stop_cluster_corosync():
    if utils.is_rhel6():
        print("Stopping Cluster (cman)...")
        output, retval = utils.stop_service("cman")
        if retval != 0:
            print(output)
            utils.err("unable to stop cman")
    else:
        print("Stopping Cluster (corosync)...")
        service_list = []
        if utils.need_to_handle_qdevice_service():
            service_list.append("corosync-qdevice")
        service_list.append("corosync")
        for service in service_list:
            output, retval = utils.stop_service(service)
            if retval != 0:
                print(output)
                utils.err("unable to stop {0}".format(service))

def kill_cluster(argv):
    daemons = [
        "crmd",
        "pengine",
        "attrd",
        "lrmd",
        "stonithd",
        "cib",
        "pacemakerd",
        "pacemaker_remoted",
        "corosync-qdevice",
        "corosync",
    ]
    dummy_output, dummy_retval = utils.run(["killall", "-9"] + daemons)
#    if dummy_retval != 0:
#        print "Error: unable to execute killall -9"
#        print output
#        sys.exit(1)

def cluster_push(argv):
    if len(argv) > 2:
        usage.cluster(["cib-push"])
        sys.exit(1)

    filename = None
    scope = None
    timeout = None
    diff_against = None

    if "--wait" in utils.pcs_options:
        timeout = utils.validate_wait_get_timeout()
    for arg in argv:
        if "=" not in arg:
            filename = arg
        else:
            arg_name, arg_value = arg.split("=", 1)
            if arg_name == "scope":
                if "--config" in utils.pcs_options:
                    utils.err("Cannot use both scope and --config")
                if not utils.is_valid_cib_scope(arg_value):
                    utils.err("invalid CIB scope '%s'" % arg_value)
                else:
                    scope = arg_value
            elif arg_name == "diff-against":
                diff_against = arg_value
            else:
                usage.cluster(["cib-push"])
                sys.exit(1)
    if "--config" in utils.pcs_options:
        scope = "configuration"
    if diff_against and scope:
        utils.err("Cannot use both scope and diff-against")
    if not filename:
        usage.cluster(["cib-push"])
        sys.exit(1)

    try:
        new_cib_dom = xml.dom.minidom.parse(filename)
        if scope and not new_cib_dom.getElementsByTagName(scope):
            utils.err(
                "unable to push cib, scope '%s' not present in new cib"
                % scope
            )
    except (EnvironmentError, xml.parsers.expat.ExpatError) as e:
        utils.err("unable to parse new cib: %s" % e)

    if diff_against:
        try:
            xml.dom.minidom.parse(diff_against)
        except (EnvironmentError, xml.parsers.expat.ExpatError) as e:
            utils.err("unable to parse original cib: %s" % e)
        runner = utils.cmd_runner()
        command = [
            "crm_diff", "--original", diff_against, "--new", filename,
            "--no-version"
        ]
        patch, error, dummy_retval = runner.run(command)
        # dummy_retval == 1 means one of two things:
        # a) an error has occured
        # b) --original and --new differ
        # therefore it's of no use to see if an error occurred
        if error.strip():
            utils.err("unable to diff the CIBs:\n" + error)
        if not patch.strip():
            print(
                "The new CIB is the same as the original CIB, nothing to push."
            )
            sys.exit(0)

        command = ["cibadmin", "--patch", "--xml-pipe"]
        output, error, retval = runner.run(command, patch)
        if retval != 0:
            utils.err("unable to push cib\n" + error + output)

    else:
        command = ["cibadmin", "--replace", "--xml-file", filename]
        if scope:
            command.append("--scope=%s" % scope)
        output, retval = utils.run(command)
        if retval != 0:
            utils.err("unable to push cib\n" + output)

    print("CIB updated")

    if "--wait" not in utils.pcs_options:
        return
    cmd = ["crm_resource", "--wait"]
    if timeout:
        cmd.extend(["--timeout", str(timeout)])
    output, retval = utils.run(cmd)
    if retval != 0:
        msg = []
        if retval == settings.pacemaker_wait_timeout_status:
            msg.append("waiting timeout")
        if output:
            msg.append("\n" + output)
        utils.err("\n".join(msg).strip())

def cluster_edit(argv):
    if 'EDITOR' in os.environ:
        if len(argv) > 1:
            usage.cluster(["edit"])
            sys.exit(1)

        scope = None
        scope_arg = ""
        for arg in argv:
            if "=" not in arg:
                usage.cluster(["edit"])
                sys.exit(1)
            else:
                arg_name, arg_value = arg.split("=", 1)
                if arg_name == "scope" and "--config" not in utils.pcs_options:
                    if not utils.is_valid_cib_scope(arg_value):
                        utils.err("invalid CIB scope '%s'" % arg_value)
                    else:
                        scope_arg = arg
                        scope = arg_value
                else:
                    usage.cluster(["edit"])
                    sys.exit(1)
        if "--config" in utils.pcs_options:
            scope = "configuration"
            # Leave scope_arg empty as cluster_push will pick up a --config
            # option from utils.pcs_options
            scope_arg = ""

        editor = os.environ['EDITOR']
        tempcib = tempfile.NamedTemporaryFile(mode="w+", suffix=".pcs")
        cib = utils.get_cib(scope)
        tempcib.write(cib)
        tempcib.flush()
        try:
            subprocess.call([editor, tempcib.name])
        except OSError:
            utils.err("unable to open file with $EDITOR: " + editor)

        tempcib.seek(0)
        newcib = "".join(tempcib.readlines())
        if newcib == cib:
            print("CIB not updated, no changes detected")
        else:
            cluster_push([arg for arg in [tempcib.name, scope_arg] if arg])

    else:
        utils.err("$EDITOR environment variable is not set")

def get_cib(argv):
    if len(argv) > 2:
        usage.cluster(["cib"])
        sys.exit(1)

    filename = None
    scope = None
    for arg in argv:
        if "=" not in arg:
            filename = arg
        else:
            arg_name, arg_value = arg.split("=", 1)
            if arg_name == "scope" and "--config" not in utils.pcs_options:
                if not utils.is_valid_cib_scope(arg_value):
                    utils.err("invalid CIB scope '%s'" % arg_value)
                else:
                    scope = arg_value
            else:
                usage.cluster(["cib"])
                sys.exit(1)
    if "--config" in utils.pcs_options:
        scope = "configuration"

    if not filename:
        print(utils.get_cib(scope), end="")
    else:
        try:
            f = open(filename, 'w')
            output = utils.get_cib(scope)
            if output != "":
                f.write(output)
            else:
                utils.err("No data in the CIB")
        except IOError as e:
            utils.err("Unable to write to file '%s', %s" % (filename, e.strerror))


def _ensure_cluster_is_offline_if_atb_should_be_enabled(
    lib_env, node_num_modifier, skip_offline_nodes=False
):
    """
    Check if cluster is offline if auto tie breaker should be enabled.
    Raises LibraryError if ATB needs to be enabled cluster is not offline.

    lib_env -- LibraryEnvironment
    node_num_modifier -- number which wil be added to the number of nodes in
        cluster when determining whenever ATB is needed.
    skip_offline_nodes -- if True offline nodes will be skipped
    """
    if not lib_env.is_cman_cluster:
        corosync_conf = lib_env.get_corosync_conf()
        if lib_sbd.atb_has_to_be_enabled(
            lib_env.cmd_runner(), corosync_conf, node_num_modifier
        ):
            print(
                "Warning: auto_tie_breaker quorum option will be enabled to "
                "make SBD fencing effecive after this change. Cluster has to "
                "be offline to be able to make this change."
            )
            com_cmd = CheckCorosyncOffline(
                lib_env.report_processor, skip_offline_nodes
            )
            com_cmd.set_targets(
                lib_env.get_node_target_factory().get_target_list(
                    corosync_conf.get_nodes()
                )
            )
            run_and_raise(lib_env.get_node_communicator(), com_cmd)


def cluster_node(argv):
    if len(argv) < 1:
        usage.cluster(["node"])
        sys.exit(1)

    if argv[0] == "add":
        add_node = True
    elif argv[0] in ["remove","delete"]:
        add_node = False
    elif argv[0] == "add-outside":
        try:
            node_add_outside_cluster(
                utils.get_library_wrapper(),
                argv[1:],
                utils.get_modifiers(),
            )
        except CmdLineInputError as e:
            utils.exit_on_cmdline_input_errror(e, "cluster", "node")
        return
    else:
        usage.cluster(["node"])
        sys.exit(1)

    if len(argv) != 2:
        usage.cluster([" ".join(["node", argv[0]])])
        sys.exit(1)

    node = argv[1]
    node0, node1 = utils.parse_multiring_node(node)
    if not node0:
        utils.err("missing ring 0 address of the node")

    # allow to continue if removing a node with --force
    if add_node or "--force" not in utils.pcs_options:
        status, output = utils.checkAuthorization(node0)
        if status != 0:
            if status == 2:
                msg = "pcsd is not running on {0}".format(node0)
            elif status == 3:
                msg = (
                    "{node} is not yet authenticated "
                    + " (try pcs cluster auth {node})"
                ).format(node=node0)
            else:
                msg = output
            if not add_node:
                msg += ", use --force to override"
            utils.err(msg)

    lib_env = utils.get_lib_env()
    modifiers = utils.get_modifiers()

    if add_node == True:
        node_add(lib_env, node0, node1, modifiers)
    else:
        node_remove(lib_env, node0, modifiers)


def node_add_outside_cluster(lib, argv, modifiers):
    if len(argv) != 2:
        raise CmdLineInputError(
            "Usage: pcs cluster node add-outside <node[,node-altaddr]> <cluster node>"
        )

    if len(modifiers["watchdog"]) > 1:
        raise CmdLineInputError("Multiple watchdogs defined")

    node_ring0, node_ring1 = utils.parse_multiring_node(argv[0])
    cluster_node = argv[1]
    data = [
        ("new_nodename", node_ring0),
    ]

    if node_ring1:
        data.append(("new_ring1addr", node_ring1))
    if modifiers["watchdog"]:
        data.append(("watchdog", modifiers["watchdog"][0]))
    if modifiers["device"]:
        # way to send data in array
        data += [("devices[]", device) for device in modifiers["device"]]

    communicator = utils.get_lib_env().node_communicator()
    try:
        communicator.call_host(
            cluster_node,
            "remote/add_node_all",
            communicator.format_data_dict(data),
        )
    except NodeCommandUnsuccessfulException as e:
        print(e.reason)
    except NodeCommunicationException as e:
        process_library_reports([node_communicator_exception_to_report_item(e)])


def node_add(lib_env, node0, node1, modifiers):
    wait = False
    wait_timeout = None
    if "--start" in utils.pcs_options and "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout(False)
        wait = True
    need_ring1_address = utils.need_ring1_address(utils.getCorosyncConf())
    if not node1 and need_ring1_address:
        utils.err(
            "cluster is configured for RRP, "
            "you have to specify ring 1 address for the node"
        )
    elif node1 and not need_ring1_address:
        utils.err(
            "cluster is not configured for RRP, "
            "you must not specify ring 1 address for the node"
        )
    node_addr = NodeAddresses(node0, node1)
    (canAdd, error) =  utils.canAddNodeToCluster(
        lib_env.get_node_communicator(),
        lib_env.get_node_target_factory().get_target(node_addr)
    )

    if not canAdd:
        utils.err("Unable to add '%s' to cluster: %s" % (node0, error))

    report_processor = lib_env.report_processor
    com_factory = lib_env.communicator_factory

    # First set up everything else than corosync. Once the new node is
    # present in corosync.conf / cluster.conf, it's considered part of a
    # cluster and the node add command cannot be run again. So we need to
    # minimize the amout of actions (and therefore possible failures) after
    # adding the node to corosync.
    try:
        # qdevice setup
        if not utils.is_rhel6():
            conf_facade = corosync_conf_facade.from_string(
                utils.getCorosyncConf()
            )
            qdevice_model, qdevice_model_options, _, _ = conf_facade.get_quorum_device_settings()
            if qdevice_model == "net":
                _add_device_model_net(
                    lib_env,
                    qdevice_model_options["host"],
                    conf_facade.get_cluster_name(),
                    [node_addr],
                    skip_offline_nodes=False
                )

        # sbd setup
        new_node_target = lib_env.get_node_target_factory().get_target(
            node_addr
        )
        if lib_sbd.is_sbd_enabled(utils.cmd_runner()):
            if "--watchdog" not in utils.pcs_options:
                watchdog = settings.sbd_watchdog_default
                print("Warning: using default watchdog '{0}'".format(
                    watchdog
                ))
            else:
                watchdog = utils.pcs_options["--watchdog"][0]

            _ensure_cluster_is_offline_if_atb_should_be_enabled(
                lib_env, 1, modifiers["skip_offline_nodes"]
            )

            report_processor.process(lib_reports.sbd_check_started())

            device_list = utils.pcs_options.get("--device", [])
            device_num = len(device_list)
            sbd_with_device = lib_sbd.is_device_set_local()
            sbd_cfg = environment_file_to_dict(lib_sbd.get_local_sbd_config())

            if sbd_with_device and device_num not in range(1, 4):
                utils.err(
                    "SBD is configured to use shared storage, therefore it " +\
                    "is required to specify at least one device and at most " +\
                    "{0} devices (option --device),".format(
                        settings.sbd_max_device_num
                    )
                )
            elif not sbd_with_device and device_num > 0:
                utils.err(
                    "SBD is not configured to use shared device, " +\
                    "therefore --device should not be specified"
                )

            com_cmd = CheckSbd(lib_env.report_processor)
            com_cmd.add_request(new_node_target, watchdog, device_list)
            run_and_raise(com_factory.get_communicator(), com_cmd)

            com_cmd = SetSbdConfig(lib_env.report_processor)
            com_cmd.add_request(
                new_node_target,
                lib_sbd.create_sbd_config(
                    sbd_cfg, new_node_target.label, watchdog, device_list
                )
            )
            run_and_raise(com_factory.get_communicator(), com_cmd)

            com_cmd = EnableSbdService(lib_env.report_processor)
            com_cmd.add_request(new_node_target)
            run_and_raise(com_factory.get_communicator(), com_cmd)
        else:
            com_cmd = DisableSbdService(lib_env.report_processor)
            com_cmd.add_request(new_node_target)
            run_and_raise(com_factory.get_communicator(), com_cmd)

        # booth setup
        booth_sync.send_all_config_to_node(
            com_factory.get_communicator(),
            report_processor,
            new_node_target,
            rewrite_existing=modifiers["force"],
            skip_wrong_config=modifiers["force"]
        )

        if os.path.isfile(settings.corosync_authkey_file):
            com_cmd = DistributeFiles(
                lib_env.report_processor,
                node_communication_format.corosync_authkey_file(
                    open(settings.corosync_authkey_file, "rb").read()
                ),
                # added force, it was missing before
                # but it doesn't make sence here
                skip_offline_targets=modifiers["skip_offline_nodes"],
                allow_fails=modifiers["force"],
            )
            com_cmd.set_targets(
                lib_env.get_node_target_factory().get_target_list([node_addr])
            )
            run_and_raise(lib_env.get_node_communicator(), com_cmd)

        # do not send pcmk authkey to guest and remote nodes, they either have
        # it or are not working anyway
        # if the cluster is stopped, we cannot get the cib anyway
        _share_authkey(
            lib_env,
            get_nodes(lib_env.get_corosync_conf()),
            node_addr,
            skip_offline_nodes=modifiers["skip_offline_nodes"],
            allow_incomplete_distribution=modifiers["skip_offline_nodes"]
        )

    except LibraryError as e:
        process_library_reports(e.args)
    except NodeCommunicationException as e:
        process_library_reports(
            [node_communicator_exception_to_report_item(e)]
        )

    # Now add the new node to corosync.conf / cluster.conf
    corosync_conf = None
    for my_node in utils.getNodesFromCorosyncConf():
        retval, output = utils.addLocalNode(my_node, node0, node1)
        if retval != 0:
            utils.err(
                "unable to add %s on %s - %s" % (node0, my_node, output.strip()),
                False
            )
        else:
            print("%s: Corosync updated" % my_node)
            corosync_conf = output
    if not utils.is_cman_cluster():
        # When corosync 2 is in use, the procedure for adding a node is:
        # 1. add the new node to corosync.conf
        # 2. reload  corosync.conf before the new node is started
        # 3. start the new node
        # If done otherwise, membership gets broken and qdevice hangs. Cluster
        # will recover after a minute or so but still it's a wrong way.
        # When corosync 1 is in use, the procedure for adding a node is:
        # 1. add the new node to cluster.conf
        # 2. start the new node
        # Starting the node will automaticall reload cluster.conf on all
        # nodes. If the config is reloaded before the new node is started,
        # the new node gets fenced by the cluster.
        output, retval = utils.reloadCorosync()
    if corosync_conf != None:
        # send local cluster pcsd configs to the new node
        # may be used for sending corosync config as well in future
        pcsd_data = {
            'nodes': [node0],
            'force': True,
        }
        output, retval = utils.run_pcsdcli('send_local_configs', pcsd_data)
        if retval != 0:
            utils.err("Unable to set pcsd configs")
        if output['status'] == 'notauthorized':
            utils.err(
                "Unable to authenticate to " + node0
                + ", try running 'pcs cluster auth'"
            )
        if output['status'] == 'ok' and output['data']:
            try:
                node_response = output['data'][node0]
                if node_response['status'] not in ['ok', 'not_supported']:
                    utils.err("Unable to set pcsd configs")
            except:
                utils.err('Unable to communicate with pcsd')

        print("Setting up corosync...")
        utils.setCorosyncConfig(node0, corosync_conf)
        if "--enable" in utils.pcs_options:
            retval, err = utils.enableCluster(node0)
            if retval != 0:
                print("Warning: enable cluster - {0}".format(err))
        if "--start" in utils.pcs_options or utils.is_rhel6():
            # Always start the new node on cman cluster in order to reload
            # cluster.conf (see above).
            retval, err = utils.startCluster(node0)
            if retval != 0:
                print("Warning: start cluster - {0}".format(err))

        pcsd.pcsd_sync_certs([node0], exit_after_error=False)
    else:
        utils.err("Unable to update any nodes")
    if utils.is_cman_with_udpu_transport():
        print("Warning: Using udpu transport on a CMAN cluster, "
            + "cluster restart is required to apply node addition")
    if wait:
        print()
        wait_for_nodes_started([node0], wait_timeout)

def node_remove(lib_env, node0, modifiers):
    if node0 not in utils.getNodesFromCorosyncConf():
        utils.err(
            "node '%s' does not appear to exist in configuration" % node0
        )
    if "--force" not in utils.pcs_options:
        retval, data = utils.get_remote_quorumtool_output(node0)
        if retval != 0:
            utils.err(
                "Unable to determine whether removing the node will cause "
                + "a loss of the quorum, use --force to override\n"
                + data
            )
        # we are sure whether we are on cman cluster or not because only
        # nodes from a local cluster can be stopped (see nodes validation
        # above)
        if utils.is_rhel6():
            quorum_info = utils.parse_cman_quorum_info(data)
        else:
            quorum_info = utils.parse_quorumtool_output(data)
        if quorum_info:
            if utils.is_node_stop_cause_quorum_loss(
                quorum_info, local=False, node_list=[node0]
            ):
                utils.err(
                    "Removing the node will cause a loss of the quorum"
                    + ", use --force to override"
                )
        elif not utils.is_node_offline_by_quorumtool_output(data):
            utils.err(
                "Unable to determine whether removing the node will cause "
                + "a loss of the quorum, use --force to override\n"
                + data
            )
        # else the node seems to be stopped already, we're ok to proceed

    try:
        _ensure_cluster_is_offline_if_atb_should_be_enabled(
            lib_env, -1, modifiers["skip_offline_nodes"]
        )
    except LibraryError as e:
        utils.process_library_reports(e.args)

    nodesRemoved = False
    c_nodes = utils.getNodesFromCorosyncConf()
    destroy_cluster([node0], keep_going=("--force" in utils.pcs_options))
    for my_node in c_nodes:
        if my_node == node0:
            continue
        retval, output = utils.removeLocalNode(my_node, node0)
        if retval != 0:
            utils.err(
                "unable to remove %s on %s - %s" % (node0,my_node,output.strip()),
                False
            )
        else:
            if output[0] == 0:
                print("%s: Corosync updated" % my_node)
                nodesRemoved = True
            else:
                utils.err(
                    "%s: Error executing command occured: %s" % (my_node, "".join(output[1])),
                    False
                )
    if nodesRemoved == False:
        utils.err("Unable to update any nodes")

    output, retval = utils.reloadCorosync()
    output, retval = utils.run(["crm_node", "--force", "-R", node0])
    if utils.is_cman_with_udpu_transport():
        print("Warning: Using udpu transport on a CMAN cluster, "
            + "cluster restart is required to apply node removal")

def cluster_localnode(argv):
    if len(argv) != 2:
        usage.cluster()
        exit(1)
    elif argv[0] == "add":
        node = argv[1]
        if not utils.is_rhel6():
            success = utils.addNodeToCorosync(node)
        else:
            success = utils.addNodeToClusterConf(node)

        if success:
            print("%s: successfully added!" % node)
        else:
            utils.err("unable to add %s" % node)
    elif argv[0] in ["remove","delete"]:
        node = argv[1]
        if not utils.is_rhel6():
            success = utils.removeNodeFromCorosync(node)
        else:
            success = utils.removeNodeFromClusterConf(node)

# The removed node might be present in CIB. If it is, pacemaker will show it as
# offline, no matter it's not in corosync / cman config any longer. We remove
# the node by running 'crm_node -R <node>' on the node where the remove command
# was ran. This only works if pacemaker is running. If it's not, we need
# to remove the node manually from the CIB on all nodes.
        cib_node_remove = None
        if utils.usefile:
            cib_node_remove = utils.filename
        elif not utils.is_service_running(utils.cmd_runner(), "pacemaker"):
            cib_node_remove = os.path.join(settings.cib_dir, "cib.xml")
        if cib_node_remove:
            original_usefile, original_filename = utils.usefile, utils.filename
            utils.usefile = True
            utils.filename = cib_node_remove
            dummy_output, dummy_retval = utils.run([
                "cibadmin",
                "--delete-all",
                "--force",
                "--xpath=/cib/configuration/nodes/node[@uname='{0}']".format(
                    node
                ),
            ])
            utils.usefile, utils.filename = original_usefile, original_filename

        if success:
            print("%s: successfully removed!" % node)
        else:
            utils.err("unable to remove %s" % node)
    else:
        usage.cluster()
        exit(1)

def cluster_uidgid_rhel6(argv, silent_list = False):
    if not os.path.isfile(settings.cluster_conf_file):
        utils.err("the file doesn't exist on this machine, create a cluster before running this command" % settings.cluster_conf_file)

    if len(argv) == 0:
        found = False
        output, retval = utils.run(["ccs", "-f", settings.cluster_conf_file, "--lsmisc"])
        if retval != 0:
            utils.err("error running ccs\n" + output)
        lines = output.split('\n')
        for line in lines:
            if line.startswith('UID/GID: '):
                print(line)
                found = True
        if not found and not silent_list:
            print("No uidgids configured in cluster.conf")
        return

    command = argv.pop(0)
    uid=""
    gid=""
    if (command == "add" or command == "rm") and len(argv) > 0:
        for arg in argv:
            if arg.find('=') == -1:
                utils.err("uidgid options must be of the form uid=<uid> gid=<gid>")

            (k,v) = arg.split('=',1)
            if k != "uid" and k != "gid":
                utils.err("%s is not a valid key, you must use uid or gid" %k)

            if k == "uid":
                uid = v
            if k == "gid":
                gid = v
        if uid == "" and gid == "":
            utils.err("you must set either uid or gid")

        if command == "add":
            output, retval = utils.run(["ccs", "-f", settings.cluster_conf_file, "--setuidgid", "uid="+uid, "gid="+gid])
            if retval != 0:
                utils.err("unable to add uidgid\n" + output.rstrip())
        elif command == "rm":
            output, retval = utils.run(["ccs", "-f", settings.cluster_conf_file, "--rmuidgid", "uid="+uid, "gid="+gid])
            if retval != 0:
                utils.err("unable to remove uidgid\n" + output.rstrip())

        # If we make a change, we sync out the changes to all nodes unless we're using -f
        if not utils.usefile:
            sync_nodes(utils.getNodesFromCorosyncConf(), utils.getCorosyncConf())

    else:
        usage.cluster(["uidgid"])
        exit(1)

def cluster_uidgid(argv, silent_list = False):
    if utils.is_rhel6():
        cluster_uidgid_rhel6(argv, silent_list)
        return

    if len(argv) == 0:
        found = False
        uid_gid_files = os.listdir(settings.corosync_uidgid_dir)
        for ug_file in uid_gid_files:
            uid_gid_dict = utils.read_uid_gid_file(ug_file)
            if "uid" in uid_gid_dict or "gid" in uid_gid_dict:
                line = "UID/GID: uid="
                if "uid" in uid_gid_dict:
                    line += uid_gid_dict["uid"]
                line += " gid="
                if "gid" in uid_gid_dict:
                    line += uid_gid_dict["gid"]

                print(line)
                found = True
        if not found and not silent_list:
            print("No uidgids configured in cluster.conf")
        return

    command = argv.pop(0)
    uid=""
    gid=""

    if (command == "add" or command == "rm") and len(argv) > 0:
        for arg in argv:
            if arg.find('=') == -1:
                utils.err("uidgid options must be of the form uid=<uid> gid=<gid>")

            (k,v) = arg.split('=',1)
            if k != "uid" and k != "gid":
                utils.err("%s is not a valid key, you must use uid or gid" %k)

            if k == "uid":
                uid = v
            if k == "gid":
                gid = v
        if uid == "" and gid == "":
            utils.err("you must set either uid or gid")

        if command == "add":
            utils.write_uid_gid_file(uid,gid)
        elif command == "rm":
            retval = utils.remove_uid_gid_file(uid,gid)
            if retval == False:
                utils.err("no uidgid files with uid=%s and gid=%s found" % (uid,gid))

    else:
        usage.cluster(["uidgid"])
        exit(1)

def cluster_get_corosync_conf(argv):
    if utils.is_rhel6():
        utils.err("corosync.conf is not supported on CMAN clusters")

    if len(argv) > 1:
        usage.cluster()
        exit(1)

    if len(argv) == 0:
        print(utils.getCorosyncConf(), end="")
        return

    node = argv[0]
    retval, output = utils.getCorosyncConfig(node)
    if retval != 0:
        utils.err(output)
    else:
        print(output, end="")

def cluster_reload(argv):
    if len(argv) != 1 or argv[0] != "corosync":
        usage.cluster(["reload"])
        exit(1)

    output, retval = utils.reloadCorosync()
    if retval != 0 or "invalid option" in output:
        utils.err(output.rstrip())
    print("Corosync reloaded")

# Completely tear down the cluster & remove config files
# Code taken from cluster-clean script in pacemaker
def cluster_destroy(argv):
    if "--all" in utils.pcs_options:
        # destroy remote and guest nodes
        cib = None
        lib_env = utils.get_lib_env()
        try:
            cib = lib_env.get_cib()
        except LibraryError as e:
            warn(
                "Unable to load CIB to get guest and remote nodes from it, "
                "those nodes will not be deconfigured."
            )
        if cib is not None:
            try:
                all_remote_nodes = get_nodes(tree=cib)
                if len(all_remote_nodes) > 0:
                    _destroy_pcmk_remote_env(
                        lib_env,
                        all_remote_nodes,
                        skip_offline_nodes=True,
                        allow_fails=True
                    )
            except LibraryError as e:
                utils.process_library_reports(e.args)

        # destroy full-stack nodes
        destroy_cluster(utils.getNodesFromCorosyncConf())
    else:
        print("Shutting down pacemaker/corosync services...")
        for service in ["pacemaker", "corosync-qdevice", "corosync"]:
            # Returns an error if a service is not running. It is safe to
            # ignore it since we want it not to be running anyways.
            utils.stop_service(service)
        print("Killing any remaining services...")
        os.system("killall -q -9 corosync corosync-qdevice aisexec heartbeat pacemakerd ccm stonithd ha_logd lrmd crmd pengine attrd pingd mgmtd cib fenced dlm_controld gfs_controld")
        try:
            utils.disableServices()
        except:
            # previously errors were suppressed in here, let's keep it that way
            # for now
            pass
        try:
            disable_service(utils.cmd_runner(), lib_sbd.get_sbd_service_name())
        except:
            # it's not a big deal if sbd disable fails
            pass

        print("Removing all cluster configuration files...")
        if utils.is_rhel6():
            os.system("rm -f /etc/cluster/cluster.conf")
        else:
            os.system("rm -f /etc/corosync/corosync.conf")
            os.system("rm -f {0}".format(settings.corosync_authkey_file))
        state_files = ["cib.xml*", "cib-*", "core.*", "hostcache", "cts.*",
                "pe*.bz2","cib.*"]
        for name in state_files:
            os.system("find /var/lib/pacemaker -name '"+name+"' -exec rm -f \{\} \;")
        os.system("rm -f {0}".format(settings.pacemaker_authkey_file))
        try:
            qdevice_net.client_destroy()
        except:
            # errors from deleting other files are suppressed as well
            # we do not want to fail if qdevice was not set up
            pass

def cluster_verify(argv):
    if len(argv) > 1:
        usage.cluster("verify")
        raise SystemExit(1)

    if argv:
        filename = argv[0]
        if not utils.usefile:
            #We must operate on given cib everywhere.
            utils.usefile = True
            utils.filename = filename
        elif os.path.abspath(filename) == os.path.abspath(utils.filename):
            warn("File '{0}' specified twice".format(os.path.abspath(filename)))
        else:
            raise error(
                "Ambiguous cib filename specification: '{0}' vs  -f '{1}'"
                .format(filename, utils.filename)
            )

    lib = utils.get_library_wrapper()
    try:
        lib.cluster.verify(verbose="-V" in utils.pcs_options)
    except LibraryError as e:
        utils.process_library_reports(e.args)

def cluster_report(argv):
    if len(argv) != 1:
        usage.cluster(["report"])
        sys.exit(1)

    outfile = argv[0]
    dest_outfile = outfile + ".tar.bz2"
    if os.path.exists(dest_outfile):
        if "--force" not in utils.pcs_options:
            utils.err(dest_outfile + " already exists, use --force to overwrite")
        else:
            try:
                os.remove(dest_outfile)
            except OSError as e:
                utils.err("Unable to remove " + dest_outfile + ": " + e.strerror)
    crm_report_opts = []

    crm_report_opts.append("-f")
    if "--from" in utils.pcs_options:
        crm_report_opts.append(utils.pcs_options["--from"])
        if "--to" in utils.pcs_options:
            crm_report_opts.append("-t")
            crm_report_opts.append(utils.pcs_options["--to"])
    else:
        yesterday = datetime.datetime.now() - datetime.timedelta(1)
        crm_report_opts.append(yesterday.strftime("%Y-%m-%d %H:%M"))

    crm_report_opts.append(outfile)
    output, retval = utils.run([settings.crm_report] + crm_report_opts)
    if (
        retval != 0
        and
        "ERROR: Cannot determine nodes; specify --nodes or --single-node" in output
    ):
        utils.err("cluster is not configured on this node")
    newoutput = ""
    for line in output.split("\n"):
        if line.startswith("cat:") or line.startswith("grep") or line.startswith("grep") or line.startswith("tail"):
            continue
        if "We will attempt to remove" in line:
            continue
        if "-p option" in line:
            continue
        if "However, doing" in line:
            continue
        if "to diagnose" in line:
            continue
        if "--dest" in line:
            line = line.replace("--dest", "<dest>")
        newoutput = newoutput + line + "\n"
    if retval != 0:
        utils.err(newoutput)
    print(newoutput)

def cluster_remote_node(argv):
    usage_add = """\
    remote-node add <hostname> <resource id> [options]
        Enables the specified resource as a remote-node resource on the
        specified hostname (hostname should be the same as 'uname -n')."""
    usage_remove = """\
    remote-node remove <hostname>
        Disables any resources configured to be remote-node resource on the
        specified hostname (hostname should be the same as 'uname -n')."""

    if len(argv) < 1:
        print("\nUsage: pcs cluster remote-node...")
        print(usage_add)
        print()
        print(usage_remove)
        print()
        sys.exit(1)

    command = argv.pop(0)
    if command == "add":
        if len(argv) < 2:
            print("\nUsage: pcs cluster remote-node add...")
            print(usage_add)
            print()
            sys.exit(1)
        if "--force" in utils.pcs_options:
            warn("this command is deprecated, use 'pcs cluster node add-guest'")
        else:
            raise error(
                "this command is deprecated, use 'pcs cluster node add-guest'"
                ", use --force to override"
            )
        hostname = argv.pop(0)
        rsc = argv.pop(0)
        if not utils.dom_get_resource(utils.get_cib_dom(), rsc):
            utils.err("unable to find resource '%s'" % rsc)
        resource.resource_update(
            rsc,
            ["meta", "remote-node="+hostname] + argv,
            deal_with_guest_change=False
        )

    elif command in ["remove","delete"]:
        if len(argv) < 1:
            print("\nUsage: pcs cluster remote-node remove...")
            print(usage_remove)
            print()
            sys.exit(1)
        if "--force" in utils.pcs_options:
            warn(
                "this command is deprecated, use"
                " 'pcs cluster node remove-guest'"
            )
        else:
            raise error(
                "this command is deprecated, use 'pcs cluster node"
                " remove-guest', use --force to override"
            )
        hostname = argv.pop(0)
        dom = utils.get_cib_dom()
        nvpairs = dom.getElementsByTagName("nvpair")
        nvpairs_to_remove = []
        for nvpair in nvpairs:
            if nvpair.getAttribute("name") == "remote-node" and nvpair.getAttribute("value") == hostname:
                for np in nvpair.parentNode.getElementsByTagName("nvpair"):
                    if np.getAttribute("name").startswith("remote-"):
                        nvpairs_to_remove.append(np)

        if len(nvpairs_to_remove) == 0:
            utils.err("unable to remove: cannot find remote-node '%s'" % hostname)

        for nvpair in nvpairs_to_remove[:]:
            nvpair.parentNode.removeChild(nvpair)
        dom = constraint.remove_constraints_containing_node(dom, hostname)
        utils.replace_cib_configuration(dom)
        if not utils.usefile:
            output, retval = utils.run([
                "crm_node", "--force", "--remove", hostname
            ])
            if retval != 0:
                utils.err("unable to remove: {0}".format(output))
    else:
        print("\nUsage: pcs cluster remote-node...")
        print(usage_add)
        print()
        print(usage_remove)
        print()
        sys.exit(1)
