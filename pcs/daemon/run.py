import os
import signal
import socket
from functools import partial

from tornado.ioloop import IOLoop
from tornado.locks import Lock

from pcs import settings
from pcs.daemon import log, systemd, session, ruby_pcsd, app
from pcs.daemon.env import prepare_env
from pcs.daemon.http_server import HttpsServerManage

class SignalInfo:
    #pylint: disable=too-few-public-methods
    server_manage = None
    ioloop_started = False

def handle_signal(incomming_signal, frame):
    #pylint: disable=unused-argument
    log.pcsd.warning('Caught signal: %s, shutting down', incomming_signal)
    if SignalInfo.server_manage:
        SignalInfo.server_manage.stop()
    if SignalInfo.ioloop_started:
        IOLoop.current().stop()
    raise SystemExit(0)

def sign_ioloop_started():
    SignalInfo.ioloop_started = True

def config_sync(
    sync_config_lock: Lock, ruby_pcsd_wrapper: ruby_pcsd.Wrapper
):
    async def config_synchronization():
        async with sync_config_lock:
            next_run_time = await ruby_pcsd_wrapper.sync_configs()
        IOLoop.current().call_at(next_run_time, config_synchronization)
    return config_synchronization

def main():
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    log.setup(settings.pcsd_log_location)

    env = prepare_env(os.environ, log.pcsd)
    if env.has_errors:
        raise SystemExit(1)

    sync_config_lock = Lock()
    ruby_pcsd_wrapper = ruby_pcsd.Wrapper(
        gem_home=env.GEM_HOME,
        pcsd_cmdline_entry=env.PCSD_CMDLINE_ENTRY,
        log_file_location=settings.pcsd_log_location,
        debug=env.PCSD_DEBUG,
        ruby_executable=settings.ruby_executable
    )
    make_app = partial(
        app.make_app,
        session.Storage(env.PCSD_SESSION_LIFETIME),
        ruby_pcsd_wrapper,
        sync_config_lock,
        env.PCSD_STATIC_FILES_DIR,
        disable_gui=env.PCSD_DISABLE_GUI,
        debug=env.PCSD_DEBUG,
    )
    try:
        SignalInfo.server_manage = HttpsServerManage(
            make_app,
            server_name=socket.gethostname(),
            port=env.PCSD_PORT,
            bind_addresses=env.PCSD_BIND_ADDR,
            ssl_options=env.PCSD_SSL_OPTIONS,
            ssl_ciphers=env.PCSD_SSL_CIPHERS,
            cert_location=settings.pcsd_cert_location,
            key_location=settings.pcsd_key_location,
        ).start()
    except socket.gaierror as e:
        log.pcsd.error(f"Unable to bind to specific address(es), exiting: {e} ")
        raise SystemExit(1)
    except OSError as e:
        log.pcsd.error(f"Unable to start pcsd daemon, exiting: {e} ")
        raise SystemExit(1)

    ioloop = IOLoop.current()
    ioloop.add_callback(sign_ioloop_started)
    if systemd.is_systemd() and env.NOTIFY_SOCKET:
        ioloop.add_callback(systemd.notify, env.NOTIFY_SOCKET)
    ioloop.add_callback(config_sync(sync_config_lock, ruby_pcsd_wrapper))
    ioloop.start()
