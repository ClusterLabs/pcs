from textwrap import dedent

from pcs_test.tools.command_env.mock_runner import Call as RunnerCall

from pcs import settings

class SystemctlShortcuts:
    def __init__(self, calls):
        self.__calls = calls

    def disable(
        self, service, name="runner.systemctl.disable",
        stdout="", stderr="", returncode=0
    ):
        self.__calls.place(
            name,
            RunnerCall(
                f"{settings.systemctl_binary} disable {service}.service",
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            )
        )

    def enable(
        self, service, name="runner.systemctl.enable",
        stdout="", stderr="", returncode=0
    ):
        self.__calls.place(
            name,
            RunnerCall(
                f"{settings.systemctl_binary} enable {service}.service",
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            )
        )

    def start(
        self, service, name="runner.systemctl.start",
        stdout="", stderr="", returncode=0
    ):
        self.__calls.place(
            name,
            RunnerCall(
                f"{settings.systemctl_binary} start {service}.service",
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            )
        )

    def stop(
        self, service, name="runner.systemctl.stop",
        stdout="", stderr="", returncode=0
    ):
        self.__calls.place(
            name,
            RunnerCall(
                f"{settings.systemctl_binary} stop {service}.service",
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            )
        )

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

    def is_enabled(
        self, service, is_enabled=True,
        name="runner_systemctl.is_enabled", before=None, instead=None
    ):
        args = dict(
            stdout="disabled\n",
            returncode=1,
        )
        if is_enabled:
            args = dict(
                stdout="enabled\n",
                returncode=0,
            )
        self.__calls.place(
            name,
            RunnerCall(
                "{bin_path} is-enabled {service}.service".format(
                    bin_path=settings.systemctl_binary,
                    service=service,
                ),
                **args
            ),
            before=before,
            instead=instead
        )

    def list_unit_files(
        self, unit_file_states,
        name="runner_systemctl.list_unit_files", before=None, instead=None
    ):
        if not unit_file_states:
            output = dedent(
                """\
                UNIT FILE   STATE

                0 unit files listed.
                """
            )
        else:
            unit_len = max(len(x) for x in unit_file_states) + len(".service")
            state_len = max(len(x) for x in unit_file_states.values())
            pattern = "{unit:<{unit_len}} {state:<{state_len}}"
            lines = (
                [
                    pattern.format(
                        unit="UNIT FILE", unit_len=unit_len,
                        state="STATE", state_len=state_len
                    )
                ]
                +
                [
                    pattern.format(
                        unit="{0}.service".format(unit), unit_len=unit_len,
                        state=state, state_len=state_len
                    )
                    for unit, state in unit_file_states.items()
                ]
                +
                [
                    "",
                    "{0} unit files listed.".format(len(unit_file_states))
                ]
            )
            output = "\n".join(lines)

        self.__calls.place(
            name,
            RunnerCall(
                "{bin_path} list-unit-files --full".format(
                    bin_path=settings.systemctl_binary
                ),
                stdout=output
            ),
            before=before,
            instead=instead
        )
