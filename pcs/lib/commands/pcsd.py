from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.file import RawFileError
from pcs.common.reports.item import ReportItem
from pcs.common.tools import format_os_error
from pcs.lib.communication.nodes import SendPcsdSslCertAndKey
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names


def synchronize_ssl_certificate(env: LibraryEnvironment, skip_offline=False):
    """
    Send the local pcsd SSL cert and key to all full nodes in the local cluster.

    Consider the pcs Web UI is accessed via an IP running as a resource in the
    cluster. When the IP is moved, the user's browser connects to the new node
    and we want it to get the same certificate to make the transition a
    seamless experience (otherwise the browser display a warning that the
    certificate has changed).
    Using pcsd Web UI on remote and guest nodes is not supported (pcs/pcsd
    depends on the corosanc.conf file being present on the local node) so we
    send the cert only to corossync (== full stack) nodes.
    """
    report_processor = env.report_processor
    target_factory = env.get_node_target_factory()
    cluster_nodes_names, report_list = get_existing_nodes_names(
        env.get_corosync_conf()
    )
    if not cluster_nodes_names:
        report_list.append(
            ReportItem.error(reports.messages.CorosyncConfigNoNodesDefined())
        )
    report_processor.report_list(report_list)

    try:
        with open(settings.pcsd_cert_location, "r") as file:
            ssl_cert = file.read()
    except OSError as e:
        report_processor.report(
            ReportItem.error(
                reports.messages.FileIoError(
                    file_type_codes.PCSD_SSL_CERT,
                    RawFileError.ACTION_READ,
                    format_os_error(e),
                    file_path=settings.pcsd_cert_location,
                )
            )
        )
    try:
        with open(settings.pcsd_key_location, "r") as file:
            ssl_key = file.read()
    except OSError as e:
        report_processor.report(
            ReportItem.error(
                reports.messages.FileIoError(
                    file_type_codes.PCSD_SSL_KEY,
                    RawFileError.ACTION_READ,
                    format_os_error(e),
                    file_path=settings.pcsd_key_location,
                )
            )
        )

    (
        target_report_list,
        target_list,
    ) = target_factory.get_target_list_with_reports(
        cluster_nodes_names, skip_non_existing=skip_offline
    )
    report_processor.report_list(target_report_list)

    if report_processor.has_errors:
        raise LibraryError()

    env.report_processor.report(
        ReportItem.info(
            reports.messages.PcsdSslCertAndKeyDistributionStarted(
                sorted([target.label for target in target_list])
            )
        )
    )

    com_cmd = SendPcsdSslCertAndKey(env.report_processor, ssl_cert, ssl_key)
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)
