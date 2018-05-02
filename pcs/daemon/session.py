import random
import string
from time import time as now

PCSD_SESSION = "rack.session"

class Session:
    def __init__(self, sid, username=None, groups=None, is_authenticated=False):
        # Session id propageted via cookies.
        self.__sid = sid
        # Username given by login attempt. It does not matter if the
        # authentication succeeded.
        self.__username = username
        # The flag that indicated if the user was authenticated.
        # The user is authenticated when they is recognized as a system user
        # belonging to the high availability admin group (typicaly hacluster).
        self.__is_authenticated = is_authenticated
        # Id that will be returned by login-status or login (for ajax).
        self.__ajax_id = (
            f"{int(now())}-{random.randint(1, 100)}" if is_authenticated
            else None
        )
        # Groups of the user. Similary to username, it does not means that the
        # user is authenticated when the groups are loaded.
        self.__groups = groups or []
        # The moment of the last access. The only muttable attribute.
        self.refresh()

    @property
    def is_authenticated(self):
        self.refresh()
        return self.__is_authenticated

    @property
    def username(self):
        self.refresh()
        return self.__username

    @property
    def sid(self):
        self.refresh()
        return self.__sid

    @property
    def ajax_id(self):
        self.refresh()
        return self.__ajax_id

    @property
    def groups(self):
        self.refresh()
        return self.__groups

    def refresh(self):
        """
        Set the time of last access to now.
        """
        self.__last_access = now()
        return self

    def was_unused_last(self, seconds):
        return now() > self.__last_access + seconds

class Storage:
    def __init__(self, lifetime_seconds):
        self.__sessions = {}
        self.__lifetime_seconds = lifetime_seconds

    def provide(self, sid=None) -> Session:
        if self.__is_valid_sid(sid):
            return self.__sessions[sid].refresh()
        return self.__register(self.__generate_sid())

    def drop_expired(self):
        obsolete_sid_list = [
            sid for sid, session in self.__sessions.items()
            if session.was_unused_last(self.__lifetime_seconds)
        ]
        for sid in obsolete_sid_list:
            del self.__sessions[sid]

    def destroy(self, sid):
        if sid in self.__sessions:
            del self.__sessions[sid]
        return self

    def login(self, sid, username, groups) -> Session:
        return self.__register(
            self.__valid_sid(sid),
            username,
            groups,
            is_authenticated=True
        )

    def failed_login_attempt(self, sid, username) -> Session:
        return self.__register(self.__valid_sid(sid), username)

    def __is_valid_sid(self, sid):
        return not (
            sid is None
            or
            # Do not let a user (an attacker?) to force us to use their sid.
            sid not in self.__sessions
            or
            self.__sessions[sid].was_unused_last(self.__lifetime_seconds)
        )

    def __valid_sid(self, sid):
        return sid if self.__is_valid_sid(sid) else self.__generate_sid()

    def __register(self, *args, **kwargs) -> Session:
        session = Session(*args, **kwargs)
        self.__sessions[session.sid] = session
        return session

    def __generate_sid(self):
        for _ in range(10):
            sid = ''.join(
                random.choices(
                    string.ascii_lowercase + string.digits,
                    k=64
                )
            )
            if sid not in self.__sessions:
                return sid
        #TODO what to do?
        raise Exception("Cannot generate unique sid")

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
            # It is needed to cache session or the sid. Because from client can
            # come no sid or an invalid sid. In such case every call would
            # provide new session. But want to have here the first provided.
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
        Write session id into response cookie.
        """
        self.set_cookie(PCSD_SESSION, self.session.sid)

    def put_request_cookies_sid_to_response_cookies_sid(self):
        """
        If sid came in the request cookies put it into response cookies. But do
        not start new one.
        """
        #TODO this method should exists temporarily (for sinatra compatibility)
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
