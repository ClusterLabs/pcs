from tornado.httpserver import HTTPServer
from tornado.netutil import bind_sockets

from pcs.daemon import log
from pcs.daemon.ssl import PcsdSSL


class HttpsServerManageException(Exception):
    pass


class HttpsServerManage:
    """
    Instance of HttpsServerManage encapsulates the construction of an HTTPServer
    """

    # Main motivation for this object is to be able to change the ssl
    # certificates from an http request without restarting the whole pcsd
    # daemon.
    #
    # For this purpose an application, which handles http requests, gets
    # a reference to the HttpsServerManage instance. When new certificates
    # arrive via a request the application asks the HttpsServerManage instance
    # for necessary steps (it stops listening of the current HTTPServer and
    # starts a new one with updated certificates).

    def __init__(self, make_app, port, bind_addresses, ssl: PcsdSSL):
        self.__make_app = make_app
        self.__port = port
        self.__bind_addresses = bind_addresses

        self.__server = None
        self.__ssl = ssl
        self.__server_is_running = False

    @property
    def server_is_running(self):
        return self.__server_is_running

    def stop(self):
        self.__server.stop()
        self.__server_is_running = False

    def start(self):
        self.__ssl.guarantee_valid_certs()

        log.pcsd.info("Starting server...")

        self.__server = HTTPServer(
            self.__make_app(self), ssl_options=self.__ssl.create_context()
        )

        # It is necessary to bind sockets for every new HTTPServer since
        # HTTPServer.stop calls sock.close() inside.
        sockets = []
        for address in self.__bind_addresses:
            log.pcsd.info(
                "Binding socket for address '%s' and port '%s'",
                address if address is not None else "*",
                self.__port,
            )
            sockets.extend(bind_sockets(self.__port, address))

        self.__server.add_sockets(sockets)

        log.pcsd.info("Server is listening")
        self.__server_is_running = True
        return self

    def reload_certs(self):
        if not self.server_is_running:
            raise HttpsServerManageException(
                "Could not reload certificates, server is not running"
            )
        log.pcsd.info("Stopping server to reload ssl certificates...")
        self.stop()
        self.start()
