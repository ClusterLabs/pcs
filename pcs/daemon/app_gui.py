import os.path

from tornado.web import StaticFileHandler, Finish

from pcs.daemon import app_session, ruby_pcsd, session
from pcs.daemon.app_common import BaseHandler, EnhanceHeadersMixin, Sinatra

class AjaxMixin:
    """
    AjaxMixin adds methods for an ajax request detection and common unauthorized
    response.
    """
    @property
    def is_ajax(self):
        return (
            self.request.headers.get("X-Requested-With", default=None)
            ==
            "XMLHttpRequest"
        )

    def unauthorized(self):
        self.set_status(401)
        self.write('{"notauthorized":"true"}')
        return Finish()

class SinatraGui(app_session.Mixin, Sinatra):
    """
    SinatraGui is base class for handlers which calls the Sinatra GUI functions.
    It adds work with session.
    It adds default GET and POST handlers with hook before Sinatra is called.
    """
    can_use_sinatra = True

    def initialize(self, session_storage, ruby_pcsd_wrapper):
        #pylint: disable=arguments-differ
        app_session.Mixin.initialize(self, session_storage)
        Sinatra.initialize(self, ruby_pcsd_wrapper)

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
        await self.handle_sinatra_request()

    async def post(self, *args, **kwargs):
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
            self.enhance_headers()
            self.redirect("/login", status=302) #redirect temporary (302)
            self.can_use_sinatra = False

class SinatraAjaxProtected(SinatraGui, AjaxMixin):
    """
    SinatraAjaxProtected handles urls that calls the ajax Sinatra GUI functions.
    It allows to use this urls only for ajax calls.
    """
    @property
    def is_authorized(self):
        # User is authorized only to perform ajax calls to prevent CSRF attack.
        return self.is_ajax and self.session.is_authenticated

    def before_sinatra_use(self):
        #TODO this is for sinatra compatibility, review it.
        if self.was_sid_in_request_cookies():
            self.put_request_cookies_sid_to_response_cookies_sid()
        if not self.is_authorized:
            self.enhance_headers()
            raise self.unauthorized()

class Login(SinatraGui, AjaxMixin):
    """
    Login handles urls that cares about loging process.
    It displays a login form (taken from Sinatra), process data sent by the
    form, call an authentication mechanism and uses session for expressing
    a result of the authentication mechanism.
    """
    def before_sinatra_use(self):
        #TODO this is for sinatra compatibility, review it.
        if self.was_sid_in_request_cookies():
            self.put_request_cookies_sid_to_response_cookies_sid()

    async def post(self, *args, **kwargs):
        # This is the way of old (ruby) pcsd. Post login generates a session
        # cookie. No matter if authentication succeeded or failed.
        self.enhance_headers()

        await self.session_auth_user(
            self.get_body_argument("username"),
            self.get_body_argument("password"),
            sign_rejection=not self.is_ajax
        )

        if self.session.is_authenticated:
            self.__success_response()
        else:
            self.__failed_response()

    def __success_response(self):
        if self.is_ajax:
            self.write(self.session.ajax_id)
        else:
            self.redirect("/manage", status=303) #post -> get resource (303)

    def __failed_response(self):
        if self.is_ajax:
            raise self.unauthorized()

        self.redirect("/login", status=303) #post -> get resource (303)

class LoginStatus(app_session.Mixin, AjaxMixin, BaseHandler):
    """
    LoginStatus handles urls for obtaining current login status via ajax.
    """
    # This is for ajax. However, non-ajax requests are allowed as well. It
    # worked the same way in ruby.
    async def get(self, *args, **kwargs):
        await self.init_session()
        self.enhance_headers()
        if not self.session.is_authenticated:
            raise self.unauthorized()
        self.sid_to_cookies()
        self.write(self.session.ajax_id)

class Logout(app_session.Mixin, AjaxMixin, BaseHandler):
    """
    Logout handles url for logout. It is used for both ajax and non-ajax
    requests.
    """
    async def get(self, *args, **kwargs):
        await self.init_session()
        self.session_logout()
        self.sid_to_cookies()
        self.enhance_headers()
        if self.is_ajax:
            self.write("OK")
        else:
            self.redirect("/login", status=302) #redirect temporary (302)

class StaticFile(EnhanceHeadersMixin, StaticFileHandler):
    # abstract method `data_received` does need to be overriden. This
    # method should be implemented to handle streamed request data.
    # BUT static files are not streamed SO:
    #pylint: disable=abstract-method
    def initialize(self, path, default_filename=None):
        #pylint: disable=arguments-differ
        super().initialize(path, default_filename)
        # In ruby server the header X-Content-Type-Options was sent and we
        # keep it here to keep compatibility for simplifying testing. There is
        # no another special reason for it. So, maybe, it can be removed in
        # future.
        self.set_header_nosniff_content_type()
        self.set_strict_transport_security()

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
        (r"/login-status", LoginStatus, sessions),
        (r"/logout", Logout, sessions),

        # The protection by session was moved from ruby code to python code
        # (tornado).
        (
            r"/($|manage$|permissions$|managec/.+/main)",
            SinatraGuiProtected,
            {**sessions, **ruby_wrapper}
        ),

        (r"/.*", SinatraAjaxProtected, {**sessions, **ruby_wrapper}),
    ]
