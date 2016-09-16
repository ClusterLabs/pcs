from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import base64
import binascii
import functools
import os
import os.path
import re
import shutil
import tempfile

from pcs import settings
from pcs.common.tools import join_multilines
from pcs.lib import external, reports
from pcs.lib.errors import LibraryError


__model = "net"
__service_name = "corosync-qnetd"
__qnetd_certutil = os.path.join(
    settings.corosync_qnet_binaries,
    "corosync-qnetd-certutil"
)
__qnetd_tool = os.path.join(
    settings.corosync_qnet_binaries,
    "corosync-qnetd-tool"
)
__qdevice_certutil = os.path.join(
    settings.corosync_binaries,
    "corosync-qdevice-net-certutil"
)

class QnetdNotRunningException(Exception):
    pass

def qdevice_setup(runner):
    """
    initialize qdevice on local host
    """
    if external.is_dir_nonempty(settings.corosync_qdevice_net_server_certs_dir):
        raise LibraryError(reports.qdevice_already_initialized(__model))

    stdout, stderr, retval = runner.run([
        __qnetd_certutil, "-i"
    ])
    if retval != 0:
        raise LibraryError(
            reports.qdevice_initialization_error(
                __model,
                join_multilines([stderr, stdout])
            )
        )

def qdevice_initialized():
    """
    check if qdevice server certificate database has been initialized
    """
    return os.path.exists(os.path.join(
        settings.corosync_qdevice_net_server_certs_dir,
        "cert8.db"
    ))

