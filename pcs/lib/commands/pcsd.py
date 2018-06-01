from pcs import settings
from pcs.common import env_file_role_codes
from pcs.common.reports import SimpleReportProcessor
from pcs.common.tools import format_environment_error
from pcs.lib import reports
from pcs.lib.communication.nodes import SendPcsdSslCertAndKey
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.errors import LibraryError

def synchronize_ssl_certificate(env, skip_offline=False):
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
    report_processor = SimpleReportProcessor(env.report_processor)
    target_factory = env.get_node_target_factory()
    cluster_nodes_names = env.get_corosync_conf().get_nodes_names()

    try:
        with open(settings.pcsd_cert_location, "r") as f:
            ssl_cert = f.read()
    except EnvironmentError as e:
        report_processor.report(
            reports.file_io_error(
                env_file_role_codes.PCSD_SSL_CERT,
                file_path=settings.pcsd_cert_location,
                reason=format_environment_error(e),
                operation="read",
            )
        )
    try:
        with open(settings.pcsd_key_location, "r") as f:
            ssl_key = f.read()
    except EnvironmentError as e:
        report_processor.report(
            reports.file_io_error(
                env_file_role_codes.PCSD_SSL_KEY,
                file_path=settings.pcsd_key_location,
                reason=format_environment_error(e),
                operation="read",
            )
        )

    target_report_list, target_list = (
        target_factory.get_target_list_with_reports(
            cluster_nodes_names,
            skip_non_existing=skip_offline
        )
    )
    report_processor.report_list(target_report_list)

    if report_processor.has_errors:
        raise LibraryError()

    env.report_processor.process(
        reports.pcsd_ssl_cert_and_key_distribution_started(
            [target.label for target in target_list]
        )
    )

    com_cmd = SendPcsdSslCertAndKey(env.report_processor, ssl_cert, ssl_key)
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)
