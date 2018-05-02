import socket
import ssl
from collections import namedtuple
from functools import lru_cache
from os.path import (
    dirname,
    realpath,
    abspath,
    exists as path_exists,
    join as join_path,
)

from pcs import settings
from pcs.lib.validate import is_port_number

# Relative location instead of system location is used for development purposes.
PCSD_LOCAL_DIR = realpath(dirname(abspath(__file__))+ "/../../pcsd")

PCSD_CMDLINE_ENTRY_RB_SCRIPT = "sinatra_cmdline_wrapper.rb"
PCSD_STATIC_FILES_DIR_NAME = "public"

PCSD_PORT = "PCSD_PORT"
PCSD_SSL_CIPHERS = "PCSD_SSL_CIPHERS"
PCSD_SSL_OPTIONS = "PCSD_SSL_OPTIONS"
PCSD_BIND_ADDR = "PCSD_BIND_ADDR"
NOTIFY_SOCKET = "NOTIFY_SOCKET"
PCSD_DEBUG = "PCSD_DEBUG"
DISABLE_GUI = "DISABLE_GUI"
PCSD_SESSION_LIFETIME = "PCSD_SESSION_LIFETIME"
GEM_HOME = "GEM_HOME"
PCSD_DEV = "PCSD_DEV"
PCSD_CMDLINE_ENTRY = "PCSD_CMDLINE_ENTRY"
PCSD_STATIC_FILES_DIR = "PCSD_STATIC_FILES_DIR"
HTTPS_PROXY = "HTTPS_PROXY"
NO_PROXY = "NO_PROXY"

Env = namedtuple("Env", [
    PCSD_PORT,
    PCSD_SSL_CIPHERS,
    PCSD_SSL_OPTIONS,
    PCSD_BIND_ADDR,
    NOTIFY_SOCKET,
    PCSD_DEBUG,
    DISABLE_GUI,
    PCSD_SESSION_LIFETIME,
    GEM_HOME,
    PCSD_CMDLINE_ENTRY,
    PCSD_STATIC_FILES_DIR,
    HTTPS_PROXY,
    NO_PROXY,
    "has_errors",
])

def prepare_env(environ, logger=None):
    loader = EnvLoader(environ)
    env = Env(
        loader.port(),
        loader.ssl_ciphers(),
        loader.ssl_options(),
        loader.bind_addresses(),
        loader.notify_socket(),
        loader.pcsd_debug(),
        loader.disable_gui(),
        loader.session_lifetime(),
        loader.gem_home(),
        loader.pcsd_cmdline_entry(),
        loader.pcsd_static_files_dir(),
        loader.https_proxy(),
        loader.no_proxy(),
        loader.has_errors(),
    )
    if logger:
        for error in loader.errors:
            logger.error(error)
        for warning in loader.warnings:
            logger.warning(warning)
    return env

def str_to_ssl_options(ssl_options_string, reports):
    ssl_options = 0
    # We are tolerant to trailing whitespaces and trailing comas.
    raw_ssl_options = ssl_options_string.strip(" ,")
    if not raw_ssl_options: #raw_ssl_options.split(",") == [""]
        return ssl_options
    for raw_option in raw_ssl_options.split(","):
        option = raw_option.strip()
        if option.startswith("OP_") and hasattr(ssl, option):
            ssl_options |= getattr(ssl, option)
        else:
            reports.append(f"Unknown SSL option '{option}'")
    return ssl_options

class EnvLoader:
    def __init__(self, environ):
        self.environ = environ
        self.errors = []
        self.warnings = []

    def has_errors(self):
        return len(self.errors) > 0

    @lru_cache()
    def port(self):
        port = self.environ.get(PCSD_PORT, settings.pcsd_default_port)
        if not is_port_number(port):
            self.errors.append(f"Invalid port number '{port}'")
        return port

    def ssl_ciphers(self):
        ssl_ciphers = self.environ.get(
            PCSD_SSL_CIPHERS,
            settings.default_ssl_ciphers
        )
        try: #validate ciphers
            ssl.SSLContext().set_ciphers(ssl_ciphers)
        except ssl.SSLError as e:
            self.errors.append(f"Invalid ciphers: '{e}'")
        return ssl_ciphers

    def ssl_options(self):
        if PCSD_SSL_OPTIONS in self.environ:
            # User knows about underlying system. If there is a wrong option it
            # may be a typo - let them to correct it. They are able to correct
            # it in pcsd.conf.
            return str_to_ssl_options(
                self.environ.get(PCSD_SSL_OPTIONS),
                self.errors
            )
        # Vanilla pcsd should run even on an "exotic" system. If there is
        # a wrong option it is not probably a typo... User should not be
        # forced to modify source code (settings.py).
        return str_to_ssl_options(settings.default_ssl_options, self.warnings)


    def bind_addresses(self):
        if PCSD_BIND_ADDR not in self.environ:
            return {None}

        raw_bind_addresses = self.environ[PCSD_BIND_ADDR]
        if not raw_bind_addresses.strip():
            return {""}

        bind_addresses = set([a.strip() for a in raw_bind_addresses.split(",")])
        for address in bind_addresses:
            try:
                socket.getaddrinfo(address, self.port())
            except socket.gaierror as e:
                self.errors.append(f"Invalid bind address '{address}': '{e}'")
        return bind_addresses

    def notify_socket(self):
        return self.environ.get(NOTIFY_SOCKET, None)

    def disable_gui(self):
        return self.__has_true_in_environ(DISABLE_GUI)

    def session_lifetime(self):
        return self.environ.get(
            PCSD_SESSION_LIFETIME,
            settings.gui_session_lifetime_seconds
        )

    def pcsd_debug(self):
        if PCSD_DEBUG in self.environ:
            return self.environ[PCSD_DEBUG].lower() == "true"
        return self.__has_true_in_environ(PCSD_DEV)

    def gem_home(self):
        return self.__in_pcsd_path(
            settings.pcsd_gem_path,
            "Ruby gem location"
        )

    def pcsd_cmdline_entry(self):
        return self.__in_pcsd_path(
            PCSD_CMDLINE_ENTRY_RB_SCRIPT,
            "Ruby handlers entrypoint"
        )

    def pcsd_static_files_dir(self):
        return self.__in_pcsd_path(
            PCSD_STATIC_FILES_DIR_NAME,
            "Directory with web UI assets",
            existence_required=not self.disable_gui()
        )

    def https_proxy(self):
        return self.environ.get(HTTPS_PROXY, None)

    def no_proxy(self):
        return self.environ.get(NO_PROXY, None)

    def __in_pcsd_path(self, path, description="", existence_required=True):
        pcsd_dir = (
            settings.pcsd_exec_location
            if not self.__has_true_in_environ(PCSD_DEV) else
            PCSD_LOCAL_DIR
        )

        in_pcsd_path =join_path(pcsd_dir, path)
        if existence_required and not path_exists(in_pcsd_path):
            self.errors.append(f"{description} '{in_pcsd_path}' does not exist")
        return in_pcsd_path


    def __has_true_in_environ(self, environ_key):
        return self.environ.get(environ_key, "").lower() == "true"
