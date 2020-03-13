import base64
import binascii
from typing import List

from pcs.common import reports as report
from pcs.common.reports import (
    codes as report_codes,
    ReportProcessor,
)
from pcs.common.reports.item import (
    get_severity,
    ReportItem,
)
from pcs.lib import external, reports
from pcs.lib.corosync import qdevice_net
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError


def qdevice_setup(lib_env: LibraryEnvironment, model, enable, start):
    """
    Initialize qdevice on local host with specified model
    string model qdevice model to initialize
    bool enable make qdevice service start on boot
    bool start start qdevice now
    """
    _check_model(model)
    qdevice_net.qdevice_setup(lib_env.cmd_runner())
    lib_env.report_processor.report(
        ReportItem.info(report.messages.QdeviceInitializationSuccess(model))
    )
    if enable:
        _service_enable(lib_env, qdevice_net.qdevice_enable)
    if start:
        _service_start(lib_env, qdevice_net.qdevice_start)

def qdevice_destroy(lib_env: LibraryEnvironment, model, proceed_if_used=False):
    """
    Stop and disable qdevice on local host and remove its configuration
    string model qdevice model to destroy
    bool procced_if_used destroy qdevice even if it is used by clusters
    """
    _check_model(model)
    _check_qdevice_not_used(
        lib_env.report_processor,
        lib_env.cmd_runner(),
        model,
        proceed_if_used
    )
    _service_stop(lib_env, qdevice_net.qdevice_stop)
    _service_disable(lib_env, qdevice_net.qdevice_disable)
    qdevice_net.qdevice_destroy()
    lib_env.report_processor.report(
        ReportItem.info(report.messages.QdeviceDestroySuccess(model))
    )

def qdevice_status_text(
    lib_env: LibraryEnvironment,
    model,
    verbose=False,
    cluster=None,
):
    """
    Get runtime status of a quorum device in plain text
    string model qdevice model to query
    bool verbose get more detailed output
    string cluster show information only about specified cluster
    """
    _check_model(model)
    runner = lib_env.cmd_runner()
    try:
        return (
            qdevice_net.qdevice_status_generic_text(runner, verbose)
            +
            qdevice_net.qdevice_status_cluster_text(runner, cluster, verbose)
        )
    except qdevice_net.QnetdNotRunningException:
        raise LibraryError(
            ReportItem.error(report.messages.QdeviceNotRunning(model))
        )

def qdevice_enable(lib_env: LibraryEnvironment, model):
    """
    make qdevice start automatically on boot on local host
    """
    _check_model(model)
    _service_enable(lib_env, qdevice_net.qdevice_enable)

def qdevice_disable(lib_env: LibraryEnvironment, model):
    """
    make qdevice not start automatically on boot on local host
    """
    _check_model(model)
    _service_disable(lib_env, qdevice_net.qdevice_disable)

def qdevice_start(lib_env: LibraryEnvironment, model):
    """
    start qdevice now on local host
    """
    _check_model(model)
    if not qdevice_net.qdevice_initialized():
        raise LibraryError(
            ReportItem.error(
                report.messages.QdeviceNotInitialized(model)
            )
        )
    _service_start(lib_env, qdevice_net.qdevice_start)

def qdevice_stop(lib_env: LibraryEnvironment, model, proceed_if_used=False):
    """
    stop qdevice now on local host
    string model qdevice model to destroy
    bool procced_if_used stop qdevice even if it is used by clusters
    """
    _check_model(model)
    _check_qdevice_not_used(
        lib_env.report_processor,
        lib_env.cmd_runner(),
        model,
        proceed_if_used
    )
    _service_stop(lib_env, qdevice_net.qdevice_stop)

def qdevice_kill(lib_env: LibraryEnvironment, model):
    """
    kill qdevice now on local host
    """
    _check_model(model)
    _service_kill(lib_env, qdevice_net.qdevice_kill)

def qdevice_net_sign_certificate_request(
    lib_env: LibraryEnvironment,
    certificate_request,
    cluster_name,
):
    """
    Sign node certificate request by qnetd CA
    string certificate_request base64 encoded certificate request
    string cluster_name name of the cluster to which qdevice is being added
    """
    try:
        certificate_request_data = base64.b64decode(certificate_request)
    except (TypeError, binascii.Error):
        raise LibraryError(
            ReportItem.error(
                report.messages.InvalidOptionValue(
                    "qnetd certificate request",
                    certificate_request,
                    ["base64 encoded certificate"]
                )
            )
        )
    return base64.b64encode(
        qdevice_net.qdevice_sign_certificate_request(
            lib_env.cmd_runner(),
            certificate_request_data,
            cluster_name
        )
    )

def client_net_setup(lib_env: LibraryEnvironment, ca_certificate):
    """
    Intialize qdevice net client on local host
    ca_certificate base64 encoded qnetd CA certificate
    """
    try:
        ca_certificate_data = base64.b64decode(ca_certificate)
    except (TypeError, binascii.Error):
        raise LibraryError(
            ReportItem.error(
                report.messages.InvalidOptionValue(
                "qnetd CA certificate",
                ca_certificate,
                ["base64 encoded certificate"]
                )
            )
        )
    qdevice_net.client_setup(lib_env.cmd_runner(), ca_certificate_data)

