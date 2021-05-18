from typing import Optional


class ManageServiceError(Exception):
    # pylint: disable=super-init-not-called
    def __init__(
        self,
        service: str,
        message: str,
        instance: Optional[str] = None,
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
