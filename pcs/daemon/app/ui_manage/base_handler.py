from typing import Any, Mapping

from tornado.web import Finish

from pcs.common.async_tasks.dto import CommandDto, CommandOptionsDto
from pcs.daemon.app.api_v0_tools import (
    SimplifiedResult,
    run_library_command_in_scheduler,
)
from pcs.daemon.app.auth import NotAuthorizedException
from pcs.daemon.app.auth_provider import (
    ApiAuthProviderFactoryInterface,
    ApiAuthProviderInterface,
)
from pcs.daemon.app.common import LegacyApiHandler
from pcs.daemon.app.ui_common import AjaxMixin
from pcs.daemon.async_tasks.scheduler import Scheduler
from pcs.lib.auth.types import AuthUser


class BaseAjaxProtectedManageHandler(LegacyApiHandler, AjaxMixin):
    """
    Base class for session-authenticated AJAX-protected /manage/* endpoints
    """

    __auth_provider: ApiAuthProviderInterface

    def initialize(
        self,
        scheduler: Scheduler,
        api_auth_provider_factory: ApiAuthProviderFactoryInterface,
    ) -> None:
        super().initialize()
        self._scheduler = scheduler
        self.__auth_provider = api_auth_provider_factory.create(self)

    def prepare(self) -> None:
        if not self.is_ajax:
            raise self.unauthorized()
        if not self.__auth_provider.is_available():
            raise self.unauthorized()

    def _error(self, message: str, http_code: int = 400) -> Finish:
        """
        Helper method for exit request processing with an error
        """
        self.set_status(http_code)
        self.write(message)
        return Finish()

    async def _get_auth_user(self) -> AuthUser:
        try:
            return await self.__auth_provider.auth_user()
        except NotAuthorizedException as e:
            raise self.unauthorized() from e

    async def _process_request(
        self, cmd_name: str, cmd_params: Mapping[str, Any]
    ) -> SimplifiedResult:
        """
        Helper method for calling pcs library commands
        """
        auth_user = await self._get_auth_user()

        command_dto = CommandDto(
            command_name=cmd_name,
            params=cmd_params,
            options=CommandOptionsDto(
                effective_username=auth_user.username,
                effective_groups=list(auth_user.groups),
            ),
        )
        return await run_library_command_in_scheduler(
            self._scheduler, command_dto, auth_user, self._error
        )

    async def _handle_request(self) -> None:
        """Override this in subclasses"""
        raise NotImplementedError()
