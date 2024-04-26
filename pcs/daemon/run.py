import multiprocessing as mp
import os
import signal
import socket
import sys
from pathlib import Path
from typing import (
    Iterable,
    Optional,
)

from tornado.ioloop import (
    IOLoop,
    PeriodicCallback,
)
from tornado.locks import Lock
from tornado.web import Application

from pcs import settings
from pcs.common import capabilities
from pcs.common.types import StringCollection
from pcs.daemon import (
    log,
    ruby_pcsd,
    session,
    ssl,
    systemd,
)
from pcs.daemon.app import (
    api_v0,
    api_v1,
    api_v2,
    auth,
)
from pcs.daemon.app import capabilities as capabilities_app
from pcs.daemon.app import (
    sinatra_remote,
    sinatra_ui,
)

try:
    from pcs.daemon.app import webui
except ImportError:
    webui = None

from pcs.daemon.app.common import (
    Http404Handler,
    RedirectHandler,
)
from pcs.daemon.async_tasks.scheduler import (
    Scheduler,
    SchedulerConfig,
)
from pcs.daemon.async_tasks.task import TaskConfig
from pcs.daemon.env import prepare_env
from pcs.daemon.http_server import HttpsServerManage
from pcs.lib.auth.provider import AuthProvider


class SignalInfo:
    async_scheduler: Optional[Scheduler] = None
    server_manage = None
    ioloop_started = False


def handle_signal(incoming_signal, frame):
    del frame
    log.pcsd.warning("Caught signal: %s, shutting down", incoming_signal)
    if SignalInfo.server_manage:
        SignalInfo.server_manage.stop()
    if SignalInfo.async_scheduler:
        SignalInfo.async_scheduler.terminate_nowait()
    if SignalInfo.ioloop_started:
        IOLoop.current().stop()
    raise SystemExit(0)


def sign_ioloop_started():
    SignalInfo.ioloop_started = True


def config_sync(sync_config_lock: Lock, ruby_pcsd_wrapper: ruby_pcsd.Wrapper):
    async def config_synchronization():
        async with sync_config_lock:
            next_run_time = await ruby_pcsd_wrapper.sync_configs()
        IOLoop.current().call_at(next_run_time, config_synchronization)

    return config_synchronization


def configure_app(
    async_scheduler: Scheduler,
    auth_provider: AuthProvider,
    session_storage: session.Storage,
    ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
    sync_config_lock: Lock,
    public_dir: str,
    pcsd_capabilities: Iterable[capabilities.Capability],
    enable_webui: bool = False,
    debug: bool = False,
):
    # pylint: disable=too-many-arguments
    def make_app(https_server_manage: HttpsServerManage):
        """
        https_server_manage -- allows to control the server (specifically
            reload its SSL certificates). A relevant handler should get this
            object via the method `initialize`.
        """

        routes = api_v2.get_routes(async_scheduler, auth_provider)
        routes.extend(api_v1.get_routes(async_scheduler, auth_provider))
        routes.extend(api_v0.get_routes(async_scheduler, auth_provider))
        routes.extend(auth.get_routes(auth_provider))
        routes.extend(
            capabilities_app.get_routes(auth_provider, pcsd_capabilities)
        )
        routes.extend(
            sinatra_remote.get_routes(
                ruby_pcsd_wrapper,
                sync_config_lock,
                https_server_manage,
                auth_provider,
            )
        )

        if webui and enable_webui:
            routes.extend(
                [(r"/(ui)?", RedirectHandler, dict(url="/ui/"))]
                + webui.get_routes(
                    url_prefix="/ui/",
                    app_dir=os.path.join(public_dir, "ui"),
                    fallback_page_path=os.path.join(
                        public_dir,
                        "ui_instructions.html",
                    ),
                    session_storage=session_storage,
                    auth_provider=auth_provider,
                )
                + sinatra_ui.get_routes(
                    session_storage, auth_provider, ruby_pcsd_wrapper
                )
            )

        return Application(
            routes, debug=debug, default_handler_class=Http404Handler
        )

    return make_app


def _print_version(argv: StringCollection) -> None:
    try:
        print(settings.pcs_version)
        if "--full" in argv:
            print(
                capabilities.capabilities_to_codes_str(
                    capabilities.get_pcsd_capabilities()
                )
            )
    except capabilities.CapabilitiesError as e:
        sys.stderr.write(f"Error: {e.msg}\n")
        raise SystemExit(1) from e


