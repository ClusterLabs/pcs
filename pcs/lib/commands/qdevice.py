from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import base64
import binascii

from pcs.lib import external, reports
from pcs.lib.corosync import qdevice_net
from pcs.lib.errors import LibraryError


def qdevice_setup(lib_env, model, enable, start):
    """
    Initialize qdevice on local host with specified model
    string model qdevice model to initialize
    bool enable make qdevice service start on boot
    bool start start qdevice now
    """
    _ensure_not_cman(lib_env)
    _check_model(model)
    qdevice_net.qdevice_setup(lib_env.cmd_runner())
    lib_env.report_processor.process(
        reports.qdevice_initialization_success(model)
    )
    if enable:
        _service_enable(lib_env, qdevice_net.qdevice_enable)
    if start:
        _service_start(lib_env, qdevice_net.qdevice_start)

def qdevice_destroy(lib_env, model):
    """
    Stop and disable qdevice on local host and remove its configuration
    string model qdevice model to initialize
    """
    _ensure_not_cman(lib_env)
    _check_model(model)
    _service_stop(lib_env, qdevice_net.qdevice_stop)
    _service_disable(lib_env, qdevice_net.qdevice_disable)
    qdevice_net.qdevice_destroy()
    lib_env.report_processor.process(reports.qdevice_destroy_success(model))

def qdevice_enable(lib_env, model):
    """
    make qdevice start automatically on boot on local host
    """
    _ensure_not_cman(lib_env)
    _check_model(model)
    _service_enable(lib_env, qdevice_net.qdevice_enable)

def qdevice_disable(lib_env, model):
    """
    make qdevice not start automatically on boot on local host
    """
    _ensure_not_cman(lib_env)
    _check_model(model)
    _service_disable(lib_env, qdevice_net.qdevice_disable)

def qdevice_start(lib_env, model):
    """
    start qdevice now on local host
    """
    _ensure_not_cman(lib_env)
    _check_model(model)
    _service_start(lib_env, qdevice_net.qdevice_start)

def qdevice_stop(lib_env, model):
    """
    stop qdevice now on local host
    """
    _ensure_not_cman(lib_env)
    _check_model(model)
    _service_stop(lib_env, qdevice_net.qdevice_stop)

def qdevice_kill(lib_env, model):
    """
    kill qdevice now on local host
    """
    _ensure_not_cman(lib_env)
    _check_model(model)
    _service_kill(lib_env, qdevice_net.qdevice_kill)

def qdevice_net_sign_certificate_request(
    lib_env, certificate_request, cluster_name
):
    """
    Sign node certificate request by qnetd CA
    string certificate_request base64 encoded certificate request
    string cluster_name name of the cluster to which qdevice is being added
    """
    _ensure_not_cman(lib_env)
    try:
        certificate_request_data = base64.b64decode(certificate_request)
    except (TypeError, binascii.Error):
        raise LibraryError(reports.invalid_option_value(
            "qnetd certificate request",
            certificate_request,
            ["base64 encoded certificate"]
        ))
    return base64.b64encode(
        qdevice_net.qdevice_sign_certificate_request(
            lib_env.cmd_runner(),
            certificate_request_data,
            cluster_name
        )
    )

def client_net_setup(lib_env, ca_certificate):
    """
    Intialize qdevice net client on local host
    ca_certificate base64 encoded qnetd CA certificate
    """
    _ensure_not_cman(lib_env)
    try:
        ca_certificate_data = base64.b64decode(ca_certificate)
    except (TypeError, binascii.Error):
        raise LibraryError(reports.invalid_option_value(
            "qnetd CA certificate",
            ca_certificate,
            ["base64 encoded certificate"]
        ))
    qdevice_net.client_setup(lib_env.cmd_runner(), ca_certificate_data)

def client_net_import_certificate(lib_env, certificate):
    """
    Import qnetd client certificate to local node certificate storage
    certificate base64 encoded qnetd client certificate
    """
    _ensure_not_cman(lib_env)
    try:
        certificate_data = base64.b64decode(certificate)
    except (TypeError, binascii.Error):
        raise LibraryError(reports.invalid_option_value(
            "qnetd client certificate",
            certificate,
            ["base64 encoded certificate"]
        ))
    qdevice_net.client_import_certificate_and_key(
        lib_env.cmd_runner(),
        certificate_data
    )

def client_net_destroy(lib_env):
    """
    delete qdevice client config files on local host
    """
    _ensure_not_cman(lib_env)
    qdevice_net.client_destroy()

def _ensure_not_cman(lib_env):
    if lib_env.is_cman_cluster:
        raise LibraryError(reports.cman_unsupported_command())

def _check_model(model):
    if model != "net":
        raise LibraryError(
            reports.invalid_option_value("model", model, ["net"])
        )

def _service_start(lib_env, func):
    lib_env.report_processor.process(
        reports.service_start_started("quorum device")
    )
    try:
        func(lib_env.cmd_runner())
    except external.StartServiceError as e:
        raise LibraryError(
            reports.service_start_error(e.service, e.message)
        )
    lib_env.report_processor.process(
        reports.service_start_success("quorum device")
    )

def _service_stop(lib_env, func):
    lib_env.report_processor.process(
        reports.service_stop_started("quorum device")
    )
    try:
        func(lib_env.cmd_runner())
    except external.StopServiceError as e:
        raise LibraryError(
            reports.service_stop_error(e.service, e.message)
        )
    lib_env.report_processor.process(
        reports.service_stop_success("quorum device")
    )

def _service_kill(lib_env, func):
    try:
        func(lib_env.cmd_runner())
    except external.KillServicesError as e:
        raise LibraryError(
            reports.service_kill_error(e.service, e.message)
        )
    lib_env.report_processor.process(
        reports.service_kill_success(["quorum device"])
    )

def _service_enable(lib_env, func):
    try:
        func(lib_env.cmd_runner())
    except external.EnableServiceError as e:
        raise LibraryError(
            reports.service_enable_error(e.service, e.message)
        )
    lib_env.report_processor.process(
        reports.service_enable_success("quorum device")
    )

def _service_disable(lib_env, func):
    try:
        func(lib_env.cmd_runner())
    except external.DisableServiceError as e:
        raise LibraryError(
            reports.service_disable_error(e.service, e.message)
        )
    lib_env.report_processor.process(
        reports.service_disable_success("quorum device")
    )
