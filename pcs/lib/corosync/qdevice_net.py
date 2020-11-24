import os
import os.path
import re
import shutil

from pcs import settings
from pcs.common import reports
from pcs.common.str_tools import join_multilines
from pcs.common.reports.item import ReportItem
from pcs.lib import external
from pcs.lib.communication import qdevice_net as qdevice_net_com
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.errors import LibraryError
from pcs.lib.tools import write_tmpfile


__model = "net"
__service_name = "corosync-qnetd"
__qnetd_certutil = os.path.join(
    settings.corosync_qnet_binaries, "corosync-qnetd-certutil"
)
__qnetd_tool = os.path.join(
    settings.corosync_qnet_binaries, "corosync-qnetd-tool"
)
__qdevice_certutil = os.path.join(
    settings.corosync_qdevice_binaries, "corosync-qdevice-net-certutil"
)
__nss_certificate_db_files = (
    # old NSS DB format
    "cert8.db",
    "key3.db",
    "secmod.db",
    # new NSS DB format
    "cert9.db",
    "key4.db",
    "pkcs11.txt",
)


class QnetdNotRunningException(Exception):
    pass


def set_up_client_certificates(
    runner,
    reporter,
    communicator_factory,
    qnetd_target,
    cluster_name,
    cluster_nodes_target_list,
    skip_offline_nodes,
    allow_skip_offline=True,
):
    """
    setup cluster nodes for using qdevice model net
    CommandRunner runner -- command runner instance
    ReportProcessor reporter -- report processor instance
    NodeCommunicatorFactory communicator_factory -- communicator facto. instance
    Target qnetd_target -- qdevice provider (qnetd host)
    string cluster_name -- name of the cluster to which qdevice is being added
    list cluster_nodes_target_list -- list of cluster nodes targets
    bool skip_offline_nodes -- continue even if not all nodes are accessible
    bool allow_skip_offline -- enables forcing errors by skip_offline_nodes
    """
    reporter.report(
        ReportItem.info(
            reports.messages.QdeviceCertificateDistributionStarted()
        )
    )
    # get qnetd CA certificate
    com_cmd = qdevice_net_com.GetCaCert(reporter)
    com_cmd.set_targets([qnetd_target])
    qnetd_ca_cert = run_and_raise(
        communicator_factory.get_communicator(), com_cmd
    )[0][1]
    # init certificate storage on all nodes
    com_cmd = qdevice_net_com.ClientSetup(
        reporter, qnetd_ca_cert, skip_offline_nodes, allow_skip_offline
    )
    com_cmd.set_targets(cluster_nodes_target_list)
    run_and_raise(communicator_factory.get_communicator(), com_cmd)
    # create client certificate request
    cert_request = client_generate_certificate_request(runner, cluster_name)
    # sign the request on qnetd host
    com_cmd = qdevice_net_com.SignCertificate(reporter)
    com_cmd.add_request(qnetd_target, cert_request, cluster_name)
    signed_certificate = run_and_raise(
        communicator_factory.get_communicator(), com_cmd
    )[0][1]
    # transform the signed certificate to pk12 format which can sent to nodes
    pk12 = client_cert_request_to_pk12(runner, signed_certificate)
    # distribute final certificate to nodes
    com_cmd = qdevice_net_com.ClientImportCertificateAndKey(
        reporter, pk12, skip_offline_nodes, allow_skip_offline
    )
    com_cmd.set_targets(cluster_nodes_target_list)
    run_and_raise(communicator_factory.get_communicator(), com_cmd)


def qdevice_setup(runner):
    """
    initialize qdevice on local host
    """
    if qdevice_initialized():
        raise LibraryError(
            ReportItem.error(
                reports.messages.QdeviceAlreadyInitialized(__model)
            )
        )

    stdout, stderr, retval = runner.run([__qnetd_certutil, "-i"])
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.QdeviceInitializationError(
                    __model,
                    join_multilines([stderr, stdout]),
                )
            )
        )


def qdevice_initialized():
    """
    check if qdevice server certificate database has been initialized
    """
    return _nss_certificate_db_initialized(
        settings.corosync_qdevice_net_server_certs_dir
    )


def qdevice_destroy():
    """
    delete qdevice configuration on local host
    """
    try:
        if qdevice_initialized():
            shutil.rmtree(settings.corosync_qdevice_net_server_certs_dir)
    except EnvironmentError as e:
        raise LibraryError(
            ReportItem.error(
                reports.messages.QdeviceDestroyError(__model, e.strerror)
            )
        ) from e


