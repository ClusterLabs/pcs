import os
import os.path
import re
import shutil
from typing import (
    IO,
    Callable,
    Optional,
    Sequence,
)

from pcs import settings
from pcs.common import reports
from pcs.common.node_communicator import (
    NodeCommunicatorFactory,
    RequestTarget,
)
from pcs.common.str_tools import join_multilines
from pcs.common.types import StringSequence
from pcs.lib.communication import qdevice_net as qdevice_net_com
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
from pcs.lib.tools import write_tmpfile

SERVICE_NAME = "corosync-qnetd"

__model = "net"
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
    runner: CommandRunner,
    reporter: reports.ReportProcessor,
    communicator_factory: NodeCommunicatorFactory,
    qnetd_target: RequestTarget,
    cluster_name: str,
    cluster_nodes_target_list: Sequence[RequestTarget],
    skip_offline_nodes: bool,
    allow_skip_offline: bool = True,
) -> None:
    """
    setup cluster nodes for using qdevice model net

    runner -- command runner instance
    reporter -- report processor instance
    communicator_factory -- communicator facto. instance
    qnetd_target -- qdevice provider (qnetd host)
    cluster_name -- name of the cluster to which qdevice is being added
    cluster_nodes_target_list -- list of cluster nodes targets
    skip_offline_nodes -- continue even if not all nodes are accessible
    allow_skip_offline -- enables forcing errors by skip_offline_nodes
    """
    # pylint: disable=too-many-locals
    reporter.report(
        reports.ReportItem.info(
            reports.messages.QdeviceCertificateDistributionStarted()
        )
    )
    # get qnetd CA certificate
    com_cmd_1 = qdevice_net_com.GetCaCert(reporter)
    com_cmd_1.set_targets([qnetd_target])
    qnetd_ca_cert = run_and_raise(
        communicator_factory.get_communicator(), com_cmd_1
    )[0][1]
    # init certificate storage on all nodes
    com_cmd_2 = qdevice_net_com.ClientSetup(
        reporter, qnetd_ca_cert, skip_offline_nodes, allow_skip_offline
    )
    com_cmd_2.set_targets(cluster_nodes_target_list)
    run_and_raise(communicator_factory.get_communicator(), com_cmd_2)
    # create client certificate request
    cert_request = client_generate_certificate_request(runner, cluster_name)
    # sign the request on qnetd host
    com_cmd_3 = qdevice_net_com.SignCertificate(reporter)
    com_cmd_3.add_request(qnetd_target, cert_request, cluster_name)
    signed_certificate = run_and_raise(
        communicator_factory.get_communicator(), com_cmd_3
    )[0][1]
    # transform the signed certificate to pk12 format which can sent to nodes
    pk12 = client_cert_request_to_pk12(runner, signed_certificate)
    # distribute final certificate to nodes
    com_cmd_4 = qdevice_net_com.ClientImportCertificateAndKey(
        reporter, pk12, skip_offline_nodes, allow_skip_offline
    )
    com_cmd_4.set_targets(cluster_nodes_target_list)
    run_and_raise(communicator_factory.get_communicator(), com_cmd_4)


def qdevice_setup(runner: CommandRunner) -> None:
    """
    initialize qdevice on local host
    """
    if qdevice_initialized():
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.QdeviceAlreadyInitialized(__model)
            )
        )

    stdout, stderr, retval = runner.run([__qnetd_certutil, "-i"])
    if retval != 0:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.QdeviceInitializationError(
                    __model,
                    join_multilines([stderr, stdout]),
                )
            )
        )


def qdevice_initialized() -> bool:
    """
    check if qdevice server certificate database has been initialized
    """
    return _nss_certificate_db_initialized(
        settings.corosync_qdevice_net_server_certs_dir
    )


def qdevice_destroy() -> None:
    """
    delete qdevice configuration on local host
    """
    try:
        if qdevice_initialized():
            shutil.rmtree(settings.corosync_qdevice_net_server_certs_dir)
    except EnvironmentError as e:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.QdeviceDestroyError(__model, e.strerror)
            )
        ) from e


def qdevice_status_generic_text(
    runner: CommandRunner, verbose: bool = False
) -> str:
    """
    get qdevice runtime status in plain text

    verbose -- get more detailed output
    """
    args = ["-s"]
    if verbose:
        args.append("-v")
    stdout, stderr, retval = _qdevice_run_tool(runner, args)
    if retval != 0:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.QdeviceGetStatusError(
                    __model,
                    join_multilines([stderr, stdout]),
                )
            )
        )
    return stdout


def qdevice_status_cluster_text(
    runner: CommandRunner, cluster: Optional[str] = None, verbose: bool = False
) -> str:
    """
    get qdevice runtime status in plain text

    cluster -- show information only about specified cluster
    verbose -- get more detailed output
    """
    args = ["-l"]
    if verbose:
        args.append("-v")
    if cluster:
        args.extend(["-c", cluster])
    stdout, stderr, retval = _qdevice_run_tool(runner, args)
    if retval != 0:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.QdeviceGetStatusError(
                    __model,
                    join_multilines([stderr, stdout]),
                )
            )
        )
    return stdout


