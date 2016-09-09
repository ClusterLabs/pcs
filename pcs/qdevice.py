from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys

from pcs import (
    usage,
    utils,
)
from pcs.cli.common.errors import CmdLineInputError
from pcs.lib.errors import LibraryError

def qdevice_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        usage.qdevice()
        sys.exit(1)

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "help":
            usage.qdevice(argv)
        elif sub_cmd == "status":
            qdevice_status_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "setup":
            qdevice_setup_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "destroy":
            qdevice_destroy_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "start":
            qdevice_start_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "stop":
            qdevice_stop_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "kill":
            qdevice_kill_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "enable":
            qdevice_enable_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "disable":
            qdevice_disable_cmd(lib, argv_next, modifiers)
        # following commands are internal use only, called from pcsd
        elif sub_cmd == "sign-net-cert-request":
            qdevice_sign_net_cert_request_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "net-client":
            qdevice_net_client_cmd(lib, argv_next, modifiers)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "qdevice", sub_cmd)

# this is internal use only, called from pcsd
def qdevice_net_client_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        utils.err("invalid command")

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "setup":
            qdevice_net_client_setup_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "import-certificate":
            qdevice_net_client_import_certificate_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "destroy":
            qdevice_net_client_destroy(lib, argv_next, modifiers)
        else:
            raise CmdLineInputError("invalid command")
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.err(e.message)

def qdevice_status_cmd(lib, argv, modifiers):
    if len(argv) < 1 or len(argv) > 2:
        raise CmdLineInputError()
    model = argv[0]
    cluster = None if len(argv) < 2 else argv[1]
    print(
        lib.qdevice.status(model, modifiers["full"], cluster)
    )

def qdevice_setup_cmd(lib, argv, modifiers):
    if len(argv) != 2:
        raise CmdLineInputError()
    if argv[0] != "model":
        raise CmdLineInputError()
    model = argv[1]
    lib.qdevice.setup(model, modifiers["enable"], modifiers["start"])

def qdevice_destroy_cmd(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.destroy(model, modifiers["force"])

def qdevice_start_cmd(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.start(model)

def qdevice_stop_cmd(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.stop(model, modifiers["force"])

def qdevice_kill_cmd(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.kill(model)

def qdevice_enable_cmd(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.enable(model)

def qdevice_disable_cmd(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.disable(model)

# following commands are internal use only, called from pcsd

def qdevice_net_client_setup_cmd(lib, argv, modifiers):
    ca_certificate = _read_stdin()
    lib.qdevice.client_net_setup(ca_certificate)

def qdevice_net_client_import_certificate_cmd(lib, argv, modifiers):
    certificate = _read_stdin()
    lib.qdevice.client_net_import_certificate(certificate)

def qdevice_net_client_destroy(lib, argv, modifiers):
    lib.qdevice.client_net_destroy()

def qdevice_sign_net_cert_request_cmd(lib, argv, modifiers):
    certificate_request = _read_stdin()
    signed = lib.qdevice.sign_net_cert_request(
        certificate_request,
        modifiers["name"]
    )
    if sys.version_info.major > 2:
        # In python3 base64.b64encode returns bytes.
        # In python2 base64.b64encode returns string.
        # Bytes is printed like this: b'bytes content'
        # and we need to get rid of that b'', so we change bytes to string.
        # Since it's base64encoded, it's safe to use ascii.
        signed = signed.decode("ascii")
    print(signed)

def _read_stdin():
    # in python3 stdin returns str so we need to use buffer
    if hasattr(sys.stdin, "buffer"):
        return sys.stdin.buffer.read()
    else:
        return sys.stdin.read()
