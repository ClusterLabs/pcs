import os
import signal
import socket
from functools import partial

from tornado.ioloop import IOLoop
from tornado.locks import Lock

from pcs import settings
from pcs.daemon import log, systemd, session
from pcs.daemon.app import make_app, sync_configs
from pcs.daemon.env import EnvPrepare
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
        log.pcsd.warning("IOLOOP stop")
        IOLoop.current().stop()
    raise SystemExit(0)

def sign_ioloop_started():
    SignalInfo.ioloop_started = True

def get_config_synchronization(sync_config_lock: Lock):
    async def config_synchronization():
        next_run_time = await sync_configs(sync_config_lock)
        IOLoop.current().call_at(next_run_time, config_synchronization)
    return config_synchronization

def main():
    log.setup()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    env_prepare = EnvPrepare(os.environ)

    if env_prepare.errors:
        for error in env_prepare.errors:
            log.pcsd.error(error)
        raise SystemExit(1)

    env = env_prepare.env
    sync_config_lock = Lock()
    try:
        SignalInfo.server_manage = HttpsServerManage(
            partial(
                make_app,
                session.Storage(env.PCSD_SESSION_LIFETIME),
                sync_config_lock,
                disable_gui=env.DISABLE_GUI,
                debug=env.DEBUG
            ),
            server_name=socket.gethostname(),
            port=env.PCSD_PORT,
            bind_addresses=env.PCSD_BIND_ADDR,
            ssl_options=env.PCSD_SSL_OPTIONS,
            ssl_ciphers=env.PCSD_SSL_CIPHERS,
            cert_location=settings.pcsd_cert_location,
            key_location=settings.pcsd_key_location,
        )

        ioloop = IOLoop.current()
        ioloop.add_callback(sign_ioloop_started)
        if systemd.is_systemd() and env.NOTIFY_SOCKET:
            ioloop.add_callback(systemd.notify, env.NOTIFY_SOCKET)
        ioloop.add_callback(get_config_synchronization(sync_config_lock))
        ioloop.start()
    except OSError as e:
        log.pcsd.error(f"Unable to bind to specific address(es), exiting: {e} ")
        raise SystemExit(1)
