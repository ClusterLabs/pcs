import os
import signal
import socket

from tornado.ioloop import IOLoop

from pcs import settings
from pcs.daemon import log, systemd
from pcs.daemon.app import make_app
from pcs.daemon.http_server import HttpsServerManage
from pcs.daemon.env import EnvPrepare

class SignalInfo:
    server_manage = None
    ioloop_started = False

def handle_signal(signal, frame):
    log.pcsd.warning('Caught signal: %s, shutting down', signal)
    if SignalInfo.server_manage:
        SignalInfo.server_manage.stop()
    if SignalInfo.ioloop_started:
        log.pcsd.warning("IOLOOP stop")
        IOLoop.current().stop()
    raise SystemExit(1)

async def notify_systemd(env):
    if systemd.is_systemd() and env.NOTIFY_SOCKET:
        try:
            await systemd.notify(env.NOTIFY_SOCKET)
        except systemd.NotifyError as e:
            log.pcsd.error(f"Unable to notify systemd: {e}")
            raise SystemExit(1)

def sign_ioloop_started():
    SignalInfo.ioloop_started = True

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
        )

        IOLoop.current().add_callback(notify_systemd, env)
        IOLoop.current().add_callback(sign_ioloop_started)
        IOLoop.current().start()

    except OSError as e:
        log.pcsd.error(f"Unable to bind to specific address(es), exiting: {e} ")
        raise SystemExit(1)
