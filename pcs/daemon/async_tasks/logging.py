import datetime
import logging
import os

import pcs.settings as settings


def setup_scheduler_logger() -> logging.Logger:
    """
    Creates and configures scheduler's logger
    :return: Logger instance
    """
    logger = logging.getLogger("pcs_scheduler")
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(
        settings.async_api_log_filename, "a", "utf8"
    )
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    formatter = logging.Formatter(
        "{asctime} | {levelname}: {message}", style="{"
    )
    file_handler.setFormatter(formatter)

    return logger


def setup_worker_logger() -> logging.Logger:
    """
    Creates and configures worker's logger
    :return: Logger instance
    """
    logger = logging.getLogger(f"pcs_worker_{os.getpid()}")
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(
        f"{settings.worker_logs_path}/"
        f"{datetime.datetime.now().strftime('%Y%m%d%H%M')}_"
        f"{os.getpid()}.log",
        "w",
        "utf8",
    )
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    formatter = logging.Formatter(
        "{asctime} | {levelname}: {message}", style="{"
    )
    file_handler.setFormatter(formatter)

    return logger
