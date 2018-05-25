from pcs.daemon.session import Storage

PCSD_SESSION = "pcsd.sid"

class Mixin:
    __session = None
    """
    Mixin for tornado.web.RequestHandler
    """
    def initialize(self, session_storage: Storage):
        self.__storage = session_storage

    @property
    def session(self):
        if self.__session is None:
            # It is needed to cache session or the sid. Because no sid or an
            # invalid sid can come from a client. In such case every call would
            # provide new session. But we want to always have the first session
            # provided.
            self.__session = self.__storage.provide(self.__sid_from_client)
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
            self.__session = None
        elif self.__sid_from_client is not None:
            self.__storage.destroy(self.__sid_from_client)

    def session_login(self, username, groups=None):
        self.__session = self.__storage.login(self.__sid, username, groups)

    def session_login_failed(self, username):
        self.__session = self.__storage.failed_login_attempt(
            self.__sid,
            username,
        )

    def sid_to_cookies(self):
        """
        Write the session id into a response cookie.
        """
        self.set_cookie(PCSD_SESSION, self.session.sid)

    def put_request_cookies_sid_to_response_cookies_sid(self):
        """
        If sid came in the request cookies put it into response cookies. But do
        not start new one.
        """
        #TODO this method should exist temporarily (for sinatra compatibility)
        #pylint: disable=invalid-name
        if self.__sid_from_client is not None:
            self.set_cookie(PCSD_SESSION, self.__sid_from_client)

    def was_sid_in_request_cookies(self):
        return self.__sid_from_client is not None

    @property
    def __sid(self):
        if self.__session is not None:
            return self.__session.sid
        return self.__sid_from_client

    @property
    def __sid_from_client(self):
        return self.get_cookie(PCSD_SESSION, default=None)
