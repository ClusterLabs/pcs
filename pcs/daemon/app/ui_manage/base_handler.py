from collections.abc import Mapping
from typing import Any

from tornado.web import Finish

from pcs.common.async_tasks.dto import CommandDto, CommandOptionsDto
from pcs.daemon.app.api_v0_tools import (
    SimplifiedResult,
    run_library_command_in_scheduler,
)
from pcs.daemon.app.auth_provider import (
    ApiAuthProviderFactoryInterface,
    ApiAuthProviderInterface,
    NotAuthorizedException,
)
from pcs.daemon.app.common import LegacyApiHandler
from pcs.daemon.app.ui_common import AjaxMixin
from pcs.daemon.async_tasks.scheduler import Scheduler
from pcs.lib.auth.types import AuthUser


class BaseAjaxProtectedManageHandler(LegacyApiHandler, AjaxMixin):
    """
    Base class for session-authenticated AJAX-protected /manage/* endpoints
    """

    _auth_provider: ApiAuthProviderInterface
    _auth_user: AuthUser

    def initialize(
        self,
        scheduler: Scheduler,
        api_auth_provider_factory: ApiAuthProviderFactoryInterface,
    ) -> None:
        super().initialize()
        self._scheduler = scheduler
        self._auth_provider = api_auth_provider_factory.create(self)

    async def prepare(self) -> None:
        if not self.is_ajax:
            raise self.unauthorized()
        try:
            self._auth_user = await self._auth_provider.auth_user()
        except NotAuthorizedException as e:
            raise self.unauthorized() from e

    def _error(self, message: str, http_code: int = 400) -> Finish:
        """
        Helper method for exit request processing with an error
        """
        self.set_status(http_code)
        self.write(message)
        return Finish()

    async def _run_library_command(
        self, cmd_name: str, cmd_params: Mapping[str, Any]
    ) -> SimplifiedResult:
        """
        Helper method for calling pcs library commands
        """
        command_dto = CommandDto(
            command_name=cmd_name,
            params=dict(cmd_params),
            options=CommandOptionsDto(),
        )
        return await run_library_command_in_scheduler(
            self._scheduler, command_dto, self._auth_user, self._error
        )

    async def _handle_request(self) -> None:
        """Override this in subclasses"""
        raise NotImplementedError()
