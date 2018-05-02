from tornado.httpserver import HTTPServer
from tornado.netutil import bind_sockets

from pcs.daemon.ssl import PcsdSSL
from pcs.daemon import log


class HttpsServerManage:
    """
    Instance of HttpsServerManage encapsulate the construction of HTTPServer.
    """

    # Main motivation for this object is to be able to change the ssl certificates
    # from http request without restarting the whole pcsd daemon.
    #
    # For this purpose an application, which handles http requests, gets reference
    # to the HttpsServerManage instance. When new certificates arrives via request
    # the application ask the HttpsServerManage instance for necessary steps (
    # it should stop the current HTTPServer listening and start new one with
    # actual certificates).
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

    def stop(self):
        self.__server.stop()

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
        sockets = []
        for address in self.__bind_addresses:
            sockets.extend(bind_sockets(self.__port, address))
        self.__server.add_sockets(sockets)

        log.pcsd.info(
            f"Listening on "
            f"'{', '.join([a or '' for a in self.__bind_addresses])}'"
            f" port '{self.__port}'",
        )

    def __ensure_cert_key(self):
        error_list = self.__ssl.check_cert_key()

        if not error_list:
            return

        for error in error_list:
            log.pcsd.error(error)
        log.pcsd.error("Invalid certificate and/or key, using temporary ones")

        self.__ssl.regenerate_cert_key(self.__server_name)
