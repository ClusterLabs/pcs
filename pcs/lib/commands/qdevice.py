from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

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
    _check_model(model)
    _service_stop(lib_env, qdevice_net.qdevice_stop)
    _service_disable(lib_env, qdevice_net.qdevice_disable)
    qdevice_net.qdevice_destroy()
    lib_env.report_processor.process(reports.qdevice_destroy_success(model))

def qdevice_enable(lib_env, model):
    """
    make qdevice start automatically on boot on local host
    """
    _check_model(model)
    _service_enable(lib_env, qdevice_net.qdevice_enable)

def qdevice_disable(lib_env, model):
    """
    make qdevice not start automatically on boot on local host
    """
    _check_model(model)
    _service_disable(lib_env, qdevice_net.qdevice_disable)

def qdevice_start(lib_env, model):
    """
    start qdevice now on local host
    """
    _check_model(model)
    _service_start(lib_env, qdevice_net.qdevice_start)

def qdevice_stop(lib_env, model):
    """
    stop qdevice now on local host
    """
    _check_model(model)
    _service_stop(lib_env, qdevice_net.qdevice_stop)

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
