import os.path
import ssl
from collections import namedtuple
from functools import lru_cache

from pcs import settings
from pcs.common.validate import (
    is_integer,
    is_port_number,
)

try:
    from pcs.daemon.app import webui
except ImportError:
    webui = None

# Relative location instead of system location is used for development purposes.
LOCAL_PUBLIC_DIR = os.path.realpath(
    os.path.dirname(os.path.abspath(__file__)) + "/../../pcsd/public"
)
LOCAL_WEBUI_DIR = os.path.join(LOCAL_PUBLIC_DIR, "ui")
WEBUI_FALLBACK_FILE = "ui_instructions.html"

PCSD_PORT = "PCSD_PORT"
PCSD_SSL_CIPHERS = "PCSD_SSL_CIPHERS"
PCSD_SSL_OPTIONS = "PCSD_SSL_OPTIONS"
PCSD_BIND_ADDR = "PCSD_BIND_ADDR"
NOTIFY_SOCKET = "NOTIFY_SOCKET"
PCSD_DEBUG = "PCSD_DEBUG"
PCSD_SESSION_LIFETIME = "PCSD_SESSION_LIFETIME"
PCSD_DEV = "PCSD_DEV"
WEBUI_DIR = "WEBUI_DIR"
WEBUI_FALLBACK = "WEBUI_FALLBACK"
PCSD_WORKER_COUNT = "PCSD_WORKER_COUNT"
PCSD_WORKER_RESET_LIMIT = "PCSD_WORKER_RESET_LIMIT"
PCSD_MAX_WORKER_COUNT = "PCSD_MAX_WORKER_COUNT"
PCSD_DEADLOCK_THRESHOLD_TIMEOUT = "PCSD_DEADLOCK_THRESHOLD_TIMEOUT"
PCSD_CHECK_INTERVAL_MS = "PCSD_CHECK_INTERVAL_MS"
PCSD_TASK_ABANDONED_TIMEOUT = "PCSD_TASK_ABANDONED_TIMEOUT"
PCSD_TASK_UNRESPONSIVE_TIMEOUT = "PCSD_TASK_UNRESPONSIVE_TIMEOUT"
PCSD_TASK_DELETION_TIMEOUT = "PCSD_TASK_DELETION_TIMEOUT"

Env = namedtuple(
    "Env",
    [
        PCSD_PORT,
        PCSD_SSL_CIPHERS,
        PCSD_SSL_OPTIONS,
        PCSD_BIND_ADDR,
        NOTIFY_SOCKET,
        PCSD_DEBUG,
        PCSD_SESSION_LIFETIME,
        WEBUI_DIR,
        WEBUI_FALLBACK,
        PCSD_DEV,
        PCSD_WORKER_COUNT,
        PCSD_WORKER_RESET_LIMIT,
        PCSD_MAX_WORKER_COUNT,
        PCSD_DEADLOCK_THRESHOLD_TIMEOUT,
        PCSD_CHECK_INTERVAL_MS,
        PCSD_TASK_ABANDONED_TIMEOUT,
        PCSD_TASK_UNRESPONSIVE_TIMEOUT,
        PCSD_TASK_DELETION_TIMEOUT,
        "has_errors",
    ],
)


