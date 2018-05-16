import logging

LOGGER_NAMES = [
    "pcs.daemon",
    "tornado.application",
    "tornado.access",
    "tornado.general",
]

class Formatter(logging.Formatter):
    default_time_format = '%Y-%m-%dT%H:%M:%S'
    # It produces `datetime.miliseconds`
    default_msec_format = '%s.%03d'
    py_to_rb_level_name_map = {
        "WARNING": "WARN",
        "CRITICAL": "FATAL",
    }

    def __init__(self):
        super().__init__(
            # Python uses only milseconds so there are 3 spaces to align it with
            # ruby where microseconds are used.
            fmt="{levelname[0]}, [{asctime}    #{process}]"
                " {levelname:>5s} -- : {message}"
            ,
            datefmt=None,
            style="{"
        )

    def format(self, record):
        # The levelname should be the same as in Ruby. Note that ruby uses width
        # up to 5 for levelname. So the levels WARNING and CRITICAL would break
        # the log alignment.
        if record.levelname in self.py_to_rb_level_name_map:
            record.levelname = self.py_to_rb_level_name_map[record.levelname]
        return super().format(record)

def setup(log_file):
    handler = logging.handlers.WatchedFileHandler(log_file, encoding="utf8")
    handler.setFormatter(Formatter())

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
        logging.getLogger(logger_name).setLevel(logging.DEBUG)

#pylint:disable=invalid-name
pcsd = logging.getLogger("pcs.daemon")
