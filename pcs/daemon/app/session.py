from pcs.daemon.session import Storage

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

    def init_session(self):
        self.__session = self.__storage.provide(self.__sid_from_client)

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

    def session_refresh_auth(self, user_auth_info, sign_rejection=False):
        if user_auth_info.is_authorized:
            self.__session = self.__storage.login(
                self.__session.sid,
                user_auth_info.name,
                user_auth_info.groups,
            )
            self.sid_to_cookies()
        elif sign_rejection:
            self.__session = self.__storage.rejected_user(
                self.__session.sid,
                user_auth_info.name,
            )
            self.sid_to_cookies()