def qdevice_status_generic_text(runner, verbose=False):
    """
    get qdevice runtime status in plain text
    bool verbose get more detailed output
    """
    args = ["-s"]
    if verbose:
        args.append("-v")
    stdout, stderr, retval = _qdevice_run_tool(runner, args)
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.QdeviceGetStatusError(
                    __model,
                    join_multilines([stderr, stdout]),
                )
            )
        )
    return stdout


def qdevice_status_cluster_text(runner, cluster=None, verbose=False):
    """
    get qdevice runtime status in plain text
    bool verbose get more detailed output
    string cluster show information only about specified cluster
    """
    args = ["-l"]
    if verbose:
        args.append("-v")
    if cluster:
        args.extend(["-c", cluster])
    stdout, stderr, retval = _qdevice_run_tool(runner, args)
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.QdeviceGetStatusError(
                    __model,
                    join_multilines([stderr, stdout]),
                )
            )
        )
    return stdout


def qdevice_connected_clusters(status_cluster_text):
    """
    parse qnetd cluster status listing and return connected clusters' names
    string status_cluster_text output of corosync-qnetd-tool -l
    """
    connected_clusters = []
    regexp = re.compile(r'^Cluster "(?P<cluster>[^"]+)":$')
    for line in status_cluster_text.splitlines():
        match = regexp.search(line)
        if match:
            connected_clusters.append(match.group("cluster"))
    return connected_clusters


def _qdevice_run_tool(runner, args):
    """
    run corosync-qnetd-tool, raise QnetdNotRunningException if qnetd not running
    CommandRunner runner
    iterable args corosync-qnetd-tool arguments
    """
    stdout, stderr, retval = runner.run([__qnetd_tool] + args)
    if retval == 3 and "is qnetd running?" in stderr.lower():
        raise QnetdNotRunningException()
    return stdout, stderr, retval


def qdevice_enable(runner):
    """
    make qdevice start automatically on boot on local host
    """
    external.enable_service(runner, __service_name)


def qdevice_disable(runner):
    """
    make qdevice not start automatically on boot on local host
    """
    external.disable_service(runner, __service_name)


def qdevice_start(runner):
    """
    start qdevice now on local host
    """
    external.start_service(runner, __service_name)


def qdevice_stop(runner):
    """
    stop qdevice now on local host
    """
    external.stop_service(runner, __service_name)


def qdevice_kill(runner):
    """
    kill qdevice now on local host
    """
    external.kill_services(runner, [__service_name])


def qdevice_sign_certificate_request(runner, cert_request, cluster_name):
    """
    sign client certificate request
    cert_request certificate request data
    string cluster_name name of the cluster to which qdevice is being added
    """
    if not qdevice_initialized():
        raise LibraryError(
            ReportItem.error(reports.messages.QdeviceNotInitialized(__model))
        )
    # save the certificate request, corosync tool only works with files
    tmpfile = _store_to_tmpfile(
        cert_request, reports.messages.QdeviceCertificateSignError
    )
    # sign the request
    stdout, stderr, retval = runner.run(
        [__qnetd_certutil, "-s", "-c", tmpfile.name, "-n", cluster_name]
    )
    tmpfile.close()  # temp file is deleted on close
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.QdeviceCertificateSignError(
                    join_multilines([stderr, stdout]),
                )
            )
        )
    # get signed certificate, corosync tool only works with files
    return _get_output_certificate(
        stdout,
        # pylint: disable=unnecessary-lambda
        lambda reason: reports.messages.QdeviceCertificateSignError(reason),
    )


def client_setup(runner, ca_certificate):
    """
    initialize qdevice client on local host
    ca_certificate qnetd CA certificate
    """
    client_destroy()
    # save CA certificate, corosync tool only works with files
    ca_file_path = os.path.join(
        settings.corosync_qdevice_net_client_certs_dir,
        settings.corosync_qdevice_net_client_ca_file_name,
    )
    try:
        if not os.path.exists(ca_file_path):
            os.makedirs(
                settings.corosync_qdevice_net_client_certs_dir, mode=0o700
            )
        with open(ca_file_path, "wb") as ca_file:
            ca_file.write(ca_certificate)
    except EnvironmentError as e:
        raise LibraryError(
            ReportItem.error(
                reports.messages.QdeviceInitializationError(
                    __model,
                    e.strerror,
                )
            )
        ) from e
    # initialize client's certificate storage
    stdout, stderr, retval = runner.run(
        [__qdevice_certutil, "-i", "-c", ca_file_path]
    )
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.QdeviceInitializationError(
                    __model,
                    join_multilines([stderr, stdout]),
                )
            )
        )


