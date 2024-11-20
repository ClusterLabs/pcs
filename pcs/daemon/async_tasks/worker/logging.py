import logging
import logging.handlers
import multiprocessing as mp
import os

WORKER_LOGGER = "pcs_worker"


class Logger(logging.Logger):
    def makeRecord(  # type: ignore
        self,
        name,
        level,
        fn,
        lno,
        msg,
        args,
        exc_info,
        func=None,
        extra=None,
        sinfo=None,
    ) -> logging.LogRecord:
        # pylint: disable=too-many-arguments
        # pylint: disable=too-many-positional-arguments
        pid = os.getpid()
        return super().makeRecord(
            name,
            level,
            fn,
            lno,
            f"Worker#{pid}: {msg}",
            args,
            exc_info,
            func=func,
            extra=extra,
            sinfo=sinfo,
        )


def setup_worker_logger(queue: mp.Queue) -> logging.Logger:
    """
    Creates and configures worker's logger
    :return: Logger instance
    """
    logging.setLoggerClass(Logger)
    logger = logging.getLogger(WORKER_LOGGER)
    logger.setLevel(logging.DEBUG)

    queue_handler = logging.handlers.QueueHandler(queue)
    logger.addHandler(queue_handler)

    return logger
