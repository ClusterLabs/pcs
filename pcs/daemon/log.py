import logging

LOGGER_NAMES = [
    "pcs.daemon",
    "pcs.daemon.scheduler",
    "tornado.application",
    "tornado.access",
    "tornado.general",
]

# pylint:disable=invalid-name
pcsd = logging.getLogger("pcs.daemon")


def from_external_source(level, created: float, usecs: int, message, group_id):
    record = pcsd.makeRecord(
        name=pcsd.name,
        level=level,
        # Information about stack fram is not needed here. Values are
        # inspired by the code of the logging module.
        fn="(external)",
        lno=0,
        # Message from ruby does not need args.
        msg=message,
        args=[],
        # The exception information makes not sense here.
        exc_info=None,
    )

    # A value of attribute relativelyCreated is in logging module calculated by
    # this way:
    # self.relativeCreated = (self.created - _startTime) * 1000
    # To update it, we need to reduce it by difference between current value
    # of attribute created (which is newer, so higher) and the correct one
    # (which comes from an external source)
    record.relativeCreated -= (record.created - created) * 1000
    record.created = created
    record.msec = usecs // 1000
    record.pcsd_group_id = str(group_id).zfill(5)
    pcsd.handle(record)


class Formatter(logging.Formatter):
    default_time_format = "%Y-%m-%dT%H:%M:%S"
    # It produces `datetime.milliseconds`
    default_msec_format = "%s.%03d"

    def __init__(self):
        super().__init__(
            fmt="{levelname[0]}, [{asctime} #{pcsd_group_id}]"
            " {levelname:>8s} -- : {message}",
            datefmt=None,
            style="{",
        )

    def format(self, record):
        # Non-external records, which are currently the minority, needs to be
        # extended by group_id (see init arugument fmt and function
        # from_external_source).
        if not hasattr(record, "pcsd_group_id"):
            record.pcsd_group_id = "00000"
        return super().format(record)


def setup(log_file):
    handler = logging.handlers.WatchedFileHandler(log_file, encoding="utf8")
    handler.setFormatter(Formatter())
    handler.setLevel(logging.INFO)

    for logger_name in LOGGER_NAMES:
        pcsd_log = logging.getLogger(logger_name)
        pcsd_log.addHandler(handler)
        pcsd_log.setLevel(logging.INFO)


def enable_debug():
    # Debug messages won't be written if we call setLevel(logging.DEBUG) on the
    # handler when loggers itself have an higher level. So the level is set to
    # the loggers. Our handler has the implicit NOTSET level and there is no
    # reason to make it more complicated currently.
    for logger_name in LOGGER_NAMES:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
