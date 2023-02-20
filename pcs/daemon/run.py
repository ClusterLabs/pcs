import os
import signal
import socket
from pathlib import Path

from tornado.ioloop import IOLoop
from tornado.locks import Lock
from tornado.web import Application

from pcs import settings
from pcs.daemon import (
    log,
    ruby_pcsd,
    session,
    ssl,
    systemd,
)
from pcs.daemon.app import (
    sinatra_remote,
    sinatra_ui,
    ui,
)
from pcs.daemon.app.common import (
    Http404Handler,
    RedirectHandler,
)
from pcs.daemon.env import prepare_env
from pcs.daemon.http_server import HttpsServerManage


class SignalInfo:
    # pylint: disable=too-few-public-methods
    server_manage = None
    ioloop_started = False


def handle_signal(incoming_signal, frame):
    # pylint: disable=unused-argument
    log.pcsd.warning("Caught signal: %s, shutting down", incoming_signal)
    if SignalInfo.server_manage:
        SignalInfo.server_manage.stop()
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
    session_storage: session.Storage,
    ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
    sync_config_lock: Lock,
    public_dir,
    disable_gui=False,
    debug=False,
):
    def make_app(https_server_manage: HttpsServerManage):
        """
        https_server_manage -- allows to control the server (specifically
            reload its SSL certificates). A relevant handler should get this
            object via the method `initialize`.
        """
        routes = sinatra_remote.get_routes(
            ruby_pcsd_wrapper,
            sync_config_lock,
            https_server_manage,
        )

        if not disable_gui:
            routes.extend(
                # old web ui by default
                [(r"/", RedirectHandler, dict(url="/manage"))]
                + [(r"/ui", RedirectHandler, dict(url="/ui/"))]
                + ui.get_routes(
                    url_prefix="/ui/",
                    app_dir=os.path.join(public_dir, "ui"),
                    fallback_page_path=os.path.join(
                        public_dir,
                        "ui_instructions.html",
                    ),
                    session_storage=session_storage,
                )
                + sinatra_ui.get_routes(
                    session_storage, ruby_pcsd_wrapper, public_dir
                )
            )

        return Application(
            routes, debug=debug, default_handler_class=Http404Handler
        )

    return make_app


def main():
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    Path(settings.pcsd_log_location).touch(mode=0o600, exist_ok=True)
    log.setup(settings.pcsd_log_location)

    env = prepare_env(os.environ, log.pcsd)
    if env.has_errors:
        raise SystemExit(1)

    if env.PCSD_DEBUG:
        log.enable_debug()

    sync_config_lock = Lock()
    ruby_pcsd_wrapper = ruby_pcsd.Wrapper(
        settings.pcsd_ruby_socket,
        debug=env.PCSD_DEBUG,
    )
    make_app = configure_app(
        session.Storage(env.PCSD_SESSION_LIFETIME),
        ruby_pcsd_wrapper,
        sync_config_lock,
        env.PCSD_STATIC_FILES_DIR,
        disable_gui=env.PCSD_DISABLE_GUI,
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

    ioloop = IOLoop.current()
    ioloop.add_callback(sign_ioloop_started)
    if systemd.is_systemd() and env.NOTIFY_SOCKET:
        ioloop.add_callback(systemd.notify, env.NOTIFY_SOCKET)
    ioloop.add_callback(config_sync(sync_config_lock, ruby_pcsd_wrapper))
    ioloop.start()
