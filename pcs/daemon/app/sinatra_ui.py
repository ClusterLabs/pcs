from pcs.daemon import ruby_pcsd
from pcs.daemon.app.auth import (
    NotAuthorizedException,
    UnixSocketAuthProvider,
)
from pcs.daemon.app.common import (
    LegacyApiHandler,
    RoutesType,
)
from pcs.daemon.app.sinatra_common import SinatraMixin
from pcs.daemon.app.ui_common import AjaxMixin
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser


class SinatraAjaxProtected(LegacyApiHandler, SinatraMixin, AjaxMixin):
    """
    SinatraAjaxProtected handles urls that calls the ajax Sinatra GUI functions.
    It allows to use this urls only for ajax calls.
    """

    _auth_provider: UnixSocketAuthProvider

    def initialize(
        self,
        ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
        auth_provider: AuthProvider,
    ) -> None:
        self.initialize_sinatra(ruby_pcsd_wrapper)
        self._auth_provider = UnixSocketAuthProvider(self, auth_provider)

    def prepare(self) -> None:
        if not self.is_ajax:
            raise self.unauthorized()

    async def _handle_request(self):
        try:
            auth_user = await self._get_auth_user()
        except NotAuthorizedException as e:
            raise self.unauthorized() from e

        # Webui version needs to deal with extra session operation here.
        self._after_get_auth_user_hook(auth_user)

        result = await self.ruby_pcsd_wrapper.request(
            auth_user,
            self.request,
        )
        self.send_sinatra_result(result)

    async def _get_auth_user(self):
        return await self._auth_provider.auth_by_socket_user()

    def _after_get_auth_user_hook(self, auth_user: AuthUser):
        pass


def get_routes(
    auth_provider: AuthProvider,
    ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
) -> RoutesType:
    return [
        # The protection by session was moved from ruby code to python code
        # (tornado).
        (
            r"/.*",
            SinatraAjaxProtected,
            dict(
                ruby_pcsd_wrapper=ruby_pcsd_wrapper,
                auth_provider=auth_provider,
            ),
        ),
    ]
