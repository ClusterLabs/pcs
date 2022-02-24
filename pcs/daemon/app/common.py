from tornado.web import RedirectHandler as TornadoRedirectHandler
from tornado.web import RequestHandler


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

        # The HTTP Content-Security-Policy (CSP) frame-ancestors directive
        # specifies valid parents that may embed a page using <frame>,
        # <iframe>, <object>, <embed>, or <applet>.

        # Requested upstream:
        # https://lists.clusterlabs.org/pipermail/users/2020-May/027199.html

        # For now, I'm just setting this to the same value as already present
        # X-Frame-Options header to keep them consistent.
        self.set_header("Content-Security-Policy", "frame-ancestors 'self'")

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
        # pylint: disable=abstract-method
        pass


class RedirectHandler(EnhanceHeadersMixin, TornadoRedirectHandler):
    """
    RedirectHandler with Strict-Transport-Security headers.
    """

    # abstract method `data_received` is not used in redirect:
    # pylint: disable=abstract-method
    def initialize(self, url, permanent=True):
        super().initialize(url, permanent)
        self.set_strict_transport_security()