def client_initialized():
    """
    check if qdevice net client certificate database has been initialized
    """
    return _nss_certificate_db_initialized(
        settings.corosync_qdevice_net_client_certs_dir
    )


def client_destroy():
    """
    delete qdevice client config files on local host
    """
    try:
        if client_initialized():
            shutil.rmtree(settings.corosync_qdevice_net_client_certs_dir)
    except EnvironmentError as e:
        raise LibraryError(
            ReportItem.error(
                reports.messages.QdeviceDestroyError(__model, e.strerror)
            )
        ) from e


def client_generate_certificate_request(runner, cluster_name):
    """
    create a certificate request which can be signed by qnetd server
    string cluster_name name of the cluster to which qdevice is being added
    """
    if not client_initialized():
        raise LibraryError(
            ReportItem.error(reports.messages.QdeviceNotInitialized(__model))
        )
    stdout, stderr, retval = runner.run(
        [__qdevice_certutil, "-r", "-n", cluster_name]
    )
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.QdeviceInitializationError(
                    __model,
                    join_multilines([stderr, stdout]),
                )
            )
        )
    return _get_output_certificate(
        stdout,
        lambda reason: reports.messages.QdeviceInitializationError(
            __model,
            reason,
        ),
    )


def client_cert_request_to_pk12(runner, cert_request):
    """
    transform signed certificate request to pk12 certificate which can be
    imported to nodes
    cert_request signed certificate request
    """
    if not client_initialized():
        raise LibraryError(
            ReportItem.error(reports.messages.QdeviceNotInitialized(__model))
        )
    # save the signed certificate request, corosync tool only works with files
    tmpfile = _store_to_tmpfile(
        cert_request,
        reports.messages.QdeviceCertificateImportError,
    )
    # transform it
    stdout, stderr, retval = runner.run(
        [__qdevice_certutil, "-M", "-c", tmpfile.name]
    )
    tmpfile.close()  # temp file is deleted on close
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.QdeviceCertificateImportError(
                    join_multilines([stderr, stdout]),
                )
            )
        )
    # get resulting pk12, corosync tool only works with files
    return _get_output_certificate(
        stdout,
        # pylint: disable=unnecessary-lambda
        lambda reason: reports.messages.QdeviceCertificateImportError(reason),
    )


def client_import_certificate_and_key(runner, pk12_certificate):
    """
    import qdevice client certificate to the local node certificate storage
    """
    if not client_initialized():
        raise LibraryError(
            ReportItem.error(reports.messages.QdeviceNotInitialized(__model))
        )
    # save the certificate, corosync tool only works with files
    tmpfile = _store_to_tmpfile(
        pk12_certificate,
        reports.messages.QdeviceCertificateImportError,
    )
    stdout, stderr, retval = runner.run(
        [__qdevice_certutil, "-m", "-c", tmpfile.name]
    )
    tmpfile.close()  # temp file is deleted on close
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.QdeviceCertificateImportError(
                    join_multilines([stderr, stdout]),
                )
            )
        )


def _nss_certificate_db_initialized(cert_db_path):
    for filename in __nss_certificate_db_files:
        if os.path.exists(os.path.join(cert_db_path, filename)):
            return True
    return False


def _store_to_tmpfile(data, report_item_message):
    try:
        return write_tmpfile(data, binary=True)
    except EnvironmentError as e:
        raise LibraryError(
            ReportItem.error(report_item_message(e.strerror))
        ) from e


def _get_output_certificate(cert_tool_output, report_message_func):
    regexp = re.compile(r"^Certificate( request)? stored in (?P<path>.+)$")
    filename = None
    for line in cert_tool_output.splitlines():
        match = regexp.search(line)
        if match:
            filename = match.group("path")
    if not filename:
        raise LibraryError(
            ReportItem.error(report_message_func(cert_tool_output))
        )
    try:
        with open(filename, "rb") as cert_file:
            return cert_file.read()
    except EnvironmentError as e:
        raise LibraryError(
            ReportItem.error(
                report_message_func(
                    "{path}: {error}".format(path=filename, error=e.strerror)
                )
            )
        ) from e
