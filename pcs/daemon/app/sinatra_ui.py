from pcs.daemon import (
    ruby_pcsd,
    session,
)
from pcs.daemon.app.auth import (
    NotAuthorizedException,
    SessionAuthProvider,
)
from pcs.daemon.app.common import RoutesType
from pcs.daemon.app.sinatra_common import Sinatra
from pcs.daemon.app.ui_common import AjaxMixin
from pcs.lib.auth.provider import AuthProvider


class SinatraAjaxProtected(Sinatra, AjaxMixin):
    """
    SinatraAjaxProtected handles urls that calls the ajax Sinatra GUI functions.
    It allows to use this urls only for ajax calls.
    """

    _auth_provider: SessionAuthProvider

    def initialize(
        self,
        session_storage: session.Storage,
        ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
        auth_provider: AuthProvider,
    ) -> None:
        # pylint: disable=arguments-differ
        Sinatra.initialize(self, ruby_pcsd_wrapper)
        self._auth_provider = SessionAuthProvider(
            self, auth_provider, session_storage
        )

    def prepare(self) -> None:
        if not self.is_ajax:
            raise self.unauthorized()
        self._auth_provider.init_session()

    async def handle_sinatra_request(self):
        try:
            auth_user = await self._auth_provider.auth_by_sid()
        except NotAuthorizedException as e:
            raise self.unauthorized() from e
        self._auth_provider.update_session(auth_user)
        if self._auth_provider.is_sid_in_request_cookies():
            self._auth_provider.put_request_cookies_sid_to_response_cookies_sid()

        result = await self.ruby_pcsd_wrapper.request_gui(
            self.request,
            auth_user.username,
            auth_user.groups,
        )
        self.send_sinatra_result(result)

    async def get(self, *args, **kwargs):
        del args, kwargs
        await self.handle_sinatra_request()

    async def post(self, *args, **kwargs):
        del args, kwargs
        await self.handle_sinatra_request()


def get_routes(
    session_storage: session.Storage,
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
                session_storage=session_storage,
                ruby_pcsd_wrapper=ruby_pcsd_wrapper,
                auth_provider=auth_provider,
            ),
        ),
    ]
