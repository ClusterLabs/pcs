from time import time as now
from typing import Optional

from pcs.common.tools import get_unique_uuid


class Session:
    def __init__(
        self,
        sid: str,
        username: str,
    ) -> None:
        # Session id propageted via cookies.
        self.__sid = sid
        # Username given by login attempt. It does not matter if the
        # authentication succeeded.
        self.__username = username
        # The moment of the last access. The only muttable attribute.
        self.refresh()

    @property
    def username(self) -> str:
        self.refresh()
        return self.__username

    @property
    def sid(self) -> str:
        self.refresh()
        return self.__sid

    def refresh(self) -> None:
        """
        Set the time of last access to now.
        """
        self.__last_access = now()

    def was_unused_last(self, seconds: int) -> bool:
        return now() > self.__last_access + seconds


class Storage:
    def __init__(self, lifetime_seconds: int) -> None:
        self.__sessions: dict[str, Session] = {}
        self.__lifetime_seconds = lifetime_seconds

    def get(self, sid: str) -> Optional[Session]:
        self.drop_expired()
        session = self.__sessions.get(sid)
        if session is not None:
            session.refresh()
        return session

    def drop_expired(self) -> None:
        obsolete_sid_list = [
            sid
            for sid, session in self.__sessions.items()
            if session.was_unused_last(self.__lifetime_seconds)
        ]
        for sid in obsolete_sid_list:
            self.destroy(sid)

    def destroy(self, sid: str) -> None:
        if sid in self.__sessions:
            del self.__sessions[sid]

    def login(self, username: str) -> Session:
        self.drop_expired()
        sid = get_unique_uuid(tuple(self.__sessions.keys()))
        session = Session(sid, username)
        self.__sessions[sid] = session
        return session