def qdevice_connected_clusters(status_cluster_text: str) -> list[str]:
    """
    parse qnetd cluster status listing and return connected clusters' names

    status_cluster_text -- output of corosync-qnetd-tool -l
    """
    connected_clusters = []
    regexp = re.compile(r'^Cluster "(?P<cluster>[^"]+)":$')
    for line in status_cluster_text.splitlines():
        match = regexp.search(line)
        if match:
            connected_clusters.append(match.group("cluster"))
    return connected_clusters


def _qdevice_run_tool(
    runner: CommandRunner, args: StringSequence
) -> tuple[str, str, int]:
    """
    run corosync-qnetd-tool, raise QnetdNotRunningException if qnetd not running

    iterable args -- corosync-qnetd-tool arguments
    """
    stdout, stderr, retval = runner.run([__qnetd_tool] + list(args))
    if retval == 3 and "is qnetd running?" in stderr.lower():
        raise QnetdNotRunningException()
    return stdout, stderr, retval


def qdevice_sign_certificate_request(
    runner: CommandRunner, cert_request: bytes, cluster_name: str
) -> bytes:
    """
    sign client certificate request

    cert_request -- certificate request data
    cluster_name -- name of the cluster to which qdevice is being added
    """
    if not qdevice_initialized():
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.QdeviceNotInitialized(__model)
            )
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
            reports.ReportItem.error(
                reports.messages.QdeviceCertificateSignError(
                    join_multilines([stderr, stdout]),
                )
            )
        )
    # get signed certificate, corosync tool only works with files
    return _get_output_certificate(
        stdout,
        reports.messages.QdeviceCertificateSignError,
    )


def client_setup(runner: CommandRunner, ca_certificate: bytes) -> None:
    """
    initialize qdevice client on local host

    ca_certificate -- qnetd CA certificate
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
            reports.ReportItem.error(
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
            reports.ReportItem.error(
                reports.messages.QdeviceInitializationError(
                    __model,
                    join_multilines([stderr, stdout]),
                )
            )
        )


def client_initialized() -> bool:
    """
    check if qdevice net client certificate database has been initialized
    """
    return _nss_certificate_db_initialized(
        settings.corosync_qdevice_net_client_certs_dir
    )


def client_destroy() -> None:
    """
    delete qdevice client config files on local host
    """
    try:
        if client_initialized():
            shutil.rmtree(settings.corosync_qdevice_net_client_certs_dir)
    except EnvironmentError as e:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.QdeviceDestroyError(__model, e.strerror)
            )
        ) from e


def client_generate_certificate_request(
    runner: CommandRunner, cluster_name: str
) -> bytes:
    """
    create a certificate request which can be signed by qnetd server

    cluster_name -- name of the cluster to which qdevice is being added
    """
    if not client_initialized():
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.QdeviceNotInitialized(__model)
            )
        )
    stdout, stderr, retval = runner.run(
        [__qdevice_certutil, "-r", "-n", cluster_name]
    )
    if retval != 0:
        raise LibraryError(
            reports.ReportItem.error(
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


def client_cert_request_to_pk12(
    runner: CommandRunner, cert_request: bytes
) -> bytes:
    """
    transform signed certificate request to pk12 certificate which can be
    imported to nodes

    cert_request -- signed certificate request
    """
    if not client_initialized():
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.QdeviceNotInitialized(__model)
            )
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
            reports.ReportItem.error(
                reports.messages.QdeviceCertificateImportError(
                    join_multilines([stderr, stdout]),
                )
            )
        )
    # get resulting pk12, corosync tool only works with files
    return _get_output_certificate(
        stdout, reports.messages.QdeviceCertificateImportError
    )


def client_import_certificate_and_key(
    runner: CommandRunner, pk12_certificate: bytes
) -> None:
    """
    import qdevice client certificate to the local node certificate storage
    """
    if not client_initialized():
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.QdeviceNotInitialized(__model)
            )
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
            reports.ReportItem.error(
                reports.messages.QdeviceCertificateImportError(
                    join_multilines([stderr, stdout]),
                )
            )
        )


def _nss_certificate_db_initialized(cert_db_path: str) -> bool:
    for filename in __nss_certificate_db_files:
        if os.path.exists(os.path.join(cert_db_path, filename)):
            return True
    return False


def _store_to_tmpfile(
    data: bytes, report_item_message: Callable[[str], reports.ReportItemMessage]
) -> IO[bytes]:
    try:
        return write_tmpfile(data, binary=True)
    except EnvironmentError as e:
        raise LibraryError(
            reports.ReportItem.error(report_item_message(e.strerror))
        ) from e


def _get_output_certificate(
    cert_tool_output: str,
    report_message_func: Callable[[str], reports.ReportItemMessage],
) -> bytes:
    regexp = re.compile(r"^Certificate( request)? stored in (?P<path>.+)$")
    filename = None
    for line in cert_tool_output.splitlines():
        match = regexp.search(line)
        if match:
            filename = match.group("path")
    if not filename:
        raise LibraryError(
            reports.ReportItem.error(report_message_func(cert_tool_output))
        )
    try:
        with open(filename, "rb") as cert_file:
            return cert_file.read()
    except EnvironmentError as e:
        raise LibraryError(
            reports.ReportItem.error(
                report_message_func(
                    "{path}: {error}".format(path=filename, error=e.strerror)
                )
            )
        ) from e
