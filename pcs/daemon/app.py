import base64
import json
from contextlib import contextmanager
from os.path import dirname, realpath, abspath, join as join_path
from time import time

from tornado.gen import Task, multi, convert_yielded, sleep
from tornado.httputil import split_host_and_port
from tornado.process import Subprocess
from tornado.web import Application, RequestHandler, StaticFileHandler, Finish

from pcs.daemon.http_server import HttpsServerManage
from pcs.daemon.auth import authorize_user
from pcs.daemon.session import SessionMixin, SessionStorage

# abstract method `data_received` does need to be overriden. This method should
# be implemented to handle streamed request data.
# BUT:
# * static files are not streamed
# * in other handlers we currently do not plan to use it:
# SO:
#pylint: disable=abstract-method

PCSD_DIR = realpath(dirname(abspath(__file__))+ "/../../pcsd")
PUBLIC_DIR = join_path(PCSD_DIR, "public")
PCSD_CMD =  "sinatra_cmdline_proxy.rb"

class EnhnceHeadersMixin:
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
            self.request.headers.get("X_Requested_With", default=None)
            ==
            "XMLHttpRequest"
        )

    def unauthorized(self):
        self.set_status(401)
        self.write('{"notauthorized":"true"}')
        return Finish()

def build_pcsd_request(request, session=None):
    host, port = split_host_and_port(request.host)
    return {
        "config": {
            "type": "sinatra_request",
            "user_pass_dir": PCSD_DIR,
            # Session was taken from ruby. However, some session information is
            # needed for ruby code (e.g. rendering some parts of templates). So
            # this information must be sent to ruby by another way.
            "username": session.username,
            "groups": session.groups,
            "is_authenticated": session.is_authenticated,
        },
        "env": {
            "PATH_INFO": request.path,
            "QUERY_STRING": request.query,
            "REMOTE_ADDR": request.remote_ip,
            "REMOTE_HOST": request.host,
            "REQUEST_METHOD": request.method,
            "REQUEST_URI": f"{request.protocol}://{request.host}{request.uri}",
            "SCRIPT_NAME": "",
            "SERVER_NAME": host,
            "SERVER_PORT": port,
            "SERVER_PROTOCOL": request.version,
            "HTTP_HOST": request.host,
            "HTTP_ACCEPT": "*/*",
            "HTTP_COOKIE": ";".join([
                v.OutputString() for v in request.cookies.values()
            ]),
            "HTTPS": "on" if request.protocol == "https" else "off",
            "HTTP_VERSION": request.version,
            "REQUEST_PATH": request.uri,
        }
    }

async def run_pscd(request):
    pcsd_ruby = Subprocess(
        ["ruby", "-I", PCSD_DIR, join_path(PCSD_DIR, PCSD_CMD)],
        stdin=Subprocess.STREAM,
        stdout=Subprocess.STREAM,
        stderr=Subprocess.STREAM,
    )

    await Task(pcsd_ruby.stdin.write, str.encode(json.dumps(request)))
    pcsd_ruby.stdin.close()
    result_json, dummy_error = await multi([
        Task(pcsd_ruby.stdout.read_until_close),
        Task(pcsd_ruby.stderr.read_until_close),
    ])
    return result_json

class Sinatra(SessionMixin, RequestHandler):
    def _process_pcsd_result(self, result_json):
        try:
            result = json.loads(result_json)
        except Exception as e:
            raise e

        for name, value in result["headers"].items():
            self.set_header(name, value)

        self.set_status(result["status"])
        self.write(base64.b64decode(result["body"]))

    async def proxy_to_sinatra(self):
        request = build_pcsd_request(self.request, self.session)
        self._process_pcsd_result(await convert_yielded(run_pscd(request)))

    async def get(self, *args, **kwargs):
        await self.proxy_to_sinatra()

    def redirect_temporary(self, url):
        self.redirect(url, status=302)

    def redirect_post_to_get_resource(self, url):
        self.redirect(url, status=303)

class SinatraGuiProtected(Sinatra, EnhnceHeadersMixin):
    async def get(self, *args, **kwargs):
        # sinatra must not have a session at this moment. So the response from
        # sinatra does not contain propriate cookie. Now it is new daemons' job
        # to send this cookies.
        self.ensure_session()

        if not self.session.is_authenticated:
            self.enhance_headers()
            self.redirect_temporary("/login")
            return

        await self.proxy_to_sinatra()

class SinatraAjaxProtected(Sinatra, EnhnceHeadersMixin, AjaxMixin):
    @property
    def is_authorized(self):
        # User is authorized only to perform ajax calls to prevent CSRF attack.
        return self.is_ajax and self.session.is_authenticated

    async def get(self, *args, **kwargs):
        #TODO this is for sinatra compatibility, review it.
        if self.was_sid_in_request_cookies():
            self.put_request_cookies_sid_to_response_cookies_sid()
        if not self.is_authorized:
            self.enhance_headers()
            raise self.unauthorized()
        await self.proxy_to_sinatra()