def qdevice_destroy():
    """
    delete qdevice configuration on local host
    """
    try:
        if qdevice_initialized():
            shutil.rmtree(settings.corosync_qdevice_net_server_certs_dir)
    except EnvironmentError as e:
        raise LibraryError(
            reports.qdevice_destroy_error(__model, e.strerror)
        )

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
            reports.qdevice_get_status_error(
                __model,
                join_multilines([stderr, stdout])
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
            reports.qdevice_get_status_error(
                __model,
                join_multilines([stderr, stdout])
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
        raise LibraryError(reports.qdevice_not_initialized(__model))
    # save the certificate request, corosync tool only works with files
    tmpfile = _store_to_tmpfile(
        cert_request,
        reports.qdevice_certificate_sign_error
    )
    # sign the request
    stdout, stderr, retval = runner.run([
        __qnetd_certutil, "-s", "-c", tmpfile.name, "-n", cluster_name
    ])
    tmpfile.close() # temp file is deleted on close
    if retval != 0:
        raise LibraryError(
            reports.qdevice_certificate_sign_error(
                join_multilines([stderr, stdout])
            )
        )
    # get signed certificate, corosync tool only works with files
    return _get_output_certificate(
        stdout,
        reports.qdevice_certificate_sign_error
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
        settings.corosync_qdevice_net_client_ca_file_name
    )
    try:
        if not os.path.exists(ca_file_path):
            os.makedirs(
                settings.corosync_qdevice_net_client_certs_dir,
                mode=0o700
            )
        with open(ca_file_path, "wb") as ca_file:
            ca_file.write(ca_certificate)
    except EnvironmentError as e:
        raise LibraryError(
            reports.qdevice_initialization_error(__model, e.strerror)
        )
    # initialize client's certificate storage
    stdout, stderr, retval = runner.run([
        __qdevice_certutil, "-i", "-c", ca_file_path
    ])
    if retval != 0:
        raise LibraryError(
            reports.qdevice_initialization_error(
                __model,
                join_multilines([stderr, stdout])
            )
        )

def client_initialized():
    """
    check if qdevice net client certificate database has been initialized
    """
    return os.path.exists(os.path.join(
        settings.corosync_qdevice_net_client_certs_dir,
        "cert8.db"
    ))

def client_destroy():
    """
    delete qdevice client config files on local host
    """
    try:
        if client_initialized():
            shutil.rmtree(settings.corosync_qdevice_net_client_certs_dir)
    except EnvironmentError as e:
        raise LibraryError(
            reports.qdevice_destroy_error(__model, e.strerror)
        )

def client_generate_certificate_request(runner, cluster_name):
    """
    create a certificate request which can be signed by qnetd server
    string cluster_name name of the cluster to which qdevice is being added
    """
    if not client_initialized():
        raise LibraryError(reports.qdevice_not_initialized(__model))
    stdout, stderr, retval = runner.run([
        __qdevice_certutil, "-r", "-n", cluster_name
    ])
    if retval != 0:
        raise LibraryError(
            reports.qdevice_initialization_error(
                __model,
                join_multilines([stderr, stdout])
            )
        )
    return _get_output_certificate(
        stdout,
        functools.partial(reports.qdevice_initialization_error, __model)
    )

def client_cert_request_to_pk12(runner, cert_request):
    """
    transform signed certificate request to pk12 certificate which can be
    imported to nodes
    cert_request signed certificate request
    """
    if not client_initialized():
        raise LibraryError(reports.qdevice_not_initialized(__model))
    # save the signed certificate request, corosync tool only works with files
    tmpfile = _store_to_tmpfile(
        cert_request,
        reports.qdevice_certificate_import_error
    )
    # transform it
    stdout, stderr, retval = runner.run([
        __qdevice_certutil, "-M", "-c", tmpfile.name
    ])
    tmpfile.close() # temp file is deleted on close
    if retval != 0:
        raise LibraryError(
            reports.qdevice_certificate_import_error(
                join_multilines([stderr, stdout])
            )
        )
    # get resulting pk12, corosync tool only works with files
    return _get_output_certificate(
        stdout,
        reports.qdevice_certificate_import_error
    )

def client_import_certificate_and_key(runner, pk12_certificate):
    """
    import qdevice client certificate to the local node certificate storage
    """
    if not client_initialized():
        raise LibraryError(reports.qdevice_not_initialized(__model))
    # save the certificate, corosync tool only works with files
    tmpfile = _store_to_tmpfile(
        pk12_certificate,
        reports.qdevice_certificate_import_error
    )
    stdout, stderr, retval = runner.run([
        __qdevice_certutil, "-m", "-c", tmpfile.name
    ])
    tmpfile.close() # temp file is deleted on close
    if retval != 0:
        raise LibraryError(
            reports.qdevice_certificate_import_error(
                join_multilines([stderr, stdout])
            )
        )

def remote_qdevice_get_ca_certificate(node_communicator, host):
    """
    connect to a qnetd host and get qnetd CA certificate
    string host address of the qnetd host
    """
    try:
        return base64.b64decode(
            node_communicator.call_host(
                host,
                "remote/qdevice_net_get_ca_certificate",
                None
            )
        )
    except (TypeError, binascii.Error):
        raise LibraryError(reports.invalid_response_format(host))

def remote_client_setup(node_communicator, node, qnetd_ca_certificate):
    """
    connect to a remote node and initialize qdevice there
    NodeAddresses node target node
    qnetd_ca_certificate qnetd CA certificate
    """
    return node_communicator.call_node(
        node,
        "remote/qdevice_net_client_init_certificate_storage",
        external.NodeCommunicator.format_data_dict([
            ("ca_certificate", base64.b64encode(qnetd_ca_certificate)),
        ])
    )

def remote_sign_certificate_request(
    node_communicator, host, cert_request, cluster_name
):
    """
    connect to a qdevice host and sign node certificate there
    string host address of the qnetd host
    cert_request certificate request to be signed
    string cluster_name name of the cluster to which qdevice is being added
    """
    try:
        return base64.b64decode(
            node_communicator.call_host(
                host,
                "remote/qdevice_net_sign_node_certificate",
                external.NodeCommunicator.format_data_dict([
                    ("certificate_request", base64.b64encode(cert_request)),
                    ("cluster_name", cluster_name),
                ])
            )
        )
    except (TypeError, binascii.Error):
        raise LibraryError(reports.invalid_response_format(host))

def remote_client_import_certificate_and_key(node_communicator, node, pk12):
    """
    import pk12 certificate on a remote node
    NodeAddresses node target node
    pk12 certificate
    """
    return node_communicator.call_node(
        node,
        "remote/qdevice_net_client_import_certificate",
        external.NodeCommunicator.format_data_dict([
            ("certificate", base64.b64encode(pk12)),
        ])
    )

def remote_client_destroy(node_communicator, node):
    """
    delete qdevice client config files on a remote node
    NodeAddresses node target node
    """
    return node_communicator.call_node(
        node,
        "remote/qdevice_net_client_destroy",
        None
    )

def _store_to_tmpfile(data, report_func):
    try:
        tmpfile = tempfile.NamedTemporaryFile(mode="wb", suffix=".pcs")
        tmpfile.write(data)
        tmpfile.flush()
        return tmpfile
    except EnvironmentError as e:
        raise LibraryError(report_func(e.strerror))

def _get_output_certificate(cert_tool_output, report_func):
    regexp = re.compile(r"^Certificate( request)? stored in (?P<path>.+)$")
    filename = None
    for line in cert_tool_output.splitlines():
        match = regexp.search(line)
        if match:
            filename = match.group("path")
    if not filename:
        raise LibraryError(report_func(cert_tool_output))
    try:
        with open(filename, "rb") as cert_file:
            return cert_file.read()
    except EnvironmentError as e:
        raise LibraryError(report_func(
            "{path}: {error}".format(path=filename, error=e.strerror)
        ))
