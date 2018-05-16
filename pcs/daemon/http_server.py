from tornado.httpserver import HTTPServer
from tornado.netutil import bind_sockets

from pcs.daemon.ssl import PcsdSSL
from pcs.daemon import log

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
    # for necessary steps (it should make the current HTTPServer stop listening
    # and start a new one with updated certificates).
    #
    # This is currently not implemented since it could require changes in the
    # client.

    #TODO?
    #pylint: disable=too-many-instance-attributes, too-many-arguments
    def __init__(
        self,
        make_app,
        server_name, port, bind_addresses,
        ssl_options, ssl_ciphers, cert_location, key_location,
    ):
        self.__make_app = make_app
        self.__server_name = server_name
        self.__port = port
        self.__bind_addresses = bind_addresses
        self.__ssl_options = ssl_options
        self.__ssl_ciphers = ssl_ciphers

        self.__server = None
        self.__ssl = PcsdSSL(cert_location, key_location)
        self.__server_is_running = False

    @property
    def server_is_running(self):
        return self.__server_is_running

    def stop(self):
        self.__server.stop()
        self.__server_is_running = False

    def start(self):
        self.__ensure_cert_key()

        log.pcsd.info("Starting server...")

        self.__server = HTTPServer(
            self.__make_app(self),
            ssl_options=self.__ssl.create_context(
                self.__ssl_options,
                self.__ssl_ciphers,
            )
        )

        # It is necessary to bind sockets for every new HTTPServer since
        # HTTPServer.stop calls sock.close() inside.
        sockets = []
        for address in self.__bind_addresses:
            log.pcsd.info(
                "Binding socket for address '%s' and port '%s'",
                address if address is not None else "*",
                self.__port
            )
            sockets.extend(bind_sockets(self.__port, address))

        self.__server.add_sockets(sockets)

        log.pcsd.info(f"Server is listening")
        self.__server_is_running = True

    def reload_certs(self):
        if not self.server_is_running:
            raise HttpsServerManageException(
                "Could not reload certificates, server is not running"
            )
        log.pcsd.info("Stopping server to reload ssl certificates...")
        self.stop()
        self.start()

    def __ensure_cert_key(self):
        error_list = self.__ssl.check_cert_key()

        if not error_list:
            return

        for error in error_list:
            log.pcsd.error(error)
        log.pcsd.error(
            "Invalid SSL certificate and/or key, using temporary ones"
        )

        self.__ssl.regenerate_cert_key(self.__server_name)
