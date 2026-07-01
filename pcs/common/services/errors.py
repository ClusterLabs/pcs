class ManageServiceError(Exception):
    def __init__(
        self,
        service: str,
        message: str,
        instance: str | None = None,
    ):
        self.service = service
        self.message = message
        self.instance = instance


class DisableServiceError(ManageServiceError):
    pass


class EnableServiceError(ManageServiceError):
    pass


class StartServiceError(ManageServiceError):
    pass


class StopServiceError(ManageServiceError):
    pass