def client_net_import_certificate(lib_env: LibraryEnvironment, certificate):
    """
    Import qnetd client certificate to local node certificate storage
    certificate base64 encoded qnetd client certificate
    """
    try:
        certificate_data = base64.b64decode(certificate)
    except (TypeError, binascii.Error):
        raise LibraryError(
            ReportItem.error(
                report.messages.InvalidOptionValue(
                    "qnetd client certificate",
                    certificate,
                    ["base64 encoded certificate"]
                )
            )
        )
    qdevice_net.client_import_certificate_and_key(
        lib_env.cmd_runner(),
        certificate_data
    )

def client_net_destroy(lib_env: LibraryEnvironment):
    # pylint: disable=unused-argument
    """
    delete qdevice client config files on local host
    """
    qdevice_net.client_destroy()

def _check_model(model):
    if model != "net":
        raise LibraryError(
            ReportItem.error(
                report.messages.InvalidOptionValue("model", model, ["net"])
            )
        )

def _check_qdevice_not_used(
    reporter: ReportProcessor, runner, model, force=False
):
    _check_model(model)
    connected_clusters: List[str] = []
    if model == "net":
        try:
            status = qdevice_net.qdevice_status_cluster_text(runner)
            connected_clusters = qdevice_net.qdevice_connected_clusters(status)
        except qdevice_net.QnetdNotRunningException:
            pass
    if connected_clusters:
        reporter.report(
            ReportItem(
                severity=get_severity(report_codes.FORCE_QDEVICE_USED, force),
                message=report.messages.QdeviceUsedByClusters(
                    connected_clusters,
                )
            )
        )
        if reporter.has_errors:
            raise LibraryError()

def _service_start(lib_env: LibraryEnvironment, func):
    lib_env.report_processor.report(
        ReportItem.info(
            report.messages.ServiceActionStarted(
                report.messages.SERVICE_START, "quorum device"
            )
        )
    )
    try:
        func(lib_env.cmd_runner())
    except external.StartServiceError as e:
        raise LibraryError(
            ReportItem.error(
                report.messages.ServiceActionFailed(
                    report.messages.SERVICE_START, e.service, e.message
                )
            )
        )
    lib_env.report_processor.report(
        ReportItem.info(
            report.messages.ServiceActionSucceeded(
                report.messages.SERVICE_START, "quorum device",
            )
        )
    )

def _service_stop(lib_env: LibraryEnvironment, func):
    lib_env.report_processor.report(
        ReportItem.info(
            report.messages.ServiceActionStarted(
                report.messages.SERVICE_STOP, "quorum device"
            )
        )
    )
    try:
        func(lib_env.cmd_runner())
    except external.StopServiceError as e:
        raise LibraryError(
            ReportItem.error(
                report.messages.ServiceActionFailed(
                    report.messages.SERVICE_STOP, e.service, e.message
                )
            )
        )
    lib_env.report_processor.report(
        ReportItem.info(
            report.messages.ServiceActionSucceeded(
                report.messages.SERVICE_STOP, "quorum device"
            )
        )
    )

def _service_kill(lib_env: LibraryEnvironment, func):
    try:
        func(lib_env.cmd_runner())
    except external.KillServicesError as e:
        raise LibraryError(
            *[
                ReportItem.error(
                    report.messages.ServiceActionFailed(
                        report.messages.SERVICE_KILL, service, e.message
                    )
                )
                for service in e.service
            ]
        )
    lib_env.report_processor.report(
        ReportItem.info(
            report.messages.ServiceActionSucceeded(
                report.messages.SERVICE_KILL, "quorum device"
            )
        )
    )

def _service_enable(lib_env: LibraryEnvironment, func):
    try:
        func(lib_env.cmd_runner())
    except external.EnableServiceError as e:
        raise LibraryError(
            ReportItem.error(
                report.messages.ServiceActionFailed(
                    report.messages.SERVICE_ENABLE,
                    e.service,
                    e.message,
                )
            )
        )
    lib_env.report_processor.report(
        ReportItem.info(
            report.messages.ServiceActionSucceeded(
                report.messages.SERVICE_ENABLE, "quorum device"
            )
        )
    )

def _service_disable(lib_env: LibraryEnvironment, func):
    try:
        func(lib_env.cmd_runner())
    except external.DisableServiceError as e:
        raise LibraryError(
            ReportItem.error(
                report.messages.ServiceActionFailed(
                    report.messages.SERVICE_DISABLE,
                    e.service,
                    e.message,
                )
            )
        )
    lib_env.report_processor.report(
        ReportItem.info(
            report.messages.ServiceActionSucceeded(
                report.messages.SERVICE_DISABLE, "quorum device"
            )
        )
    )