class Login(Sinatra, EnhnceHeadersMixin, AjaxMixin):
    async def get(self, *args, **kwargs):
        #TODO this is for sinatra compatibility, review it.
        if self.was_sid_in_request_cookies():
            self.put_request_cookies_sid_to_response_cookies_sid()
        await self.proxy_to_sinatra()

    async def post(self, *args, **kwargs):
        # This is the way of old (ruby) pcs. Post login generate session cookie.
        # No mather if authentication succeeded or failed.
        self.enhance_headers()

        auth_user = await authorize_user(
            self.get_argument("username"),
            self.get_argument("password")
        )

        if auth_user:
            self.ensure_session()
            self.session_login(auth_user.name, auth_user.groups)
            self.__success_response()
        else:
            self.__failed_response(self.get_argument("username"))

    def __success_response(self):
        if self.is_ajax:
            self.write(self.session.ajax_id)
        else:
            self.redirect_post_to_get_resource("/manage")

    def __failed_response(self, username):
        if self.is_ajax:
            raise self.unauthorized()

        self.ensure_session()
        self.session_login_failed(username)
        self.redirect_post_to_get_resource("/login")

class LoginStatus(SessionMixin, RequestHandler, EnhnceHeadersMixin, AjaxMixin):
    # This is for ajax. However no-ajax requests are allowed. It is how it works
    # in ruby.
    def get(self, *args, **kwargs):
        self.enhance_headers()
        if not self.session.is_authenticated:
            raise self.unauthorized()
        #TODO this is for sinatra compatibility, review it.
        if self.was_sid_in_request_cookies():
            self.put_request_cookies_sid_to_response_cookies_sid()
        self.write(self.session.ajax_id)

class Logout(Sinatra, EnhnceHeadersMixin, AjaxMixin):
    def get(self, *args, **kwargs):
        self.session_logout()
        self.ensure_session()
        self.enhance_headers()
        if self.is_ajax:
            self.write("OK")
        else:
            self.redirect_temporary("/login")

class RegenerateCertHandler(RequestHandler):
    def initialize(self, https_server_manage: HttpsServerManage):
        #pylint: disable=arguments-differ
        self.https_server_manage = https_server_manage

    def get(self, *args, **kwargs):
        self.https_server_manage.regenerate_certificate()
        self.write("CERTIFICATE_RELOADED")

class StaticFile(EnhnceHeadersMixin, StaticFileHandler):
    def initialize(self, path, default_filename=None):
        super().initialize(path, default_filename)
        # In ruby server the header X-Content-Type-Options was sent and we
        # keep it here to keep compatibility for simplifying testing. There is
        # no another special reason for it. So, maybe, it can be removed in
        # future.
        self.set_header_nosniff_content_type()

def static_route(url_prefix, public_subdir):
    return (
        rf"{url_prefix}(.*)",
        StaticFile,
        dict(
            path=join_path(PUBLIC_DIR, public_subdir)
        )
    )

class SyncConfigLock:
    def __init__(self):
        self.__is_locked = False

    @property
    def is_locked(self):
        return self.__is_locked

    @contextmanager
    def lock(self):
        self.__is_locked = True
        yield
        self.__is_locked = False

async def sync_configs(sync_config_lock: SyncConfigLock):
    if sync_config_lock.is_locked:
        return int(time())

    with sync_config_lock.lock():
        result_json = await convert_yielded(run_pscd(
            {"config": {"type": "sync_configs"}}
        ))
        return json.loads(result_json)["next"]

class SyncConfigMutualExclusive(Sinatra):
    def initialize(self, sync_config_lock, session_storage):
        #pylint: disable=arguments-differ
        super().initialize(session_storage)
        self.sync_config_lock = sync_config_lock

    async def get(self, *args, **kwargs):
        #TODO avoid infinity
        while self.sync_config_lock.is_locked:
            await sleep(0.1)
        with self.sync_config_lock.lock():
            await self.proxy_to_sinatra()

def make_app(
    session_storage: SessionStorage,
    sync_config_lock: SyncConfigLock,
    https_server_manage: HttpsServerManage
):
    session_route = lambda pattern, handler: (pattern, handler, dict(
        session_storage=session_storage
    ))
    return Application(
        [
            static_route("/css/", "css"),
            static_route("/js/", "js"),
            static_route("/images/", "images"),
            # Urls protected by tokens. It is stil done by ruby.
            session_route(r"/run_pcs", Sinatra),
            session_route(r"/remote/auth", Sinatra),
            (
                r"/remote/(set_sync_options|set_configs)",
                SyncConfigMutualExclusive,
                dict(
                    session_storage=session_storage,
                    sync_config_lock=sync_config_lock,
                )
            ),
            session_route(r"/remote/.*", Sinatra),

            (
                r"/daemon-maintenance/reload-cert",
                RegenerateCertHandler,
                {"https_server_manage": https_server_manage},
            ),

            session_route(r"/login", Login),
            session_route(r"/login-status", LoginStatus),
            session_route(r"/logout", Logout),

            #The protection by session was moved from ruby code to python code
            #(tornado).
            session_route(
                r"/($|manage$|permissions$|managec/.+/main)",
                SinatraGuiProtected,
            ),

            session_route(r"/.*", SinatraAjaxProtected),
        ],
        debug=True,
    )
