from collections import namedtuple
import socket

from pcs import settings
from pcs.daemon import ssl
from pcs.lib.validate import is_port_number

PCSD_PORT = "PCSD_PORT"
PCSD_SSL_CIPHERS = "PCSD_SSL_CIPHERS"
PCSD_SSL_OPTIONS = "PCSD_SSL_OPTIONS"
PCSD_BIND_ADDR = "PCSD_BIND_ADDR"
NOTIFY_SOCKET = "NOTIFY_SOCKET"
DEBUG = "DEBUG"
DISABLE_GUI = "DISABLE_GUI"

Env = namedtuple("Env", [
    PCSD_PORT,
    PCSD_SSL_CIPHERS,
    PCSD_SSL_OPTIONS,
    PCSD_BIND_ADDR,
    NOTIFY_SOCKET,
    DEBUG,
    DISABLE_GUI,
])

class EnvPrepare:
    def __init__(self, os_environ):
        self.__os_environ = os_environ
        self.__errors = []
        self.__env = None

    @property
    def errors(self):
        self.__prepare()
        return tuple(self.__errors)

    @property
    def env(self):
        self.__prepare()
        return self.__env

    def __prepare(self):
        if self.__env is None:
            port = self.__port()
            self.__env = Env(
                port,
                self.__ssl_ciphers(),
                self.__ssl_options(),
                self.__bind_addresses(port),
                self.__os_environ.get(NOTIFY_SOCKET, None),
                self.__os_environ.get(DEBUG, "").lower() == "true",
                self.__os_environ.get(DISABLE_GUI, "").lower() == "true",
            )

    def __err(self, message):
        self.__errors.append(message)

    def __port(self):
        port = self.__os_environ.get(PCSD_PORT, settings.pcsd_default_port)
        if not is_port_number(port):
            self.__err(f"Invalid port number '{port}'")
        return port

    def __ssl_ciphers(self):
        ssl_ciphers = self.__os_environ.get(
            PCSD_SSL_CIPHERS,
            settings.default_ssl_ciphers
        )
        if not ssl.are_valid_ciphers(ssl_ciphers):
            self.__err(f"Invalid ciphers")
        return ssl_ciphers

    def __ssl_options(self):
        ssl_context = ssl.default_context()
        if PCSD_SSL_OPTIONS in self.__os_environ:
            # Type of ssl_context.options stays <enum 'Options'> by this way.
            ssl_context.options = 0
            raw_ssl_options = self.__os_environ.get(PCSD_SSL_OPTIONS).strip()
        else:
            raw_ssl_options = settings.default_ssl_extra_options

        if not raw_ssl_options:
            return ssl_context.options

        for raw_option in raw_ssl_options.split(","):
            try:
                ssl_context.options |= ssl.string_to_option(raw_option)
            except NameError:
                self.__err(f"Unknown SSL option '{raw_option.strip()}'")

        return ssl_context.options

    def __bind_addresses(self, port):
        if PCSD_BIND_ADDR not in self.__os_environ:
            return [None]

        raw_bind_addresses = self.__os_environ.get(PCSD_BIND_ADDR, None)
        if not raw_bind_addresses.strip():
            return [""]

        bind_addresses = [a.strip() for a in raw_bind_addresses.split(",")]
        for address in bind_addresses:
            try:
                socket.getaddrinfo(address, port)
            except socket.gaierror as e:
                self.__err(f"Invalid bind address '{address}': '{e}'")
        return bind_addresses
