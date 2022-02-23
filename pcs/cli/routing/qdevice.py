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
        # following commands are internal use only, called from pcsd
        "sign-net-cert-request": qdevice.qdevice_sign_net_cert_request_cmd,
        "net-client": create_router(
            {
                "setup": qdevice.qdevice_net_client_setup_cmd,
                "import-certificate": (
                    qdevice.qdevice_net_client_import_certificate_cmd
                ),
                "destroy": qdevice.qdevice_net_client_destroy,
            },
            ["qdevice", "net-client"],
        ),
    },
    ["qdevice"],
)
