from typing import (
    Optional,
    TypedDict,
)

from tornado.web import RequestHandler

from pcs.daemon.app.auth import UnixSocketAuthProvider
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser

from .session import (
    Session,
    Storage,
)

PCSD_SESSION = "pcsd.sid"


class SessionAuthProvider(UnixSocketAuthProvider):
    class CookieOptions(TypedDict):
        secure: bool
        httponly: bool
        samesite: str

    __cookie_options: CookieOptions = {
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
        auth_provider: AuthProvider,
        session_storage: Storage,
    ) -> None:
        super().__init__(handler, auth_provider)
        self.__session_storage = session_storage
        self.__session: Optional[Session] = None

    def init_session(self) -> None:
        self.__session = self._get_session()

    async def auth_by_sid(self) -> AuthUser:
        if self.__session:
            return await self.login_user(self.__session.username)
        return await self.auth_by_socket_user()

    def _get_session(self) -> Optional[Session]:
        if self.__sid_from_client is None:
            return None
        return self.__session_storage.get(self.__sid_from_client)

    def session_logout(self) -> None:
        if self.__session is not None:
            self.__session_storage.destroy(self.__session.sid)
        self.__session = None
        self._sid_to_cookies()

    def _sid_to_cookies(self) -> None:
        """
        Write the session id into a response cookie.
        """
        if self.__session:
            self._handler.set_cookie(
                PCSD_SESSION, self.__session.sid, **self.__cookie_options
            )
        else:
            self._handler.clear_cookie(PCSD_SESSION)

    def put_request_cookies_sid_to_response_cookies_sid(self) -> None:
        """
        If sid came in the request cookies put it into response cookies. But do
        not start new one.
        """
        # TODO this method should exist temporarily (for sinatra compatibility)
        if self.__sid_from_client is not None:
            self._handler.set_cookie(
                PCSD_SESSION, self.__sid_from_client, **self.__cookie_options
            )

    def is_sid_in_request_cookies(self) -> bool:
        return self.__sid_from_client is not None

    @property
    def __sid_from_client(self) -> Optional[str]:
        return self._handler.get_cookie(PCSD_SESSION, default=None)

    def update_session(self, auth_user: Optional[AuthUser]) -> None:
        if auth_user:
            if (
                not self.__session
                or self.__session.username != auth_user.username
            ):
                self.__session = self.__session_storage.login(
                    auth_user.username
                )
        else:
            self.__session = None
        self._sid_to_cookies()
