from http.cookies import Morsel

from pcs.daemon.auth import (
    authorize_user,
    check_user_groups,
)
from pcs.daemon.session import Storage

# monkeypatch Python 3.6 to add support for samesite attribute
Morsel._reserved["samesite"] = "SameSite"  # pylint: disable=protected-access


PCSD_SESSION = "pcsd.sid"


class Mixin:
    """
    Mixin for tornado.web.RequestHandler
    """

    __session = None
    __cookie_options = {
        "secure": True,
        "httponly": True,
        # rhbz#2097393
        # Prevent a cookie to be sent on cross-site requests, allow it to be
        # sent when navigating to pcs web UI from an external site.
        "samesite": "Lax",
    }

    def initialize(self, session_storage: Storage):
        self.__storage = session_storage

    async def init_session(self):
        self.__session = self.__storage.provide(self.__sid_from_client)
        if self.__session.is_authenticated:
            self.__refresh_auth(
                await check_user_groups(self.__session.username),
                ajax_id=self.__session.ajax_id,
            )

    async def session_auth_user(self, username, password, sign_rejection=True):
        """
        Make user authorization and refresh storage.

        bool sing_rejection -- flag according to which will be decided whether
            to manipulate with session in storage in case of failed
            authorization. It allows not to touch session for ajax calls when
            authorization fails. It keeps previous behavior and should be
            reviewed.
        """
        # initialize session since it should be used without `init_session`
        self.__session = self.__storage.provide(self.__sid_from_client)
        self.__refresh_auth(
            await authorize_user(username, password),
            sign_rejection=sign_rejection,
        )

    @property
    def session(self):
        if self.__session is None:
            raise Exception(
                "Session is not set in session mixin. "
                "Session probably has not been initialized in request handler."
            )
        return self.__session

    def prepare(self):
        """
        Expired sessions are removed before each request that uses sessions (it
        means before each request that is handled by descendant of this mixin).
        """
        self.__storage.drop_expired()

    def session_logout(self):
        if self.__session is not None:
            self.__storage.destroy(self.__session.sid)
        elif self.__sid_from_client is not None:
            self.__storage.destroy(self.__sid_from_client)
        self.__session = self.__storage.provide()

    def sid_to_cookies(self):
        """
        Write the session id into a response cookie.
        """
        self.set_cookie(PCSD_SESSION, self.session.sid, **self.__cookie_options)

    def put_request_cookies_sid_to_response_cookies_sid(self):
        """
        If sid came in the request cookies put it into response cookies. But do
        not start new one.
        """
        # TODO this method should exist temporarily (for sinatra compatibility)
        # pylint: disable=invalid-name
        if self.__sid_from_client is not None:
            self.set_cookie(
                PCSD_SESSION, self.__sid_from_client, **self.__cookie_options
            )

    def was_sid_in_request_cookies(self):
        return self.__sid_from_client is not None

    @property
    def __sid_from_client(self):
        return self.get_cookie(PCSD_SESSION, default=None)

    def __refresh_auth(self, user_auth_info, sign_rejection=True, ajax_id=None):
        if user_auth_info.is_authorized:
            self.__session = self.__storage.login(
                self.__session.sid,
                user_auth_info.name,
                user_auth_info.groups,
                ajax_id,
            )
            self.sid_to_cookies()
        elif sign_rejection:
            self.__session = self.__storage.rejected_user(
                self.__session.sid,
                user_auth_info.name,
            )
            self.sid_to_cookies()