def prepare_env(environ, logger=None):
    loader = EnvLoader(environ)
    loader.check_webui()
    env = Env(
        loader.port(),
        loader.ssl_ciphers(),
        loader.ssl_options(),
        loader.bind_addresses(),
        loader.notify_socket(),
        loader.pcsd_debug(),
        loader.session_lifetime(),
        loader.webui_dir(),
        loader.webui_fallback(),
        loader.pcsd_dev(),
        loader.pcsd_worker_count(),
        loader.pcsd_worker_reset_limit(),
        loader.pcsd_max_worker_count(),
        loader.pcsd_deadlock_threshold_timeout(),
        loader.pcsd_check_interval_ms(),
        loader.pcsd_task_abandoned_timeout(),
        loader.pcsd_task_unresponsive_timeout(),
        loader.pcsd_task_deletion_timeout(),
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
    if not raw_ssl_options:  # raw_ssl_options.split(",") == [""]
        return ssl_options
    for raw_option in raw_ssl_options.split(","):
        option = raw_option.strip()
        if option == "OP_NO_RENEGOTIATION" and not hasattr(ssl, option):
            # OP_NO_RENEGOTIATION is for a prevention of DoS attacks.
            # See https://bugzilla.redhat.com/show_bug.cgi?id=1566430
            #
            # OP_NO_RENEGOTIATION is new in python 3.7. `pcs` supports python
            # 3.6+ but even with python 3.6 it is possible to use this option if
            # the underlying openssl has version 1.1.0h+.
            ssl_options |= 1073741824
        elif option.startswith("OP_") and hasattr(ssl, option):
            ssl_options |= getattr(ssl, option)
        else:
            reports.append(f"Ignoring unknown SSL option '{option}'")
    return ssl_options


class EnvLoader:
    # pylint: disable=too-many-public-methods
    def __init__(self, environ):
        self.environ = environ
        self.errors = []
        self.warnings = []

    def has_errors(self):
        return len(self.errors) > 0

    @lru_cache(maxsize=5)
    def port(self):
        port = self.environ.get(PCSD_PORT, settings.pcsd_default_port)
        if not is_port_number(port):
            self.errors.append(f"Invalid port number '{port}', use 1..65535")
        return port

    def ssl_ciphers(self):
        ssl_ciphers = self.environ.get(
            PCSD_SSL_CIPHERS, settings.default_ssl_ciphers
        )
        try:  # validate ciphers
            ssl.SSLContext().set_ciphers(ssl_ciphers)
        except ssl.SSLError as e:
            self.errors.append(f"Invalid ciphers: '{e}'")
        return ssl_ciphers

    def ssl_options(self):
        if PCSD_SSL_OPTIONS in self.environ:
            # User knows about underlying system. If there is a wrong option it
            # may be a typo - let them correct it. They are able to correct it
            # in pcsd.conf.
            return str_to_ssl_options(
                self.environ[PCSD_SSL_OPTIONS], self.errors
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

        return {a.strip() for a in raw_bind_addresses.split(",")}

    def notify_socket(self):
        return self.environ.get(NOTIFY_SOCKET, None)

    def session_lifetime(self):
        session_lifetime = self.environ.get(
            PCSD_SESSION_LIFETIME, settings.gui_session_lifetime_seconds
        )
        try:
            return int(session_lifetime)
        except ValueError:
            self.errors.append(
                f"Invalid PCSD_SESSION_LIFETIME value '{session_lifetime}'"
                " (it must be an integer)"
            )
            return session_lifetime

    def pcsd_debug(self):
        return self.__has_true_in_environ(PCSD_DEBUG)

    def check_webui(self):
        if webui and not (
            os.path.exists(self.webui_dir())
            or os.path.exists(self.webui_fallback())
        ):
            self.errors.append(
                f"Webui assets directory '{self.webui_dir()}'"
                + f" or falback html '{self.webui_fallback()}' does not exist"
            )

    @lru_cache(maxsize=5)
    def webui_dir(self):
        return LOCAL_WEBUI_DIR if self.pcsd_dev() else settings.pcsd_webui_dir

    @lru_cache(maxsize=5)
    def webui_fallback(self):
        return os.path.join(
            LOCAL_PUBLIC_DIR if self.pcsd_dev() else settings.pcsd_public_dir,
            WEBUI_FALLBACK_FILE,
        )

    @lru_cache(maxsize=5)
    def pcsd_dev(self):
        return self.__has_true_in_environ(PCSD_DEV)

    def _get_positive_int(self, key: str, default: int) -> int:
        value = self.environ.get(key, default)
        if not is_integer(value, at_least=1):
            self.errors.append(
                f"Value '{value}' for '{key}' is not a positive integer"
            )
            return default
        return int(value)

    def _get_non_negative_int(self, key: str, default: int) -> int:
        value = self.environ.get(key, default)
        if not is_integer(value, at_least=0):
            self.errors.append(
                f"Value '{value}' for '{key}' is not a non-negative integer"
            )
            return default
        return int(value)

    @lru_cache(maxsize=1)
    def pcsd_worker_count(self) -> int:
        return self._get_positive_int(
            PCSD_WORKER_COUNT, settings.pcsd_worker_count
        )

    @lru_cache(maxsize=1)
    def pcsd_worker_reset_limit(self) -> int:
        return self._get_positive_int(
            PCSD_WORKER_RESET_LIMIT, settings.pcsd_worker_reset_limit
        )

    @lru_cache(maxsize=1)
    def pcsd_max_worker_count(self) -> int:
        return self._get_positive_int(
            PCSD_MAX_WORKER_COUNT,
            self.pcsd_worker_count() + settings.pcsd_temporary_workers,
        )

    @lru_cache(maxsize=1)
    def pcsd_deadlock_threshold_timeout(self) -> int:
        return self._get_non_negative_int(
            PCSD_DEADLOCK_THRESHOLD_TIMEOUT,
            settings.pcsd_deadlock_threshold_timeout,
        )

    @lru_cache(maxsize=1)
    def pcsd_check_interval_ms(self) -> int:
        return self._get_positive_int(
            PCSD_CHECK_INTERVAL_MS, settings.async_api_scheduler_interval_ms
        )

    @lru_cache(maxsize=1)
    def pcsd_task_abandoned_timeout(self) -> int:
        return self._get_positive_int(
            PCSD_TASK_ABANDONED_TIMEOUT, settings.task_abandoned_timeout_seconds
        )

    @lru_cache(maxsize=1)
    def pcsd_task_unresponsive_timeout(self) -> int:
        return self._get_positive_int(
            PCSD_TASK_UNRESPONSIVE_TIMEOUT,
            settings.task_unresponsive_timeout_seconds,
        )

    @lru_cache(maxsize=1)
    def pcsd_task_deletion_timeout(self) -> int:
        return self._get_non_negative_int(
            PCSD_TASK_DELETION_TIMEOUT, settings.task_deletion_timeout_seconds
        )

    def __has_true_in_environ(self, environ_key):
        return self.environ.get(environ_key, "").lower() == "true"
