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
        lib.qdevice.qdevice_status_text(
            model,
            verbose=modifiers.get("--full"),
            cluster=cluster,
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
    lib.qdevice.qdevice_setup(
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
    lib.qdevice.qdevice_destroy(model, proceed_if_used=modifiers.get("--force"))


def qdevice_start_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.qdevice_start(model)


def qdevice_stop_cmd(lib, argv, modifiers):
    """
    Options:
      * --force - stop qdevice even if it is used by clusters
    """
    modifiers.ensure_only_supported("--force")
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.qdevice_stop(model, proceed_if_used=modifiers.get("--force"))


def qdevice_kill_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.qdevice_kill(model)


def qdevice_enable_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.qdevice_enable(model)


def qdevice_disable_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.qdevice_disable(model)
