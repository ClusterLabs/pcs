import os.path

from tornado.web import(
    StaticFileHandler,
)

from pcs.daemon.sinatra import(
    Login,
    LoginStatus,
    Logout,
    SinatraGuiProtected,
    SinatraAjaxProtected,
)

#pylint: disable=abstract-method
PUBLIC_DIR = os.path.realpath(
    os.path.dirname(os.path.abspath(__file__))+ "/../../pcsd/public"
)

class StaticFile(StaticFileHandler):
    def initialize(self, path, default_filename=None):
        super().initialize(path, default_filename)
        # In ruby server the header X-Content-Type-Options was sent and we
        # keep it here to keep compatibility for simplifying testing. There is
        # no another special reason for it. So, maybe, it can be removed in
        # future.
        #
        # The X-Content-Type-Options response HTTP header is a marker used by
        # the server to indicate that the MIME types advertised in the
        # Content-Type headers should not be changed and be followed. This
        # allows to opt-out of MIME type sniffing, or, in other words, it is a
        # way to say that the webmasters knew what they were doing.
        self.set_header("X-Content-Type-Options", "nosniff")

def static_route(url_prefix, public_subdir):
    return (
        rf"{url_prefix}(.*)",
        StaticFile,
        dict(
            path=os.path.join(PUBLIC_DIR, public_subdir)
        )
    )

STATIC_ROUTES = [
    static_route("/css/", "css"),
    static_route("/js/", "js"),
    static_route("/images/", "images"),
]

ROUTES = [
    (r"/login", Login),
    (r"/login-status", LoginStatus),
    (r"/logout", Logout),

    #The protection by session was moved from ruby code to python code
    #(tornado).
    (r"/($|manage$|permissions$|managec/.+/main)", SinatraGuiProtected),

    (r"/.*", SinatraAjaxProtected),
]
