import multiprocessing as mp
import os
import signal
import socket
import sys
from logging import Logger
from pathlib import Path
from typing import Iterable, Optional

from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.locks import Lock
from tornado.web import Application

from pcs import settings
from pcs.common import capabilities
from pcs.common.types import StringCollection
from pcs.daemon import log, ruby_pcsd, ssl, systemd
from pcs.daemon.app import (
    api_v0,
    api_v1,
    api_v2,
    auth,
    auth_provider,
    sinatra_remote,
    sinatra_ui,
    ui_manage,
)
from pcs.daemon.app import capabilities as capabilities_app

try:
    from pcs.daemon.app import webui
except ImportError:
    webui = None

from pcs.common.communication.logger import CommunicatorLogger
from pcs.common.node_communicator import NodeCommunicatorFactory
from pcs.common.reports.processor import ReportProcessorToLog
from pcs.daemon.app.common import Http404Handler, RedirectHandler
from pcs.daemon.async_tasks.scheduler import Scheduler, SchedulerConfig
from pcs.daemon.async_tasks.task import TaskConfig
from pcs.daemon.env import prepare_env
from pcs.daemon.http_server import HttpsServerManage
from pcs.daemon.pcs_cfgsync import CfgSyncPullManager
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


def create_pull_manager(logger: Logger) -> CfgSyncPullManager:
    log_report_processor = ReportProcessorToLog(logger)
    node_communicator = NodeCommunicatorFactory(
        CommunicatorLogger([log_report_processor]),
        user=None,
        groups=None,
        # 30, because cfgsync in ruby used the same value. Probably
        # because 30 was default for request timeouts back then.
        # This value might be reconsider
        request_timeout=30,
    ).get_communicator()
    return CfgSyncPullManager(log_report_processor, node_communicator, logger)


async def config_sync(
    sync_config_lock: Lock, config_puller: CfgSyncPullManager
):
    async with sync_config_lock:
        # run_cfgsync sends requests to all cluster nodes, including the local
        # one. However, this runs in the same IOLoop as the async_scheduler
        # that handles these requests -> so run cfgsync waits for responses
        # but the async scheduler cannot process them, resulting in timeout.
        # So we need to run this blocking function in executor
        next_run_after_seconds = await IOLoop.current().run_in_executor(
            None, lambda: config_puller.run_cfgsync()
        )
    IOLoop.current().call_later(
        next_run_after_seconds,
        lambda: config_sync(sync_config_lock, config_puller),
    )


def configure_app(  # noqa: PLR0913
    async_scheduler: Scheduler,
    lib_auth_provider: AuthProvider,
    session_lifetime: int,
    ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
    sync_config_lock: Lock,
    webui_dir: str,
    webui_fallback: str,
    pcsd_capabilities: Iterable[capabilities.Capability],
    *,
    debug: bool = False,
):
    # pylint: disable=too-many-arguments
    def make_app(https_server_manage: HttpsServerManage):
        """
        https_server_manage -- allows to control the server (specifically
            reload its SSL certificates). A relevant handler should get this
            object via the method `initialize`.
        """

        routes = api_v2.get_routes(async_scheduler, lib_auth_provider)
        routes.extend(api_v1.get_routes(async_scheduler, lib_auth_provider))
        routes.extend(api_v0.get_routes(async_scheduler, lib_auth_provider))
        routes.extend(auth.get_routes(lib_auth_provider))
        routes.extend(
            capabilities_app.get_routes(lib_auth_provider, pcsd_capabilities)
        )
        routes.extend(
            sinatra_remote.get_routes(
                ruby_pcsd_wrapper,
                sync_config_lock,
                https_server_manage,
                lib_auth_provider,
            )
        )

        # Create common auth provider factories
        socket_factory = auth_provider.UnixSocketAuthProviderFactory(
            lib_auth_provider
        )

        if webui:
            session_storage = webui.session.Storage(session_lifetime)
            routes.extend(
                [(r"/(ui)?", RedirectHandler, dict(url="/ui/"))]
                + webui.core.get_routes(
                    url_prefix="/ui/",
                    app_dir=webui_dir,
                    fallback_page_path=webui_fallback,
                    session_storage=session_storage,
                    auth_provider=lib_auth_provider,
                )
            )
            # Create WebUI auth factory (session -> socket fallback)
            session_factory = webui.auth_provider.SessionAuthProviderFactory(
                lib_auth_provider, session_storage
            )
            ui_auth_factory = auth_provider.AuthProviderMultiFactory(
                [session_factory, socket_factory]
            )
        else:
            # No WebUI: only socket authentication
            ui_auth_factory = socket_factory

        # Even with disabled (standalone) webui the following routes must be
        # provided because they can be used via unix socket from cockpit.
        # Handlers for these routes are the same in both cases, the only
        # difference is the authentication method used.
        routes.extend(ui_manage.get_routes(ui_auth_factory, async_scheduler))
        routes.extend(sinatra_ui.get_routes(ui_auth_factory, ruby_pcsd_wrapper))

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
    lib_auth_provider = AuthProvider(log.pcsd)
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
        lib_auth_provider,
        env.PCSD_SESSION_LIFETIME,
        ruby_pcsd_wrapper,
        sync_config_lock,
        env.WEBUI_DIR,
        env.WEBUI_FALLBACK,
        pcsd_capabilities,
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

    cfgsync_pull_manager = create_pull_manager(log.pcsd)
    ioloop.add_callback(
        lambda: config_sync(sync_config_lock, cfgsync_pull_manager)
    )
    ioloop.start()
