import base64
import binascii
import os.path
from typing import List

from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.file import RawFileError
from pcs.common.reports import ReportProcessor
from pcs.common.reports import codes as report_codes
from pcs.common.reports.item import (
    ReportItem,
    get_severity,
)
from pcs.common.services.errors import ManageServiceError
from pcs.common.services.interfaces import ServiceManagerInterface
from pcs.common.tools import format_os_error
from pcs.lib import external
from pcs.lib.corosync import qdevice_net
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.services import service_exception_to_report


def qdevice_setup(lib_env: LibraryEnvironment, model, enable, start):
    """
    Initialize qdevice on local host with specified model

    string model -- qdevice model to initialize
    bool enable -- make qdevice service start on boot
    bool start -- start qdevice now
    """
    _check_model(model)
    qdevice_net.qdevice_setup(lib_env.cmd_runner())
    report_processor = lib_env.report_processor
    service_manager = lib_env.service_manager
    report_processor.report(
        ReportItem.info(reports.messages.QdeviceInitializationSuccess(model))
    )
    if enable:
        _service_enable(
            report_processor, service_manager, qdevice_net.SERVICE_NAME
        )
    if start:
        _service_start(
            report_processor, service_manager, qdevice_net.SERVICE_NAME
        )


def qdevice_destroy(lib_env: LibraryEnvironment, model, proceed_if_used=False):
    """
    Stop and disable qdevice on local host and remove its configuration

    string model -- qdevice model to destroy
    bool procced_if_used -- destroy qdevice even if it is used by clusters
    """
    _check_model(model)
    report_processor = lib_env.report_processor
    service_manager = lib_env.service_manager
    _check_qdevice_not_used(
        report_processor, lib_env.cmd_runner(), model, proceed_if_used
    )
    _service_stop(report_processor, service_manager, qdevice_net.SERVICE_NAME)
    _service_disable(
        report_processor, service_manager, qdevice_net.SERVICE_NAME
    )
    qdevice_net.qdevice_destroy()
    report_processor.report(
        ReportItem.info(reports.messages.QdeviceDestroySuccess(model))
    )


def qdevice_status_text(
    lib_env: LibraryEnvironment,
    model,
    verbose=False,
    cluster=None,
):
    """
    Get runtime status of a quorum device in plain text

    string model -- qdevice model to query
    bool verbose -- get more detailed output
    string cluster -- show information only about specified cluster
    """
    _check_model(model)
    runner = lib_env.cmd_runner()
    try:
        return qdevice_net.qdevice_status_generic_text(
            runner, verbose
        ) + qdevice_net.qdevice_status_cluster_text(runner, cluster, verbose)
    except qdevice_net.QnetdNotRunningException as e:
        raise LibraryError(
            ReportItem.error(reports.messages.QdeviceNotRunning(model))
        ) from e


def qdevice_enable(lib_env: LibraryEnvironment, model):
    """
    make qdevice start automatically on boot on local host
    """
    _check_model(model)
    _service_enable(
        lib_env.report_processor,
        lib_env.service_manager,
        qdevice_net.SERVICE_NAME,
    )


def qdevice_disable(lib_env: LibraryEnvironment, model):
    """
    make qdevice not start automatically on boot on local host
    """
    _check_model(model)
    _service_disable(
        lib_env.report_processor,
        lib_env.service_manager,
        qdevice_net.SERVICE_NAME,
    )


def qdevice_start(lib_env: LibraryEnvironment, model):
    """
    start qdevice now on local host
    """
    _check_model(model)
    if not qdevice_net.qdevice_initialized():
        raise LibraryError(
            ReportItem.error(reports.messages.QdeviceNotInitialized(model))
        )
    _service_start(
        lib_env.report_processor,
        lib_env.service_manager,
        qdevice_net.SERVICE_NAME,
    )


def qdevice_stop(lib_env: LibraryEnvironment, model, proceed_if_used=False):
    """
    stop qdevice now on local host

    string model -- qdevice model to destroy
    bool procced_if_used -- stop qdevice even if it is used by clusters
    """
    _check_model(model)
    _check_qdevice_not_used(
        lib_env.report_processor, lib_env.cmd_runner(), model, proceed_if_used
    )
    _service_stop(
        lib_env.report_processor,
        lib_env.service_manager,
        qdevice_net.SERVICE_NAME,
    )


def qdevice_kill(lib_env: LibraryEnvironment, model):
    """
    kill qdevice now on local host
    """
    _check_model(model)
    _service_kill(lib_env, qdevice_net.SERVICE_NAME)


def qdevice_net_get_ca_certificate(lib_env: LibraryEnvironment) -> bytes:
    """
    get base64 encoded qnetd CA certificate
    """
    path = os.path.join(
        settings.corosync_qdevice_net_server_certs_dir,
        settings.corosync_qdevice_net_server_ca_file_name,
    )
    try:
        with open(path, "rb") as cert_file:
            return base64.b64encode(cert_file.read())
    except OSError as e:
        lib_env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.FileIoError(
                    file_type_codes.COROSYNC_QNETD_CA_CERT,
                    RawFileError.ACTION_READ,
                    format_os_error(e),
                    path,
                )
            )
        )
        raise LibraryError() from e


