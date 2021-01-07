import os.path

from pcs.daemon import session
from pcs.daemon.app import session as app_session
from pcs.daemon.app.common import BaseHandler
from pcs.daemon.app.ui_common import AjaxMixin, StaticFile


class SPAHandler(BaseHandler):
    __index = None
    __fallback = None

    def initialize(self, index, fallback):
        # pylint: disable=arguments-differ
        self.__index = index
        self.__fallback = fallback
        # add security related headers to all responses
        self.enhance_headers()

    def get(self, *args, **kwargs):
        del args, kwargs
        self.render(
            self.__index
            if os.path.isfile(str(self.__index))
            # spa is probably not installed
            else self.__fallback
        )


class Login(SPAHandler, app_session.Mixin, AjaxMixin):
    def initialize(self, session_storage, index, fallback):
        # pylint: disable=arguments-differ
        app_session.Mixin.initialize(self, session_storage)
        SPAHandler.initialize(self, index, fallback)

    async def post(self, *args, **kwargs):
        del args, kwargs
        # This is the way of old (ruby) pcsd. Post login generates a session
        # cookie. No matter if authentication succeeded or failed.

        await self.session_auth_user(
            self.get_body_argument("username"),
            self.get_body_argument("password"),
            sign_rejection=False,
        )

        if not self.session.is_authenticated:
            raise self.unauthorized()

        self.write(self.session.ajax_id)


class Logout(app_session.Mixin, AjaxMixin, BaseHandler):
    """
    Logout handles url for logout. It is used for both ajax and non-ajax
    requests.
    """

    async def get(self, *args, **kwargs):
        del args, kwargs
        await self.init_session()
        self.session_logout()
        self.sid_to_cookies()
        self.enhance_headers()
        self.write("OK")


class StaticFileMayBe(StaticFile):
    # pylint: disable=abstract-method
    def get(self, *args, **kwargs):
        # pylint: disable=signature-differs
        # pylint: disable=invalid-overridden-method
        if not os.path.isdir(str(self.root)):
            # spa is probably not installed
            self.set_status(404, "Not Found")
            return None
        return super().get(*args, **kwargs)


def get_routes(
    url_prefix,
    app_dir,
    fallback_page_path,
    session_storage: session.Storage,
):
    sessions = dict(session_storage=session_storage)
    static_path = lambda dir="": dict(path=os.path.join(app_dir, dir))
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
        (f"{url_prefix}manifest.json", StaticFileMayBe, static_path()),
        (f"{url_prefix}login", Login, {**sessions, **pages}),
        (f"{url_prefix}logout", Logout, sessions),
        (f"{url_prefix}.*", SPAHandler, pages),
    ]
