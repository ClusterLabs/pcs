from typing import Optional, TypedDict

from tornado.ioloop import IOLoop
from tornado.web import RequestHandler

from pcs.daemon.app.auth import NotAuthorizedException
from pcs.daemon.app.auth_provider import (
    ApiAuthProviderFactoryInterface,
    ApiAuthProviderInterface,
)
from pcs.daemon.app.webui.session import Storage
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser

# Constants for session authentication
PCSD_SESSION = "pcsd.sid"


class SessionAuthProvider(ApiAuthProviderInterface):
    """
    Authentication provider for session-based authentication (WebUI).

    Authenticates users via session cookie. Sessions are managed by the
    session storage and identified by the "pcsd.sid" cookie.
    """

    class CookieOptions(TypedDict):
        secure: bool
        httponly: bool
        samesite: str

    # Cookie options for session cookie
    # Matches settings from webui/auth.py for compatibility
    _cookie_options: CookieOptions = {
        "secure": True,
        "httponly": True,
        # rhbz#2097393
        # Prevent a cookie to be sent on cross-site requests, allow it to be
        # sent when navigating to pcs web UI from an external site.
        "samesite": "Lax",
    }

    def __init__(
        self,
        handler: RequestHandler,
        lib_auth_provider: AuthProvider,
        session_storage: Storage,
    ) -> None:
        """
        Initialize session auth provider.

        handler -- Tornado request handler
        lib_auth_provider -- library auth provider for user validation
        session_storage -- session storage
        """
        self._handler = handler
        self._lib_auth_provider = lib_auth_provider
        self._session_storage = session_storage

        sid_from_client = self.__sid_from_client
        self.__session = (
            self._session_storage.get(sid_from_client)
            if sid_from_client
            else None
        )

    @property
    def __sid_from_client(self) -> Optional[str]:
        return self._handler.get_cookie(PCSD_SESSION, default=None)

    def is_available(self) -> bool:
        return self.__session is not None

    async def auth_user(self) -> AuthUser:
        if self.__session is None:
            raise NotAuthorizedException()

        # mypy complains that self.__session can be None when passed into
        # the lambda below. Passing local variable fixes this
        session = self.__session
        auth_user = await IOLoop.current().run_in_executor(
            executor=None,
            func=lambda: self._lib_auth_provider.login_user(session.username),
        )
        if auth_user is None:
            raise NotAuthorizedException()

        # Update session cookie in response
        self._set_session_cookie()

        return auth_user

    def _set_session_cookie(self) -> None:
        """Set or clear session cookie based on current session state."""
        if self.__session:
            self._handler.set_cookie(
                PCSD_SESSION, self.__session.sid, **self._cookie_options
            )
        else:
            self._handler.clear_cookie(PCSD_SESSION)


class SessionAuthProviderFactory(ApiAuthProviderFactoryInterface):
    def __init__(
        self, lib_auth_provider: AuthProvider, session_storage: Storage
    ) -> None:
        super().__init__(lib_auth_provider)
        self._session_storage = session_storage

    def create(self, handler: RequestHandler) -> SessionAuthProvider:
        return SessionAuthProvider(
            handler, self._lib_auth_provider, self._session_storage
        )
