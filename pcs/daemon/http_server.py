from tornado.httpserver import HTTPServer
from tornado.netutil import bind_sockets

from pcs.daemon.ssl import PcsdSSL
from pcs.daemon import log


class HttpsServerManage:
    #TODO
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

        self.__start()

    def regenerate_certificate(self):
        self.__ssl.regenerate_cert_key(self.__server_name)
        self.stop()
        self.__start_new_server()

    def stop(self):
        self.__server.stop()

    def __start_new_server(self):
        log.pcsd.info("Starting server...")
        self.__main_start_new_server()
        log.pcsd.info(
            f"Listening on "
            f"'{', '.join([a or '' for a in self.__bind_addresses])}'"
            f" port '{self.__port}'",
        )

    def __main_start_new_server(self):
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

    def __start(self):
        error_list = self.__ssl.check_cert_key()
        if error_list:
            for error in error_list:
                log.pcsd.error(error)
            self.__ssl.regenerate_cert_key(self.__server_name)
        self.__start_new_server()
