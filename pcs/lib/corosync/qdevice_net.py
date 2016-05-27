from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os.path
import shutil

from pcs import settings
from pcs.lib import external, reports
from pcs.lib.errors import LibraryError


__model = "net"
__service_name = "corosync-qnetd"

def qdevice_setup(runner):
    """
    initialize qdevice on local host
    """
    if external.is_dir_nonempty(settings.corosync_qdevice_net_server_certs_dir):
        raise LibraryError(reports.qdevice_already_initialized(__model))

    output, retval = runner.run([
        os.path.join(settings.corosync_binaries, "corosync-qnetd-certutil"),
        "-i"
    ])
    if retval != 0:
        raise LibraryError(
            reports.qdevice_initialization_error(__model, output.rstrip())
        )

def qdevice_destroy():
    """
    delete qdevice configuration on local host
    """
    try:
        shutil.rmtree(settings.corosync_qdevice_net_server_certs_dir)
    except EnvironmentError as e:
        raise LibraryError(
            reports.qdevice_destroy_error(__model, e.strerror)
        )

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
