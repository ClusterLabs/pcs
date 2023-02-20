from typing import (
    Any,
    Iterable,
    Optional,
    Type,
)

from tornado.web import (
    Finish,
    HTTPError,
)
from tornado.web import RedirectHandler as TornadoRedirectHandler
from tornado.web import RequestHandler

RoutesType = Iterable[
    tuple[str, Type[RequestHandler], Optional[dict[str, Any]]]
]


class EnhanceHeadersMixin:
    """
    EnhanceHeadersMixin allows to add security headers to GUI urls.
    """

    def set_header_strict_transport_security(self) -> None:
        # rhbz#1558063 rhbz#2097392
        # The HTTP Strict-Transport-Security response header (often abbreviated
        # as HSTS) lets a web site tell browsers that it should only be
        # accessed using HTTPS, instead of using HTTP.
        # Do not set "includeSubDomains" as that would affect all web sites and
        # applications running on any subdomain of the domain where pcs web UI
        # is running. The fact that pcs web UI runs on a specific port doesn't
        # matter, subdomains would still be affected.
        self.set_header("Strict-Transport-Security", "max-age=63072000")

    def set_header_nosniff_content_type(self) -> None:
        # The X-Content-Type-Options response HTTP header is a marker used by
        # the server to indicate that the MIME types advertised in the
        # Content-Type headers should not be changed and be followed. This
        # allows to opt-out of MIME type sniffing, or, in other words, it is a
        # way to say that the webmasters knew what they were doing.
        self.set_header("X-Content-Type-Options", "nosniff")

    def clear_header_server(self) -> None:
        # The Server header describes the software used by the origin server
        # that handled the request — that is, the server that generated the
        # response.
        #
        # rhbz 2058278
        # When a HTTP request is made against a cluster node running pcsd, the
        # HTTP response contains HTTP Server name in its headers.
        # This is perceived as a security threat.
        self.clear_header("Server")

    def set_header_frame_options(self) -> None:
        # The X-Frame-Options HTTP response header can be used to indicate
        # whether or not a browser should be allowed to render a page in a
        # <frame>, <iframe> or <object> . Sites can use this to avoid
        # clickjacking attacks, by ensuring that their content is not embedded
        # into other sites.
        self.set_header("X-Frame-Options", "SAMEORIGIN")

    def set_header_content_security_policy(self) -> None:
        # The HTTP Content-Security-Policy (CSP) frame-ancestors directive
        # specifies valid parents that may embed a page using <frame>,
        # <iframe>, <object>, <embed>, or <applet>.
        # Requested upstream:
        # https://lists.clusterlabs.org/pipermail/users/2020-May/027199.html
        # For now, I'm just setting this to the same value as already present
        # X-Frame-Options header to keep them consistent.

        # rhbz#2097778
        # The HTTP Content-Security-Policy (CSP) default-src directive serves
        # as a fallback for the other CSP fetch directives. For each of the
        # fetch directives that are absent, the user agent looks for the
        # default-src directive and uses this value for it.
        # 'self' refers to the origin from which the protected document is
        # being served, including the same URL scheme and port number.
        self.set_header(
            "Content-Security-Policy",
            "frame-ancestors 'self'; default-src 'self'",
        )

    def set_header_xss_protection(self) -> None:
        # The HTTP X-XSS-Protection response header is a feature of Internet
        # Explorer, Chrome and Safari that stops pages from loading when they
        # detect reflected cross-site scripting (XSS) attacks. Although these
        # protections are largely unnecessary in modern browsers when sites
        # implement a strong Content-Security-Policy that disables the use of
        # inline JavaScript ('unsafe-inline'), they can still provide
        # protections for users of older web browsers that don't yet support
        # CSP.
        self.set_header("X-Xss-Protection", "1; mode=block")

    def set_header_cache_control(self) -> None:
        # rhbz#2097383
        # The point is to prevent stealing sensitive data (such as fence
        # devices passwords) from browser caches.

        # no-store - Any caches of any kind should not store this response.
        # no-cache - Response can be stored in caches, but the response must be
        #   validated with the origin server before each reuse. This was
        #   requested probably as a fallback for caches which don't support
        #   no-store.
        self.set_header("Cache-Control", "no-store, no-cache")
        self.set_header("Pragma", "no-cache")

    def clear_header_cache_control(self) -> None:
        # Revert headers to default to allow caching, useful e.g. for static
        # content.
        self.clear_header("Cache-Control")
        self.clear_header("Pragma")

    def set_header_referrer(self) -> None:
        # rhbz#2097391
        # Do not expose cluster configuration bits to other websites (URL may
        # contain name of nodes/resources/etc.). This is mostly future-proof
        # hardening as there are currently little to no links to external
        # sites.
        self.set_header("Referrer-Policy", "no-referrer")

    def set_default_headers(self) -> None:
        """
        Modifies automatic tornado headers for all responses (i.e. including
        errors).

        Method `initialize` is the place for setting headers only for success
        responses.
        """
        self.clear_header_server()
        self.set_header_strict_transport_security()
        self.set_header_nosniff_content_type()
        self.set_header_frame_options()
        self.set_header_content_security_policy()
        self.set_header_xss_protection()
        self.set_header_cache_control()
        self.set_header_referrer()


class BaseHandler(EnhanceHeadersMixin, RequestHandler):
    """
    BaseHandler modifies HTTP headers
    """

    def data_received(self, chunk: bytes) -> None:
        # abstract method `data_received` does need to be overridden. This
        # method should be implemented to handle streamed request data.
        # BUT we currently do not plan to use it SO:
        pass


class Http404Handler(BaseHandler):
    def prepare(self) -> None:
        raise HTTPError(404)


class LegacyApiBaseHandler(BaseHandler):
    def unauthorized(self) -> Finish:
        self.set_status(401)
        self.write('{"notauthorized":"true"}')
        return Finish()


class LegacyApiHandler(LegacyApiBaseHandler):
    async def _handle_request(self) -> None:
        raise NotImplementedError()

    async def get(self, *args, **kwargs):
        del args, kwargs
        await self._handle_request()

    async def post(self, *args, **kwargs):
        del args, kwargs
        await self._handle_request()


class RedirectHandler(EnhanceHeadersMixin, TornadoRedirectHandler):
    # abstract method `data_received` is not used in redirect:
    # pylint: disable=abstract-method
    """
    RedirectHandler with modified HTTP headers.
    """
