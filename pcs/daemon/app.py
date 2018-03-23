from tornado.web import Application, RequestHandler
from pcs.daemon import gui
from pcs.daemon.sinatra import Sinatra
from pcs.daemon.http_server import HttpsServerManage

class RegenerateCertHandler(RequestHandler):
    #pylint: disable=abstract-method
    def initialize(self, https_server_manage: HttpsServerManage):
        #pylint: disable=arguments-differ
        self.https_server_manage = https_server_manage

    def get(self, *args, **kwargs):
        self.https_server_manage.regenerate_certificate()
        self.write("CERTIFICATE_RELOADED")

def make_app(https_server_manage: HttpsServerManage):
    return Application(
        gui.STATIC_ROUTES
            +
            [
                # Urls protected by tokens. It is stil done by ruby.
                (r"/run_pcs", Sinatra),
                (r"/remote/.*", Sinatra),
                (r"/remote/auth", Sinatra),

                (
                    r"/daemon-maintenance/reload-cert",
                    RegenerateCertHandler,
                    {"https_server_manage": https_server_manage},
                ),
            ]
            +
            gui.ROUTES
        ,
        debug=True,
    )
