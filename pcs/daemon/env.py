import socket
import ssl
from collections import namedtuple
from os.path import dirname, realpath, abspath

from pcs import settings
from pcs.lib.validate import is_port_number

PCSD_PORT = "PCSD_PORT"
PCSD_SSL_CIPHERS = "PCSD_SSL_CIPHERS"
PCSD_SSL_OPTIONS = "PCSD_SSL_OPTIONS"
PCSD_BIND_ADDR = "PCSD_BIND_ADDR"
NOTIFY_SOCKET = "NOTIFY_SOCKET"
DEBUG = "DEBUG"
DISABLE_GUI = "DISABLE_GUI"
PCSD_SESSION_LIFETIME = "PCSD_SESSION_LIFETIME"
GEM_HOME = "GEM_HOME"
PCSD_DEV = "PCSD_DEV"

Env = namedtuple("Env", [
    PCSD_PORT,
    PCSD_SSL_CIPHERS,
    PCSD_SSL_OPTIONS,
    PCSD_BIND_ADDR,
    NOTIFY_SOCKET,
    DEBUG,
    DISABLE_GUI,
    PCSD_SESSION_LIFETIME,
    GEM_HOME,
])

class EnvPrepare:
    def __init__(self, os_environ):
        self.__os_environ = os_environ
        self.__errors = []
        self.__warnings = []
        self.__env = self.__prepare()
        self.__logged = False

    def log_only_once(self, logger):
        if self.__logged:
            return
        for error in self.__errors:
            logger.error(error)
        for warning in self.__warnings:
            logger.warning(warning)
        self.__logged = True

    @property
    def has_errors(self):
        return len(self.__errors) > 0

    @property
    def env(self):
        return self.__env

    def __prepare(self):
        port = self.__port()
        pcsd_dir = self.__pcsd_dir()
        return Env(
            port,
            self.__ssl_ciphers(),
            self.__ssl_options(),
            self.__bind_addresses(port),
            self.__os_environ.get(NOTIFY_SOCKET, None),
            self.__debug(),
            self.__has_true_in_environ(DISABLE_GUI),
            self.__os_environ.get(
                PCSD_SESSION_LIFETIME,
                settings.gui_session_lifetime_seconds
            ),
            self.__gem_home(pcsd_dir),
        )

    def __has_true_in_environ(self, environ_key):
        return self.__os_environ.get(environ_key, "").lower() == "true"

    def __port(self):
        port = self.__os_environ.get(PCSD_PORT, settings.pcsd_default_port)
        if not is_port_number(port):
            self.__errors.append(f"Invalid port number '{port}'")
        return port

    def __pcsd_dir(self):
        return realpath(dirname(abspath(__file__))+ "/../../pcsd")

    def __ssl_ciphers(self):
        ssl_ciphers = self.__os_environ.get(
            PCSD_SSL_CIPHERS,
            settings.default_ssl_ciphers
        )
        ssl_context = ssl.SSLContext()
        try: #validate ciphers
            ssl_context.set_ciphers(ssl_ciphers)
        except ssl.SSLError as e:
            self.__errors.append(f"Invalid ciphers: '{e}'")
        return ssl_ciphers

    def __ssl_options(self):
        if PCSD_SSL_OPTIONS in self.__os_environ:
            # User knows about underlying system. If there is a wrong option it
            # may be a typo - let them to correct it. They are able to correct
            # it in pcsd.conf.
            reports  = self.__errors
            raw_ssl_options = self.__os_environ.get(PCSD_SSL_OPTIONS)
        else:
            # Vanilla pcsd should run even on an "exotic" system. If there is
            # a wrong option it is not probably a typo... User should not be
            # forced to modify source code (settings.py).
            reports  = self.__warnings
            raw_ssl_options = settings.default_ssl_options

        ssl_options = 0
        # We are tolerant to trailing whitespaces and trailing comas.
        raw_ssl_options = raw_ssl_options.strip(" ,")
        if not raw_ssl_options: #raw_ssl_options.split(",") == [""]
            return ssl_options

        for raw_option in raw_ssl_options.split(","):
            option = raw_option.strip()
            if option.startswith("OP_") and hasattr(ssl, option):
                ssl_options |= getattr(ssl, option)
            else:
                reports.append(f"Unknown SSL option '{option}'")

        return ssl_options

    def __bind_addresses(self, port):
        if PCSD_BIND_ADDR not in self.__os_environ:
            return [None]

        raw_bind_addresses = self.__os_environ.get(PCSD_BIND_ADDR, None)
        if not raw_bind_addresses.strip():
            return [""]

        bind_addresses = set([a.strip() for a in raw_bind_addresses.split(",")])
        for address in bind_addresses:
            try:
                socket.getaddrinfo(address, port)
            except socket.gaierror as e:
                self.__errors.append(f"Invalid bind address '{address}': '{e}'")
        return bind_addresses

    def __debug(self):
        if DEBUG in self.__os_environ:
            return self.__os_environ[DEBUG].lower() == "true"
        return self.__has_true_in_environ(PCSD_DEV)

    def __gem_home(self, pcsd_dir):
        return  "{}/{}".format(
            pcsd_dir
                if self.__has_true_in_environ(PCSD_DEV) else
                realpath(settings.pcsd_exec_location)
            ,
            settings.pcsd_gem_path
        )
