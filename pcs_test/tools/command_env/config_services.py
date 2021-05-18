from pcs.common.services import errors

from pcs_test.tools.command_env.mock_service_manager import Call


class ServiceManagerConfig:
    def __init__(self, calls):
        self.__calls = calls

    def start(
        self,
        service,
        instance=None,
        failure_msg=None,
        name="services.start",
        before=None,
        instead=None,
    ):
        self.__calls.place(
            name,
            Call(
                "start",
                service=service,
                instance=instance,
                return_value=None,
                exception=(
                    errors.StartServiceError(
                        service, message=failure_msg, instance=instance
                    )
                    if failure_msg
                    else None
                ),
            ),
            before=before,
            instead=instead,
        )

    def stop(
        self,
        service,
        instance=None,
        failure_msg=None,
        name="services.stop",
        before=None,
        instead=None,
    ):
        self.__calls.place(
            name,
            Call(
                "stop",
                service=service,
                instance=instance,
                return_value=None,
                exception=(
                    errors.StopServiceError(
                        service, message=failure_msg, instance=instance
                    )
                    if failure_msg
                    else None
                ),
            ),
            before=before,
            instead=instead,
        )

    def enable(
        self,
        service,
        instance=None,
        failure_msg=None,
        name="services.enable",
        before=None,
        instead=None,
    ):
        self.__calls.place(
            name,
            Call(
                "enable",
                service=service,
                instance=instance,
                return_value=None,
                exception=(
                    errors.EnableServiceError(
                        service, message=failure_msg, instance=instance
                    )
                    if failure_msg
                    else None
                ),
            ),
            before=before,
            instead=instead,
        )

    def disable(
        self,
        service,
        instance=None,
        failure_msg=None,
        name="services.disable",
        before=None,
        instead=None,
    ):
        self.__calls.place(
            name,
            Call(
                "disable",
                service=service,
                instance=instance,
                return_value=None,
                exception=(
                    errors.DisableServiceError(
                        service, message=failure_msg, instance=instance
                    )
                    if failure_msg
                    else None
                ),
            ),
            before=before,
            instead=instead,
        )

    def is_installed(
        self,
        service,
        return_value=True,
        name="services.is_installed",
        before=None,
        instead=None,
    ):
        self.__calls.place(
            name,
            Call(
                "is_installed",
                service=service,
                return_value=return_value,
            ),
            before=before,
            instead=instead,
        )

    def is_enabled(
        self,
        service,
        instance=None,
        return_value=True,
        name="services.is_enabled",
        before=None,
        instead=None,
    ):
        self.__calls.place(
            name,
            Call(
                "is_enabled",
                service=service,
                instance=instance,
                return_value=return_value,
            ),
            before=before,
            instead=instead,
        )

    def is_running(
        self,
        service,
        instance=None,
        name="services.is_running",
        return_value=True,
        before=None,
        instead=None,
    ):
        self.__calls.place(
            name,
            Call(
                "is_running",
                service,
                instance=instance,
                return_value=return_value,
            ),
            before=before,
            instead=instead,
        )

    def get_available_services(
        self,
        services,
        name="services.get_available_services",
        before=None,
        instead=None,
    ):
        self.__calls.place(
            name,
            Call("get_available_services", return_value=services),
            before=before,
            instead=instead,
        )
