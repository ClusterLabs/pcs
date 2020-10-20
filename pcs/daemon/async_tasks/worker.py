import multiprocessing as mp
import os
import signal

from dataclasses import dataclass
from logging import Logger

from pcs.common.async_tasks.dto import CommandDto
from pcs.common.async_tasks.types import TaskFinishType
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from .command_mapping import command_map
from .logging import setup_worker_logger
from .messaging import (
    Message,
    MessageType,
    TaskExecuted,
    TaskFinished,
)
from .report_proc import WorkerReportProcessor

logger: Logger


@dataclass(frozen=True)
class WorkerCommand:
    task_ident: str
    command: CommandDto


def worker_init() -> None:
    """
    Runs in every new worker process after its creation
    """
    # Create and configure new logger
    global logger
    logger = setup_worker_logger()
    logger.info("Worker initialized.")

    def ignore_signals(sig_num, frame):  # type: ignore
        # pylint: disable=unused-argument
        pass

    def flush_logs(sig_num, frame):  # type: ignore
        # pylint: disable=unused-argument
        for handler in logger.handlers:
            handler.flush()
            handler.close()

    signal.signal(signal.SIGINT, ignore_signals)
    signal.signal(signal.SIGTERM, flush_logs)


def task_executor(task: WorkerCommand, worker_com: mp.Queue) -> None:
    """
    Launches the task inside the worker
    :param task: Task identifier, command and parameter object
    :param worker_com: Queue instance for sending messages to scheduler
    """
    # pylint: disable=broad-except
    global logger
    worker_com.put(
        Message(
            task.task_ident,
            MessageType.TASK_EXECUTED,
            TaskExecuted(os.getpid()),
        )
    )
    logger.info("Task %s executed.", task.task_ident)

    env = LibraryEnvironment(  # type: ignore
        logger, WorkerReportProcessor(worker_com, task.task_ident),
    )

    task_retval = None
    try:
        task_retval = command_map[task.command.command_name](
            env, **task.command.params
        )
    except LibraryError as e:
        # Some code uses args for storing ReportList, sending them to the report
        # processor here

        for report in e.args:
            worker_com.put(Message(task.task_ident, MessageType.REPORT, report))
        worker_com.put(
            Message(
                task.task_ident,
                MessageType.TASK_FINISHED,
                TaskFinished(TaskFinishType.FAIL, None),
            )
        )
        logger.exception("Task %s raised a LibraryException.", task.task_ident)
        return
    except Exception:
        # For unhandled exceptions during execution
        worker_com.put(
            Message(
                task.task_ident,
                MessageType.TASK_FINISHED,
                TaskFinished(TaskFinishType.UNHANDLED_EXCEPTION, None),
            )
        )
        logger.exception(
            "Task %s raised an unhandled exception.", task.task_ident
        )
        return
    worker_com.put(
        Message(
            task.task_ident,
            MessageType.TASK_FINISHED,
            TaskFinished(TaskFinishType.SUCCESS, task_retval),
        )
    )
    logger.info("Task %s finished.", task.task_ident)
