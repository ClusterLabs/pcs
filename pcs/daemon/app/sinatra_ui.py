import os.path

from pcs.daemon import ruby_pcsd, session
from pcs.daemon.app import session as app_session
from pcs.daemon.app.common import BaseHandler
from pcs.daemon.app.sinatra_common import Sinatra
from pcs.daemon.app.ui_common import AjaxMixin, StaticFile


class SinatraGui(app_session.Mixin, Sinatra):
    """
    SinatraGui is base class for handlers which calls the Sinatra GUI functions.
    It adds work with session.
    It adds default GET and POST handlers with hook before Sinatra is called.
    """

    can_use_sinatra = True

    def initialize(self, session_storage, ruby_pcsd_wrapper):
        # pylint: disable=arguments-differ
        app_session.Mixin.initialize(self, session_storage)
        Sinatra.initialize(self, ruby_pcsd_wrapper)
        # add security related headers to all responses
        self.enhance_headers()

    def before_sinatra_use(self):
        pass

    async def handle_sinatra_request(self):
        await self.init_session()
        self.before_sinatra_use()
        if self.can_use_sinatra:
            result = await self.ruby_pcsd_wrapper.request_gui(
                self.request,
                self.session.username,
                self.session.groups,
                self.session.is_authenticated,
            )
            self.send_sinatra_result(result)

    async def get(self, *args, **kwargs):
        del args, kwargs
        await self.handle_sinatra_request()

    async def post(self, *args, **kwargs):
        del args, kwargs
        await self.handle_sinatra_request()


class SinatraGuiProtected(SinatraGui):
    """
    SinatraGuiProtected handles urls that calls the non-ajax Sinatra GUI
    functions. These urls provides real pages.
    """

    def before_sinatra_use(self):
        # sinatra must not have a session at this moment. So the response from
        # sinatra does not contain propriate cookie. Now it is new daemons' job
        # to send this cookies.
        self.sid_to_cookies()

        if not self.session.is_authenticated:
            self.redirect("/login", status=302)  # redirect temporary (302)
            self.can_use_sinatra = False


class SinatraAjaxProtected(SinatraGui, AjaxMixin):
    # pylint: disable=too-many-ancestors
    """
    SinatraAjaxProtected handles urls that calls the ajax Sinatra GUI functions.
    It allows to use this urls only for ajax calls.
    """

    @property
    def is_authorized(self):
        # User is authorized only to perform ajax calls to prevent CSRF attack.
        return self.is_ajax and self.session.is_authenticated

    def before_sinatra_use(self):
        # TODO this is for sinatra compatibility, review it.
        if self.was_sid_in_request_cookies():
            self.put_request_cookies_sid_to_response_cookies_sid()
        if not self.is_authorized:
            raise self.unauthorized()


class Login(SinatraGui, AjaxMixin):
    # pylint: disable=too-many-ancestors
    """
    Login handles urls that cares about loging process.
    It displays a login form (taken from Sinatra), process data sent by the
    form, call an authentication mechanism and uses session for expressing
    a result of the authentication mechanism.
    """

    def before_sinatra_use(self):
        # TODO this is for sinatra compatibility, review it.
        if self.was_sid_in_request_cookies():
            self.put_request_cookies_sid_to_response_cookies_sid()

    async def post(self, *args, **kwargs):
        # This is the way of old (ruby) pcsd. Post login generates a session
        # cookie. No matter if authentication succeeded or failed.
        await self.session_auth_user(
            self.get_body_argument("username"),
            self.get_body_argument("password"),
            sign_rejection=not self.is_ajax,
        )

        if self.session.is_authenticated:
            self.__success_response()
        else:
            self.__failed_response()

    def __success_response(self):
        if self.is_ajax:
            self.write(self.session.ajax_id)
        else:
            self.redirect("/manage", status=303)  # post -> get resource (303)

    def __failed_response(self):
        if self.is_ajax:
            raise self.unauthorized()

        self.redirect("/login", status=303)  # post -> get resource (303)


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
        if self.is_ajax:
            self.write("OK")
        else:
            self.redirect("/login", status=302)  # redirect temporary (302)


def get_routes(
    session_storage: session.Storage,
    ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
    public_dir,
):
    ruby_wrapper = dict(ruby_pcsd_wrapper=ruby_pcsd_wrapper)
    sessions = dict(session_storage=session_storage)
    static_path = lambda dir: dict(path=os.path.join(public_dir, dir))
    return [
        (r"/css/(.*)", StaticFile, static_path("css")),
        (r"/js/(.*)", StaticFile, static_path("js")),
        (r"/images/(.*)", StaticFile, static_path("images")),
        (r"/login", Login, {**sessions, **ruby_wrapper}),
        (r"/logout", Logout, sessions),
        # The protection by session was moved from ruby code to python code
        # (tornado).
        (
            r"/($|manage/?$|permissions/?$|managec/.+/main)",
            SinatraGuiProtected,
            {**sessions, **ruby_wrapper},
        ),
        (r"/.*", SinatraAjaxProtected, {**sessions, **ruby_wrapper}),
    ]
