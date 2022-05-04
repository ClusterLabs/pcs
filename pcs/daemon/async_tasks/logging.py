import logging
import multiprocessing as mp
import os


class Logger(logging.Logger):
    # pylint: disable=too-many-arguments
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
    logger = logging.getLogger("pcs_worker")
    logger.setLevel(logging.DEBUG)

    queue_handler = logging.handlers.QueueHandler(queue)  # type: ignore
    logger.addHandler(queue_handler)

    return logger
