import logging
import multiprocessing as mp


def setup_worker_logger(queue: mp.Queue) -> logging.Logger:
    """
    Creates and configures worker's logger
    :return: Logger instance
    """
    logger = logging.getLogger("pcs_worker")
    logger.setLevel(logging.DEBUG)

    queue_handler = logging.handlers.QueueHandler(queue)
    queue_handler.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)

    return logger
