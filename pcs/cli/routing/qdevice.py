from pcs import (
    qdevice,
    usage,
)
from pcs.cli.common.routing import create_router

qdevice_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.qdevice(argv)),
        "status": qdevice.qdevice_status_cmd,
        "setup": qdevice.qdevice_setup_cmd,
        "destroy": qdevice.qdevice_destroy_cmd,
        "start": qdevice.qdevice_start_cmd,
        "stop": qdevice.qdevice_stop_cmd,
        "kill": qdevice.qdevice_kill_cmd,
        "enable": qdevice.qdevice_enable_cmd,
        "disable": qdevice.qdevice_disable_cmd,
    },
    ["qdevice"],
)
