import base64
import json

from tornado.web import(
    RequestHandler,
    Finish,
)
from tornado.gen import Task, multi, convert_yielded
from tornado.httputil import split_host_and_port
from tornado.process import Subprocess

from pcs.daemon.auth import authorize_user
from pcs.daemon.session import SessionMixin

DEBUG = False

# abstract method `data_received` does need to be overriden. This method should
# be implemented to handle streamed request data.
# BUT:
# * static files are not streamed
# * in other handlers we currently do not plan to use it:
# SO:
#pylint: disable=abstract-method

class EnhnceHeadersMixin:
    def enhance_headers(self):
        """
        Put headers to be compatible with old (ruby) pcsd
        """

        # The X-Content-Type-Options response HTTP header is a marker used by
        # the server to indicate that the MIME types advertised in the
        # Content-Type headers should not be changed and be followed. This
        # allows to opt-out of MIME type sniffing, or, in other words, it is a
        # way to say that the webmasters knew what they were doing.
        self.set_header("X-Content-Type-Options", "nosniff")

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


def pcsd_log(*arg_list):
    if DEBUG:
        print('---------------------------------------------------------------')
        for arg in arg_list:
            print(arg)
        print('---------------------------------------------------------------')

def build_pcsd_request(request, session=None):
    host, port = split_host_and_port(request.host)
    return {
        "config": {
            "user_pass_dir": "/root/pcs/pcsd/",
            # Session was taken from ruby. However, some session information is
            # needed for ruby code (e.g. rendering some parts of templates). So
            # this information must be sent to ruby by another way.
            "username": session.username,
            "groups": session.groups,
            "is_authenticated": session.is_authenticated,
        },
        "env": {
            # "GATEWAY_INTERFACE": "CGI/1.1",
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
            #TODO #pylint: disable=fixme
            # "SERVER_SOFTWARE":
            #     "WEBrick/1.3.1 (Ruby/2.0.0/2014-11-13) OpenSSL/1.0.1e"
            # ,
            "HTTP_HOST": request.host,
            "HTTP_ACCEPT": "*/*",
            "HTTP_COOKIE": ";".join([
                value.OutputString()
                for value in request.cookies.values()
            ]),
            "HTTPS": "on" if request.protocol == "https" else "off",
            # "SSL_CLIENT_CERT": "",
            # "SSL_CIPHER": "DHE-RSA-AES256-GCM-SHA384",
            # "SSL_PROTOCOL": "TLSv1/SSLv3",
            # "SSL_CIPHER_USEKEYSIZE": "256",
            # "SSL_CIPHER_ALGKEYSIZE": "256",
            "HTTP_VERSION": request.version,
            "REQUEST_PATH": request.uri,
        }
    }

async def run_pscd(request):
    pcsd_ruby = Subprocess(
        [
            "ruby",
            "-I", "/root/projects/pcs/pcsd",
            "/root/projects/pcs/pcsd/sinatra_cmdline_proxy.rb"
        ],
        stdin=Subprocess.STREAM,
        stdout=Subprocess.STREAM,
        stderr=Subprocess.STREAM,
    )
    pcsd_log(json.dumps(request))

    await Task(pcsd_ruby.stdin.write, str.encode(json.dumps(request)))
    pcsd_ruby.stdin.close()
    result_json, error = await multi([
        Task(pcsd_ruby.stdout.read_until_close),
        Task(pcsd_ruby.stderr.read_until_close),
    ])
    return result_json, error

class Sinatra(SessionMixin, RequestHandler):
    def _process_pcsd_result(self, result_json):
        try:
            result = json.loads(result_json)
        except Exception as e:
            pcsd_log(e, result_json)
            raise e

        for name, value in result["headers"].items():
            self.set_header(name, value)

        self.set_status(result["status"])
        self.write(base64.b64decode(result["body"]))

    async def proxy_to_sinatra(self):
        request = build_pcsd_request(self.request, self.session)
        result_json, dummy_err = await convert_yielded(run_pscd(request))
        self._process_pcsd_result(result_json)

    async def get(self, *args, **kwargs):
        await self.proxy_to_sinatra()

    def redirect_temporary(self, url):
        """
        Send a redirect to the given (optionally relative) URL.

        see https://serverfault.com/a/391182

        A 302 redirect indicates that the redirect is temporary -- clients
        should check back at the original URL in future requests.
        """
        self.redirect(url, status=302)

    def redirect_post_to_get_resource(self, url):
        """
        Send a redirect to the given (optionally relative) URL.

        see https://serverfault.com/a/391182

        A 303 redirect is meant to redirect a POST request to a GET resource
        (otherwise, the client assumes that the request method for the new
        location is the same as for the original resource).

        RFC 1945 and RFC 2068 specify that the client is not allowed to change
        the method on the redirected request.  However, most existing user
        agent implementations treat 302 as if it were a 303 response,
        performing a GET on the Location field-value regardless of the original
        request method.
        """
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
