import shutil

from tornado.httpserver import HTTPServer
from tornado.netutil import (
    bind_sockets,
    bind_unix_socket,
)

from pcs.daemon import log
from pcs.daemon.ssl import PcsdSSL
from pcs.lib.auth.const import ADMIN_GROUP


class HttpsServerManageException(Exception):
    pass


class HttpsServerManage:
    # pylint: disable=too-many-instance-attributes
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

    def __init__(
        self,
        make_app,
        port,
        bind_addresses,
        ssl: PcsdSSL,
        unix_socket_path,
    ):
        self.__make_app = make_app
        self.__port = port
        self.__bind_addresses = bind_addresses
        self.__tcp_server = None
        self.__ssl = ssl
        self.__unix_socket_path = unix_socket_path
        self.__unix_socket_server = None
        self.__server_is_running = False

    @property
    def server_is_running(self):
        return self.__server_is_running

    def stop(self):
        self.__tcp_server.stop()
        self.__unix_socket_server.stop()
        self.__server_is_running = False

    def start(self):
        self.__ssl.guarantee_valid_certs()

        log.pcsd.info("Starting server...")

        app = self.__make_app(self)
        self.__tcp_server = HTTPServer(
            app,
            ssl_options=self.__ssl.create_context(),
        )
        self.__unix_socket_server = HTTPServer(app)

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

        self.__tcp_server.add_sockets(sockets)
        self.__unix_socket_server.add_socket(
            bind_unix_socket(self.__unix_socket_path, mode=0o660)
        )
        shutil.chown(self.__unix_socket_path, 0, ADMIN_GROUP)

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