def main(argv=None) -> None:
    # set the way how processes are started
    # https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods
    # avoid deadlock in multiprocessing.pool.Pool on terminate
    # https://github.com/python/cpython/issues/73945
    mp.set_start_method(method="forkserver")

    argv = argv if argv is not None else sys.argv[1:]
    if "--version" in argv:
        _print_version(argv)
        return

    if argv:
        sys.stderr.write(f"Error: option {argv[0]} is not recognized\n")
        raise SystemExit(1)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    Path(settings.pcsd_log_location).touch(mode=0o600, exist_ok=True)
    log.setup(settings.pcsd_log_location)

    env = prepare_env(os.environ, log.pcsd)
    if env.has_errors:
        raise SystemExit(1)

    if env.PCSD_DEBUG:
        log.enable_debug()

    async_scheduler = Scheduler(
        SchedulerConfig(
            worker_count=env.PCSD_WORKER_COUNT,
            max_worker_count=env.PCSD_MAX_WORKER_COUNT,
            worker_reset_limit=env.PCSD_WORKER_RESET_LIMIT,
            deadlock_threshold_timeout=env.PCSD_DEADLOCK_THRESHOLD_TIMEOUT,
            task_config=TaskConfig(
                abandoned_timeout=env.PCSD_TASK_ABANDONED_TIMEOUT,
                unresponsive_timeout=env.PCSD_TASK_UNRESPONSIVE_TIMEOUT,
                deletion_timeout=env.PCSD_TASK_DELETION_TIMEOUT,
            ),
        )
    )
    auth_provider = AuthProvider(log.pcsd)
    SignalInfo.async_scheduler = async_scheduler

    sync_config_lock = Lock()
    ruby_pcsd_wrapper = ruby_pcsd.Wrapper(
        settings.pcsd_ruby_socket,
        debug=env.PCSD_DEBUG,
    )

    try:
        pcsd_capabilities = capabilities.get_pcsd_capabilities()
    except capabilities.CapabilitiesError as e:
        pcsd_capabilities = []
        log.pcsd.error(e.msg)

    make_app = configure_app(
        async_scheduler,
        auth_provider,
        session.Storage(env.PCSD_SESSION_LIFETIME),
        ruby_pcsd_wrapper,
        sync_config_lock,
        env.PCSD_STATIC_FILES_DIR,
        pcsd_capabilities,
        enable_webui=not env.PCSD_DISABLE_GUI,
        debug=env.PCSD_DEV,
    )
    pcsd_ssl = ssl.PcsdSSL(
        server_name=socket.gethostname(),
        cert_location=settings.pcsd_cert_location,
        key_location=settings.pcsd_key_location,
        ssl_options=env.PCSD_SSL_OPTIONS,
        ssl_ciphers=env.PCSD_SSL_CIPHERS,
    )
    try:
        SignalInfo.server_manage = HttpsServerManage(
            make_app,
            port=env.PCSD_PORT,
            bind_addresses=env.PCSD_BIND_ADDR,
            ssl=pcsd_ssl,
            unix_socket_path=settings.pcsd_unix_socket,
        ).start()
    except socket.gaierror as e:
        log.pcsd.error(
            "Unable to bind to specific address(es), exiting: %s ", e
        )
        raise SystemExit(1) from e
    except OSError as e:
        log.pcsd.error("Unable to start pcsd daemon, exiting: %s ", e)
        raise SystemExit(1) from e
    except ssl.SSLCertKeyException as e:
        for error in e.args:
            log.pcsd.error(error)
        log.pcsd.error("Invalid SSL certificate and/or key, exiting")
        raise SystemExit(1) from e

    PeriodicCallback(
        async_scheduler.perform_actions,
        callback_time=env.PCSD_CHECK_INTERVAL_MS,
    ).start()
    ioloop = IOLoop.current()
    ioloop.add_callback(sign_ioloop_started)
    if systemd.is_systemd() and env.NOTIFY_SOCKET:
        ioloop.add_callback(systemd.notify, env.NOTIFY_SOCKET)
    ioloop.add_callback(config_sync(sync_config_lock, ruby_pcsd_wrapper))
    ioloop.start()
