import logging
from tornado.log import enable_pretty_logging

def setup():
    handler = logging.FileHandler("/var/log/pcsd/pcsd.log")
    enable_pretty_logging()

    pcsd_log = logging.getLogger("pcs.daemon")
    pcsd_log.addHandler(handler)
    pcsd_log.setLevel(logging.INFO)

    app_log = logging.getLogger("tornado.application")
    app_log.addHandler(handler)
    app_log.setLevel(logging.INFO)

    access_log = logging.getLogger("tornado.access")
    access_log.addHandler(handler)
    access_log.setLevel(logging.INFO)

    general_log = logging.getLogger("tornado.general")
    general_log.addHandler(handler)
    general_log.setLevel(logging.INFO)

pcsd = logging.getLogger("pcs.daemon")
