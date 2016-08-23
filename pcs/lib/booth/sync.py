from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os
import json
import base64

from pcs.common import report_codes
from pcs.lib import reports as lib_reports
from pcs.lib.errors import LibraryError, ReportItemSeverity as Severities
from pcs.lib.external import (
    NodeCommunicator,
    NodeCommunicationException,
    node_communicator_exception_to_report_item,
    parallel_nodes_communication_helper,
)
from pcs.lib.booth import (
    config_files as booth_conf,
    config_structure,
    config_parser,
    reports,
)


def _set_config_on_node(
    communicator, reporter, node, name, config_data, authfile=None,
    authfile_data=None
):
    """
    Set booth config for instance 'name' on specified node.

    communicator -- NodeCommunicator
    reporter -- report processor
    node -- NodeAddresses
    name -- name of booth instance
    config_data -- booth config as string
    authfile -- path to authfile
    authfile_data -- authfile content as bytes
    """
    data = {
        "config": {
            "name": "{0}.conf".format(name),
            "data": config_data
        }
    }
    if authfile is not None and authfile_data is not None:
        data["authfile"] = {
            "name": os.path.basename(authfile),
            "data": base64.b64encode(authfile_data).decode("utf-8")
        }
    communicator.call_node(
        node,
        "remote/booth_set_config",
        NodeCommunicator.format_data_dict([("data_json", json.dumps(data))])
    )
    reporter.process(reports.booth_config_accepted_by_node(node.label, [name]))


def send_config_to_all_nodes(
    communicator, reporter, node_list, name, config_data, authfile=None,
    authfile_data=None, skip_offline=False
):
    """
    Send config_data of specified booth instance from local node to all nodes in
    node_list.

    communicator -- NodeCommunicator
    reporter -- report processor
    node_list -- NodeAddressesList
    name -- name of booth instance
    config_data -- config_data content as string
    authfile -- path to authfile
    authfile_data -- content of authfile as bytes
    skip_offline -- if True offline nodes will be skipped
    """
    reporter.process(reports.booth_config_distribution_started())
    parallel_nodes_communication_helper(
        _set_config_on_node,
        [
            (
                [
                    communicator, reporter, node, name, config_data,
                    authfile, authfile_data
                ],
                {}
            )
            for node in node_list
        ],
        reporter,
        skip_offline
    )


def send_all_config_to_node(
    communicator,
    reporter,
    node,
    rewrite_existing=False,
    skip_wrong_config=False
):
    """
    Send all booth configs from default booth config directory and theri
    authfiles to specified node.

    communicator -- NodeCommunicator
    reporter -- report processor
    node -- NodeAddress
    rewrite_existing -- if True rewrite existing file
    skip_wrong_config -- if True skip local configs that are unreadable
    """
    config_dict = booth_conf.read_configs(reporter, skip_wrong_config)
    if not config_dict:
        return

    reporter.process(reports.booth_config_distribution_started())

    file_list = []
    for config, config_data in sorted(config_dict.items()):
        try:
            authfile_path = config_structure.get_authfile(
                config_parser.parse(config_data)
            )
            file_list.append({
                "name": config,
                "data": config_data,
                "is_authfile": False
            })
            if authfile_path:
                content = booth_conf.read_authfile(reporter, authfile_path)
                if not content:
                    continue
                file_list.append({
                    "name": os.path.basename(authfile_path),
                    "data": base64.b64encode(content).decode("utf-8"),
                    "is_authfile": True
                })
        except LibraryError:
            reporter.process(reports.booth_skipping_config(
                config, "unable to parse config"
            ))

    data = [("data_json", json.dumps(file_list))]

    if rewrite_existing:
        data.append(("rewrite_existing", "1"))

    try:
        response = json.loads(communicator.call_node(
            node,
            "remote/booth_save_files",
            NodeCommunicator.format_data_dict(data)
        ))
        report_list = []
        for file in response["existing"]:
            report_list.append(lib_reports.file_already_exists(
                None,
                file,
                Severities.WARNING if rewrite_existing else Severities.ERROR,
                (
                    None if rewrite_existing
                    else report_codes.FORCE_FILE_OVERWRITE
                ),
                node.label
            ))
        for file, reason in response["failed"].items():
            report_list.append(reports.booth_config_distribution_node_error(
                node.label, reason, file
            ))
        reporter.process_list(report_list)
        reporter.process(
            reports.booth_config_accepted_by_node(node.label, response["saved"])
        )
    except NodeCommunicationException as e:
        raise LibraryError(node_communicator_exception_to_report_item(e))
    except (KeyError, ValueError):
        raise LibraryError(lib_reports.invalid_response_format(node.label))


def pull_config_from_node(communicator, node, name):
    """
    Get config of specified booth instance and its authfile if there is one
    from 'node'. It returns dictionary with format:
    {
        "config": {
            "name": <file name of config>,
            "data": <content of file>
        },
        "authfile": {
            "name": <file name of authfile, None if it doesn't exist>,
            "data": <base64 coded content of authfile>
        }

    communicator -- NodeCommunicator
    node -- NodeAddresses
    name -- name of booth instance
    """
    try:
        return json.loads(communicator.call_node(
            node,
            "remote/booth_get_config",
            NodeCommunicator.format_data_dict([("name", name)])
        ))
    except NodeCommunicationException as e:
        raise LibraryError(node_communicator_exception_to_report_item(e))
    except ValueError:
        raise LibraryError(lib_reports.invalid_response_format(node.label))
