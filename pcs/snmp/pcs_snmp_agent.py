import logging
import logging.handlers
import os
import sys

# pylint: disable=import-error
import pyagentx

import pcs.utils
from pcs.snmp import settings
from pcs.snmp.updaters.v1 import ClusterPcsV1Updater

logger = logging.getLogger("pcs.snmp")
logger.addHandler(logging.NullHandler())


def is_debug():
    debug = os.environ.get("PCS_SNMP_AGENT_DEBUG", "")
    return debug.lower() in ["true", "on", "1"]


def get_update_interval():
    interval = os.environ.get("PCS_SNMP_AGENT_UPDATE_INTERVAL")
    if not interval:
        return settings.DEFAULT_UPDATE_INTERVAL

    def _log_invalid_value(_value):
        logger.warning(
            "Invalid update interval value: '%s' is not >= 1.0", str(_value)
        )
        logger.debug(
            "Using default update interval: %s",
            str(settings.DEFAULT_UPDATE_INTERVAL),
        )

    try:
        interval = float(interval)
    except ValueError:
        _log_invalid_value(interval)
        return settings.DEFAULT_UPDATE_INTERVAL
    if interval <= 1.0:
        _log_invalid_value(interval)
        return settings.DEFAULT_UPDATE_INTERVAL
    return interval


def setup_logging(debug=False):
    level = logging.INFO
    if debug:
        level = logging.DEBUG
        # this is required to enable debug also in the ruby code
        # key '--debug' has to be added
        pcs.utils.pcs_options["--debug"] = debug
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler = logging.handlers.WatchedFileHandler(
        settings.LOG_FILE, encoding="utf8"
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    for logger_name in ["pyagentx", "pcs"]:
        logger_instance = logging.getLogger(logger_name)
        logger_instance.setLevel(level)
        logger_instance.addHandler(handler)


class PcsAgent(pyagentx.Agent):
    def setup(self):
        update_interval = get_update_interval()
        logger.info("Update interval set to: %s", str(update_interval))
        self.register(
            settings.PCS_OID + ".1",
            ClusterPcsV1Updater,
            freq=update_interval,
        )


def main():
    setup_logging(is_debug())
    try:
        agent = PcsAgent()
        agent.start()
    # pylint: disable=broad-except
    except Exception as e:
        print("Unhandled exception: {0}".format(str(e)))
        agent.stop()
        sys.exit(1)
    except KeyboardInterrupt:
        agent.stop()
