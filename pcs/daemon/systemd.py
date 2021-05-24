import socket
import os.path

from functools import lru_cache

from tornado.iostream import IOStream

from pcs import settings
from pcs.daemon import log


async def notify(socket_name):
    if socket_name[0] == "@":
        # abstract namespace socket
        socket_name = "\0" + socket_name[1:]

    log.pcsd.info("Notifying systemd we are running (socket '%s')", socket_name)
    try:
        stream = IOStream(socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM))
        await stream.connect(socket_name)
        await stream.write(b"READY=1")
        stream.close()
        # pylint: disable=broad-except
    except Exception as e:
        log.pcsd.error("Unable to notify systemd on '%s': %s", socket_name, e)


@lru_cache()
def is_systemd():
    return any(os.path.isdir(path) for path in settings.systemd_unit_path)
