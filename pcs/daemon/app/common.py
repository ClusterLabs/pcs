from tornado.web import RedirectHandler as TornadoRedirectHandler
from tornado.web import RequestHandler


class EnhanceHeadersMixin:
    """
    EnhanceHeadersMixin allows to add security headers to GUI urls.
    """

    def set_header_strict_transport_security(self):
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

    def clear_header_server(self):
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
        self.set_header("Content-Security-Policy", "frame-ancestors 'self'")

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


class BaseHandler(EnhanceHeadersMixin, RequestHandler):
    """
    BaseHandler modifies HTTP headers.
    """

    def data_received(self, chunk):
        # abstract method `data_received` does need to be overridden. This
        # method should be implemented to handle streamed request data.
        # BUT we currently do not plan to use it SO:
        # pylint: disable=abstract-method
        pass


# abstract method `data_received` is not used in redirect:
# pylint: disable=abstract-method
class RedirectHandler(EnhanceHeadersMixin, TornadoRedirectHandler):
    """
    RedirectHandler with modified HTTP headers.
    """
