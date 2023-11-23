import os.path

from pcs.daemon import session
from pcs.daemon.app.auth import (
    NotAuthorizedException,
    PasswordAuthProvider,
    SessionAuthProvider,
)
from pcs.daemon.app.common import (
    BaseHandler,
    LegacyApiBaseHandler,
    RoutesType,
)
from pcs.daemon.app.ui_common import (
    AjaxMixin,
    StaticFile,
)
from pcs.lib.auth.provider import AuthProvider


class SPAHandler(LegacyApiBaseHandler):
    __index = None
    __fallback = None

    def initialize(self, index: str, fallback: str) -> None:
        self.__index = index
        self.__fallback = fallback

    def get(self):
        self.render(
            self.__index
            if os.path.isfile(str(self.__index))
            # spa is probably not installed
            else self.__fallback
        )


class Login(SPAHandler, AjaxMixin):
    _password_auth_provider: PasswordAuthProvider
    _session_auth_provider: SessionAuthProvider

    def initialize(
        self,
        session_storage: session.Storage,
        auth_provider: AuthProvider,
        index: str,
        fallback: str,
    ) -> None:
        # pylint: disable=arguments-differ
        SPAHandler.initialize(self, index, fallback)
        self._password_auth_provider = PasswordAuthProvider(self, auth_provider)
        self._session_auth_provider = SessionAuthProvider(
            self, auth_provider, session_storage
        )

    def prepare(self) -> None:
        self._session_auth_provider.init_session()

    async def post(self):
        # This is the way of old (ruby) pcsd. Post login generates a session
        # cookie. No matter if authentication succeeded or failed.
        try:
            self._session_auth_provider.update_session(
                await self._password_auth_provider.auth_by_username_password(
                    self.get_body_argument("username"),
                    self.get_body_argument("password"),
                )
            )
        except NotAuthorizedException as e:
            raise self.unauthorized() from e


class Logout(AjaxMixin, BaseHandler):
    """
    Logout handles url for logout. It is used for both ajax and non-ajax
    requests.
    """

    _auth_provider: SessionAuthProvider

    def initialize(
        self,
        session_storage: session.Storage,
        auth_provider: AuthProvider,
    ) -> None:
        self._auth_provider = SessionAuthProvider(
            self, auth_provider, session_storage
        )

    def prepare(self) -> None:
        self._auth_provider.init_session()

    async def get(self):
        self._auth_provider.session_logout()
        self.write("OK")


class StaticFileMayBe(StaticFile):
    # pylint: disable=abstract-method
    async def get(self, *args, **kwargs):
        if not os.path.isdir(str(self.root)):
            # spa is probably not installed
            self.set_status(404, "Not Found")
            return None
        return await super().get(*args, **kwargs)


def get_routes(
    url_prefix: str,
    app_dir: str,
    fallback_page_path: str,
    session_storage: session.Storage,
    auth_provider: AuthProvider,
) -> RoutesType:
    def static_path(directory=""):
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
                auth_provider=auth_provider,
                index=os.path.join(app_dir, "index.html"),
                fallback=fallback_page_path,
            ),
        ),
        (
            f"{url_prefix}logout",
            Logout,
            dict(session_storage=session_storage, auth_provider=auth_provider),
        ),
        (f"{url_prefix}.*", SPAHandler, pages),
    ]
