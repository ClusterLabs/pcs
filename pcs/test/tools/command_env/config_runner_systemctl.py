from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs import settings
from pcs.test.tools.command_env.mock_runner import Call as RunnerCall

class SystemctlShortcuts(object):
    def __init__(self, calls):
        self.__calls = calls

    def is_active(
        self, service, name="runner_systemctl.is_active", is_active=True
    ):
        args = dict(
            stdout="unknown\n",
            returncode=3,
        )
        if is_active:
            args = dict(
                stdout="active\n",
                returncode=0,
            )
        self.__calls.place(
            name,
            RunnerCall(
                "{bin_path} is-active {service}.service".format(
                    bin_path=settings.systemctl_binary,
                    service=service,
                ),
                **args
            )
        )
