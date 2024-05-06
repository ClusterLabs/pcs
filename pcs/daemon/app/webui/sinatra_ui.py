from pcs.daemon import ruby_pcsd
from pcs.daemon.app import sinatra_ui
from pcs.daemon.app.common import RoutesType
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser

from . import session
from .auth import SessionAuthProvider


class SinatraAjaxProtected(sinatra_ui.SinatraAjaxProtected):
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
        self.initialize_sinatra(ruby_pcsd_wrapper)
        self._auth_provider = SessionAuthProvider(
            self, auth_provider, session_storage
        )

    def prepare(self) -> None:
        super().prepare()
        self._auth_provider.init_session()

    async def _get_auth_user(self):
        return await self._auth_provider.auth_by_sid()

    def _after_get_auth_user_hook(self, auth_user: AuthUser):
        self._auth_provider.update_session(auth_user)
        if self._auth_provider.is_sid_in_request_cookies():
            self._auth_provider.put_request_cookies_sid_to_response_cookies_sid()


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
