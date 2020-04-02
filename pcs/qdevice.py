import sys

from pcs.cli.common.errors import CmdLineInputError


def qdevice_status_cmd(lib, argv, modifiers):
    """
    Options:
      * --full - get more detailed output
    """
    modifiers.ensure_only_supported("--full")
    if not argv or len(argv) > 2:
        raise CmdLineInputError()
    model = argv[0]
    cluster = None if len(argv) < 2 else argv[1]
    print(
        lib.qdevice.status(
            model, verbose=modifiers.get("--full"), cluster=cluster,
        )
    )


def qdevice_setup_cmd(lib, argv, modifiers):
    """
    Options:
      * --enable - enable qdevice service
      * --start - start qdevice service
    """
    modifiers.ensure_only_supported("--enable", "--start")
    if len(argv) != 2:
        raise CmdLineInputError()
    if argv[0] != "model":
        raise CmdLineInputError()
    model = argv[1]
    lib.qdevice.setup(
        model, modifiers.get("--enable"), modifiers.get("--start")
    )


def qdevice_destroy_cmd(lib, argv, modifiers):
    """
    Options:
      * --force - destroy qdevice even if it is used by clusters
    """
    modifiers.ensure_only_supported("--force")
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.destroy(model, proceed_if_used=modifiers.get("--force"))


def qdevice_start_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.start(model)


def qdevice_stop_cmd(lib, argv, modifiers):
    """
    Options:
      * --force - stop qdevice even if it is used by clusters
    """
    modifiers.ensure_only_supported("--force")
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.stop(model, proceed_if_used=modifiers.get("--force"))


def qdevice_kill_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.kill(model)


def qdevice_enable_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.enable(model)


def qdevice_disable_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.disable(model)


# following commands are internal use only, called from pcsd


def qdevice_net_client_setup_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    ca_certificate = _read_stdin()
    lib.qdevice.client_net_setup(ca_certificate)


def qdevice_net_client_import_certificate_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    certificate = _read_stdin()
    lib.qdevice.client_net_import_certificate(certificate)


def qdevice_net_client_destroy(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    lib.qdevice.client_net_destroy()


def qdevice_sign_net_cert_request_cmd(lib, argv, modifiers):
    """
    Options:
      * --name - cluster name
    """
    modifiers.ensure_only_supported("--name")
    if argv:
        raise CmdLineInputError()
    certificate_request = _read_stdin()
    signed = lib.qdevice.sign_net_cert_request(
        certificate_request, modifiers.get("--name")
    )
    # In python3 base64.b64encode returns bytes.
    # Bytes is printed like this: b'bytes content'
    # and we need to get rid of that b'', so we change bytes to string.
    # Since it's base64encoded, it's safe to use ascii.
    signed = signed.decode("ascii")
    print(signed)


def _read_stdin():
    # in python3 stdin returns str so we need to use buffer
    return sys.stdin.buffer.read()