def qdevice_net_sign_certificate_request(
    lib_env: LibraryEnvironment,
    certificate_request: str,
    cluster_name: str,
) -> bytes:
    """
    Sign node certificate request by qnetd CA

    certificate_request -- base64 encoded certificate request
    cluster_name -- name of the cluster to which qdevice is being added
    """
    try:
        certificate_request_data = base64.b64decode(certificate_request)
    except (TypeError, binascii.Error) as e:
        raise LibraryError(
            ReportItem.error(
                reports.messages.InvalidOptionValue(
                    "qnetd certificate request",
                    certificate_request,
                    ["base64 encoded certificate"],
                )
            )
        ) from e
    return base64.b64encode(
        qdevice_net.qdevice_sign_certificate_request(
            lib_env.cmd_runner(), certificate_request_data, cluster_name
        )
    )


def client_net_setup(lib_env: LibraryEnvironment, ca_certificate: str) -> None:
    """
    Initialize qdevice net client on local host

    ca_certificate -- base64 encoded qnetd CA certificate
    """
    try:
        ca_certificate_data = base64.b64decode(ca_certificate)
    except (TypeError, binascii.Error) as e:
        raise LibraryError(
            ReportItem.error(
                reports.messages.InvalidOptionValue(
                    "qnetd CA certificate",
                    ca_certificate,
                    ["base64 encoded certificate"],
                )
            )
        ) from e
    qdevice_net.client_setup(lib_env.cmd_runner(), ca_certificate_data)


def client_net_import_certificate(
    lib_env: LibraryEnvironment, certificate: str
) -> None:
    """
    Import qnetd client certificate to local node certificate storage

    certificate -- base64 encoded qnetd client certificate
    """
    try:
        certificate_data = base64.b64decode(certificate)
    except (TypeError, binascii.Error) as e:
        raise LibraryError(
            ReportItem.error(
                reports.messages.InvalidOptionValue(
                    "qnetd client certificate",
                    certificate,
                    ["base64 encoded certificate"],
                )
            )
        ) from e
    qdevice_net.client_import_certificate_and_key(
        lib_env.cmd_runner(), certificate_data
    )


def client_net_destroy(lib_env: LibraryEnvironment) -> None:
    """
    delete qdevice client config files on local host
    """
    del lib_env
    qdevice_net.client_destroy()


def _check_model(model):
    if model != "net":
        raise LibraryError(
            ReportItem.error(
                reports.messages.InvalidOptionValue("model", model, ["net"])
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
                severity=get_severity(report_codes.FORCE, force),
                message=reports.messages.QdeviceUsedByClusters(
                    connected_clusters,
                ),
            )
        )
        if reporter.has_errors:
            raise LibraryError()


def _service_start(
    report_processor: ReportProcessor,
    service_manager: ServiceManagerInterface,
    service: str,
) -> None:
    report_processor.report(
        ReportItem.info(
            reports.messages.ServiceActionStarted(
                reports.const.SERVICE_ACTION_START, "quorum device"
            )
        )
    )
    try:
        service_manager.start(service)
    except ManageServiceError as e:
        raise LibraryError(service_exception_to_report(e)) from e
    report_processor.report(
        ReportItem.info(
            reports.messages.ServiceActionSucceeded(
                reports.const.SERVICE_ACTION_START,
                "quorum device",
            )
        )
    )


def _service_stop(
    report_processor: ReportProcessor,
    service_manager: ServiceManagerInterface,
    service: str,
) -> None:
    report_processor.report(
        ReportItem.info(
            reports.messages.ServiceActionStarted(
                reports.const.SERVICE_ACTION_STOP, "quorum device"
            )
        )
    )
    try:
        service_manager.stop(service)
    except ManageServiceError as e:
        raise LibraryError(service_exception_to_report(e)) from e
    report_processor.report(
        ReportItem.info(
            reports.messages.ServiceActionSucceeded(
                reports.const.SERVICE_ACTION_STOP, "quorum device"
            )
        )
    )


def _service_kill(lib_env: LibraryEnvironment, service: str) -> None:
    try:
        external.kill_services(lib_env.cmd_runner(), [service])
    except external.KillServicesError as e:
        raise LibraryError(
            *[
                ReportItem.error(
                    reports.messages.ServiceActionFailed(
                        reports.const.SERVICE_ACTION_KILL, service, e.message
                    )
                )
                for service in e.service
            ]
        ) from e
    lib_env.report_processor.report(
        ReportItem.info(
            reports.messages.ServiceActionSucceeded(
                reports.const.SERVICE_ACTION_KILL, "quorum device"
            )
        )
    )


def _service_enable(
    report_processor: ReportProcessor,
    service_manager: ServiceManagerInterface,
    service: str,
) -> None:
    try:
        service_manager.enable(service)
    except ManageServiceError as e:
        raise LibraryError(service_exception_to_report(e)) from e
    report_processor.report(
        ReportItem.info(
            reports.messages.ServiceActionSucceeded(
                reports.const.SERVICE_ACTION_ENABLE, "quorum device"
            )
        )
    )


def _service_disable(
    report_processor: ReportProcessor,
    service_manager: ServiceManagerInterface,
    service: str,
) -> None:
    try:
        service_manager.disable(service)
    except ManageServiceError as e:
        raise LibraryError(service_exception_to_report(e)) from e
    report_processor.report(
        ReportItem.info(
            reports.messages.ServiceActionSucceeded(
                reports.const.SERVICE_ACTION_DISABLE, "quorum device"
            )
        )
    )
