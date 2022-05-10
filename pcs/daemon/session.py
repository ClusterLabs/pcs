import random
import string
from time import time as now


class Session:
    def __init__(
        self,
        sid,
        username=None,
        groups=None,
        is_authenticated=False,
        ajax_id=None,
    ):
        # Session id propageted via cookies.
        self.__sid = sid
        # Username given by login attempt. It does not matter if the
        # authentication succeeded.
        self.__username = username
        # The flag that indicated if the user was authenticated.
        # The user is authenticated when they are recognized as a system user
        # belonging to the high availability admin group (typically hacluster).
        self.__is_authenticated = is_authenticated
        # Id that will be returned by login-status or login (for ajax).
        self.__ajax_id = None
        if self.__is_authenticated:
            self.__ajax_id = (
                ajax_id if ajax_id else f"{int(now())}-{random.randint(1, 100)}"
            )
        # Groups of the user. Similalry to username, it does not mean that the
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
            sid
            for sid, session in self.__sessions.items()
            if session.was_unused_last(self.__lifetime_seconds)
        ]
        for sid in obsolete_sid_list:
            del self.__sessions[sid]

    def destroy(self, sid):
        if sid in self.__sessions:
            del self.__sessions[sid]
        return self

    def login(self, sid, username, groups, ajax_id=None) -> Session:
        return self.__register(
            self.__valid_sid(sid),
            username=username,
            groups=groups,
            is_authenticated=True,
            ajax_id=ajax_id,
        )

    def rejected_user(self, sid, username) -> Session:
        return self.__register(self.__valid_sid(sid), username=username)

    def __is_valid_sid(self, sid):
        return not (
            sid is None
            or
            # Do not let a user (an attacker?) to force us to use their sid.
            sid not in self.__sessions
            or self.__sessions[sid].was_unused_last(self.__lifetime_seconds)
        )

    def __valid_sid(self, sid):
        return sid if self.__is_valid_sid(sid) else self.__generate_sid()

    def __register(self, *args, **kwargs) -> Session:
        session = Session(*args, **kwargs)
        self.__sessions[session.sid] = session
        return session

    def __generate_sid(self):
        for _ in range(10):
            sid = "".join(
                random.choices(string.ascii_lowercase + string.digits, k=64)
            )
            if sid not in self.__sessions:
                return sid
        # TODO what to do?
        raise Exception("Cannot generate unique sid")
