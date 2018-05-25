import os.path

from tornado.locks import Lock
from tornado.web import Application, RequestHandler, StaticFileHandler, Finish

from pcs.daemon import ruby_pcsd, session, app_session
from pcs.daemon.http_server import HttpsServerManage


class EnhanceHeadersMixin:
    """
    EnhanceHeadersMixin allows to add security headers to GUI urls.
    """
    def set_strict_transport_security(self):
        # rhbz 1558063
        # The HTTP Strict-Transport-Security response header (often abbreviated
        # as HSTS)  lets a web site tell browsers that it should only be
        # accessed using HTTPS, instead of using HTTP.
        self.set_header("Strict-Transport-Security", "max-age=604800")

    def set_header_nosniff_content_type(self):
        # The X-Content-Type-Options response HTTP header is a marker used by
        # the server to indicate that the MIME types advertised in the
        # Content-Type headers should not be changed and be followed. This
        # allows to opt-out of MIME type sniffing, or, in other words, it is a
        # way to say that the webmasters knew what they were doing.
        self.set_header("X-Content-Type-Options", "nosniff")

    def enhance_headers(self):
        self.set_header_nosniff_content_type()

        # The X-Frame-Options HTTP response header can be used to indicate
        # whether or not a browser should be allowed to render a page in a
        # <frame>, <iframe> or <object> . Sites can use this to avoid
        # clickjacking attacks, by ensuring that their content is not embedded
        # into other sites.
        self.set_header("X-Frame-Options", "SAMEORIGIN")

        # The HTTP X-XSS-Protection response header is a feature of Internet
        # Explorer, Chrome and Safari that stops pages from loading when they
        # detect reflected cross-site scripting (XSS) attacks. Although these
        # protections are largely unnecessary in modern browsers when sites
        # implement a strong Content-Security-Policy that disables the use of
        # inline JavaScript ('unsafe-inline'), they can still provide
        # protections for users of older web browsers that don't yet support
        # CSP.
        self.set_header("X-Xss-Protection", "1; mode=block")

class BaseHandler(EnhanceHeadersMixin, RequestHandler):
    """
    BaseHandler adds for all urls Strict-Transport-Security.
    """
    def set_default_headers(self):
        self.set_strict_transport_security()

    def data_received(self, chunk):
        # abstract method `data_received` does need to be overriden. This
        # method should be implemented to handle streamed request data.
        # BUT we currently do not plan to use it SO:
        #pylint: disable=abstract-method
        pass

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

class Sinatra(BaseHandler):
    """
    Sinatra is base class for handlers which calls the Sinatra via wrapper.
    It accept ruby wrapper during initialization. It also provides method for
    transformation result from sinatra to http response.
    """
    def initialize(self, ruby_pcsd_wrapper: ruby_pcsd.Wrapper):
        #pylint: disable=arguments-differ
        self.__ruby_pcsd_wrapper = ruby_pcsd_wrapper

    def send_sinatra_result(self, result: ruby_pcsd.SinatraResult):
        for name, value in result.headers.items():
            self.set_header(name, value)
        self.set_status(result.status)
        self.write(result.body)

    @property
    def ruby_pcsd_wrapper(self):
        return self.__ruby_pcsd_wrapper

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

class SinatraRemote(Sinatra):
    """
    SinatraRemote is handler for urls which should be directed to the Sinatra
    remote (non-GUI) functions.
    """
    async def handle_sinatra_request(self):
        result = await self.ruby_pcsd_wrapper.request_remote(self.request)
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

class SyncConfigMutualExclusive(SinatraRemote):
    """
    SyncConfigMutualExclusive handles urls which should be directed to the
    Sinatra remote (non-GUI) functions that can not run at the same time as
    config synchronization. The exclusivity is achived by sync_config_lock.
    """
    def initialize(
        self, sync_config_lock: Lock, ruby_pcsd_wrapper: ruby_pcsd.Wrapper
    ):
        #pylint: disable=arguments-differ
        super().initialize(ruby_pcsd_wrapper)
        self.__sync_config_lock = sync_config_lock

    async def get(self, *args, **kwargs):
        async with self.__sync_config_lock:
            await super().get(*args, **kwargs)

    async def post(self, *args, **kwargs):
        async with self.__sync_config_lock:
            await super().get(*args, **kwargs)

class SetCerts(SinatraRemote):
    """
    SetCerts handles url for setting new certificate and key. It calls the
    Sinatra for setting certificate and key and in the case of the success it
    will take care of notify of http sever about this change.
    """
    def initialize(
        self,
        ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
        https_server_manage: HttpsServerManage
    ):
        #pylint: disable=arguments-differ
        super().initialize(ruby_pcsd_wrapper)
        self.__https_server_manage = https_server_manage

    async def handle_sinatra_request(self):
        result = await self.ruby_pcsd_wrapper.request_remote(self.request)
        if result.status == 200:
            self.__https_server_manage.reload_certs()
        self.send_sinatra_result(result)


def make_app(
    session_storage: session.Storage,
    ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
    sync_config_lock: Lock,
    public_dir,
    https_server_manage: HttpsServerManage,
    disable_gui=False,
    debug=False
):
    """
    https_server_manage -- allows to controll the server (specifically reload
        its SSL certificates). A relevant handler should get this object via
        the method `initialize`.
    """
    ruby_wrapper = dict(ruby_pcsd_wrapper=ruby_pcsd_wrapper)
    lock = dict(sync_config_lock=sync_config_lock)
    sessions = dict(session_storage=session_storage)

    routes = [
        # Urls protected by tokens. It is still done by ruby pcsd.
        (r"/run_pcs", SinatraRemote, ruby_wrapper),
        (
            r"/remote/set_certs",
            SetCerts,
            {**ruby_wrapper, "https_server_manage": https_server_manage}
        ),
        (
            r"/remote/(set_sync_options|set_configs)",
            SyncConfigMutualExclusive,
            {**ruby_wrapper, **lock}
        ),
        (r"/remote/.*", SinatraRemote, ruby_wrapper),
    ]

    if not disable_gui:
        static_path = lambda dir: dict(path=os.path.join(public_dir, dir))
        routes.extend([
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
        ])

    return Application(routes, debug=debug)
