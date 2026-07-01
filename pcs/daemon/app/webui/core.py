import os.path
from typing import TYPE_CHECKING

from tornado.ioloop import IOLoop

from pcs.daemon.app.common import BaseHandler, LegacyApiBaseHandler, RoutesType
from pcs.daemon.app.ui_common import AjaxMixin, StaticFile
from pcs.daemon.app.webui.auth_provider import (
    PCSD_SESSION,
    SESSION_COOKIE_OPTIONS,
)
from pcs.daemon.app.webui.session import Storage
from pcs.lib.auth.provider import AuthProvider

if TYPE_CHECKING:
    from pcs.daemon.app.webui.session import Session


class SPAHandler(LegacyApiBaseHandler):
    __index: str
    __fallback: str

    def initialize(self, index: str, fallback: str) -> None:
        self.__index = index
        self.__fallback = fallback

    def get(self) -> None:
        self.render(
            self.__index
            if os.path.isfile(str(self.__index))
            # spa is probably not installed
            else self.__fallback
        )


class Login(SPAHandler, AjaxMixin):
    _lib_auth_provider: AuthProvider
    _session_storage: Storage

    def initialize(  # type: ignore[override]
        self,
        session_storage: Storage,
        lib_auth_provider: AuthProvider,
        index: str,
        fallback: str,
    ) -> None:
        SPAHandler.initialize(self, index, fallback)
        self._lib_auth_provider = lib_auth_provider
        self._session_storage = session_storage

    async def post(self) -> None:
        auth_user = await IOLoop.current().run_in_executor(
            executor=None,
            func=lambda: self._lib_auth_provider.auth_by_username_password(
                self.get_body_argument("username") or "",
                self.get_body_argument("password") or "",
            ),
        )
        if auth_user is None:
            raise self.unauthorized()

        sid = self.get_cookie(PCSD_SESSION)
        session: Session | None = None
        if sid is not None:
            session = self._session_storage.get(sid)

        if session is None or session.username != auth_user.username:
            session = self._session_storage.login(auth_user.username)

        self.set_cookie(PCSD_SESSION, session.sid, **SESSION_COOKIE_OPTIONS)


class Logout(AjaxMixin, BaseHandler):
    """
    Logout handles url for logout. It is used for both ajax and non-ajax
    requests.
    """

    _session_storage: Storage

    def initialize(self, session_storage: Storage) -> None:
        self._session_storage = session_storage

    async def get(self) -> None:
        sid = self.get_cookie(PCSD_SESSION)
        session: Session | None = None
        if sid is not None:
            session = self._session_storage.get(sid)
        if session:
            self._session_storage.destroy(session.sid)

        self.clear_cookie(PCSD_SESSION)
        self.write("OK")


class StaticFileMayBe(StaticFile):
    async def get(self, path: str, include_body: bool = True) -> None:
        if not os.path.isdir(str(self.root)):
            # spa is probably not installed
            self.set_status(404, "Not Found")
            return None
        return await super().get(path, include_body)


def get_routes(
    url_prefix: str,
    app_dir: str,
    fallback_page_path: str,
    session_storage: Storage,
    auth_provider: AuthProvider,
) -> RoutesType:
    def static_path(directory: str = "") -> dict[str, str]:
        return dict(path=os.path.join(app_dir, directory))

    pages = dict(
        index=os.path.join(app_dir, "index.html"),
        fallback=fallback_page_path,
    )

    # One possibility is to check if SPA index exists and if does not exists
    # return only route to fallback page. However, it would require to restart
    # pcsd after putting spa. For this reason, routes stay the same, no matter
    # if SPA index exists.

    return [
        (f"{url_prefix}static/(.*)", StaticFileMayBe, static_path("static")),
        (f"{url_prefix}(manifest\\.json)", StaticFileMayBe, static_path()),
        (
            f"{url_prefix}(manifest_test_marks\\.json)",
            StaticFileMayBe,
            static_path(),
        ),
        (
            f"{url_prefix}login",
            Login,
            dict(
                session_storage=session_storage,
                lib_auth_provider=auth_provider,
                index=os.path.join(app_dir, "index.html"),
                fallback=fallback_page_path,
            ),
        ),
        (f"{url_prefix}logout", Logout, dict(session_storage=session_storage)),
        (f"{url_prefix}.*", SPAHandler, pages),
    ]
