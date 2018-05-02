import os.path

from tornado.locks import Lock
from tornado.web import Application, RequestHandler, StaticFileHandler, Finish

from pcs.daemon import ruby_pcsd, session
from pcs.daemon.http_server import HttpsServerManage
from pcs.daemon.auth import authorize_user

# abstract method `data_received` does need to be overriden. This method should
# be implemented to handle streamed request data.
# BUT:
# * static files are not streamed
# * in other handlers we currently do not plan to use it:
# SO:
#pylint: disable=abstract-method

class BaseHandler(RequestHandler):
    def set_default_headers(self):
        #bz 1558063
        self.set_header("Strict-Transport-Security", "max-age=604800")

class EnhanceHeadersMixin:
    def set_header_nosniff_content_type(self):
        # The X-Content-Type-Options response HTTP header is a marker used by
        # the server to indicate that the MIME types advertised in the
        # Content-Type headers should not be changed and be followed. This
        # allows to opt-out of MIME type sniffing, or, in other words, it is a
        # way to say that the webmasters knew what they were doing.
        self.set_header("X-Content-Type-Options", "nosniff")

    def enhance_headers(self):
        """
        Put headers to be compatible with old (ruby) pcsd
        """
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

class AjaxMixin:
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
    def initialize(self, ruby_pcsd_wrapper):
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

class SinatraGui(session.Mixin, EnhanceHeadersMixin, Sinatra):
    can_use_sinatra = True

    def initialize(self, session_storage, ruby_pcsd_wrapper):
        #pylint: disable=arguments-differ
        session.Mixin.initialize(self, session_storage)
        Sinatra.initialize(self, ruby_pcsd_wrapper)

    def before_sinatra_use(self):
        pass

    async def handle_sinatra_request(self):
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
    async def handle_sinatra_request(self):
        result = await self.ruby_pcsd_wrapper.request_remote(self.request)
        self.send_sinatra_result(result)

    async def get(self, *args, **kwargs):
        await self.handle_sinatra_request()

    async def post(self, *args, **kwargs):
        await self.handle_sinatra_request()

class SinatraGuiProtected(SinatraGui):
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
    def before_sinatra_use(self):
        #TODO this is for sinatra compatibility, review it.
        if self.was_sid_in_request_cookies():
            self.put_request_cookies_sid_to_response_cookies_sid()

    async def post(self, *args, **kwargs):
        # This is the way of old (ruby) pcs. Post login generate session cookie.
        # No mather if authentication succeeded or failed.
        self.enhance_headers()

        auth_user = await authorize_user(
            self.get_argument("username"),
            self.get_argument("password")
        )

        if auth_user:
            self.sid_to_cookies()
            self.session_login(auth_user.name, auth_user.groups)
            self.__success_response()
        else:
            self.__failed_response(self.get_argument("username"))

    def __success_response(self):
        if self.is_ajax:
            self.write(self.session.ajax_id)
        else:
            self.redirect("/manage", status=303) #post -> get resource (303)

    def __failed_response(self, username):
        if self.is_ajax:
            raise self.unauthorized()

        self.sid_to_cookies()
        self.session_login_failed(username)
        self.redirect("/login", status=303) #post -> get resource (303)

class LoginStatus(session.Mixin, EnhanceHeadersMixin, AjaxMixin, BaseHandler):
    # This is for ajax. However no-ajax requests are allowed. It is how it works
    # in ruby.
    def get(self, *args, **kwargs):
        self.enhance_headers()
        if not self.session.is_authenticated:
            raise self.unauthorized()
        self.sid_to_cookies()
        self.write(self.session.ajax_id)

class Logout(session.Mixin, EnhanceHeadersMixin, AjaxMixin, BaseHandler):
    def get(self, *args, **kwargs):
        self.session_logout()
        self.sid_to_cookies()
        self.enhance_headers()
        if self.is_ajax:
            self.write("OK")
        else:
            self.redirect("/login", status=302) #redirect temporary (302)

class StaticFile(EnhanceHeadersMixin, StaticFileHandler):
    def initialize(self, path, default_filename=None):
        #pylint: disable=arguments-differ
        super().initialize(path, default_filename)
        # In ruby server the header X-Content-Type-Options was sent and we
        # keep it here to keep compatibility for simplifying testing. There is
        # no another special reason for it. So, maybe, it can be removed in
        # future.
        self.set_header_nosniff_content_type()

class SyncConfigMutualExclusive(SinatraRemote):
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
    https_server_manage -- is there to be able controll the server (specifically
        reload the certificates). A relevant handler should get this object via
        the method `initialize`.
    """
    ruby_wrapper = dict(ruby_pcsd_wrapper=ruby_pcsd_wrapper)
    lock= dict(sync_config_lock=sync_config_lock)
    sessions = dict(session_storage=session_storage)

    routes = [
        # Urls protected by tokens. It is stil done by ruby.
        (r"/run_pcs", SinatraRemote, ruby_wrapper),
        (r"/remote/auth", SinatraRemote, ruby_wrapper),
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
            ("/css/(.*)", StaticFile, static_path("css")),
            ("/js/(.*)", StaticFile, static_path("js")),
            ("/images/(.*)", StaticFile, static_path("images")),

            (r"/login", Login, {**sessions, **ruby_wrapper}),
            (r"/login-status", LoginStatus, sessions),
            (r"/logout", Logout, sessions),

            #The protection by session was moved from ruby code to python code
            #(tornado).
            (
                r"/($|manage$|permissions$|managec/.+/main)",
                SinatraGuiProtected,
                {**sessions, **ruby_wrapper}
            ),

            (r"/.*", SinatraAjaxProtected, {**sessions, **ruby_wrapper}),
        ])

    return Application(routes, debug=debug)
