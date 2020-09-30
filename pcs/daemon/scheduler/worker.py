import multiprocessing as mp
import os

from logging import Logger
from typing import Optional

from pcs.daemon.scheduler.command_mapping import command_map
from pcs.daemon.scheduler.logging import setup_worker_logger
from pcs.daemon.scheduler.messaging import (
    Message,
    MessageType,
    TaskExecuted,
    TaskFinished,
)
from pcs.daemon.scheduler.report_proc import WorkerReportProcessor
from pcs.daemon.scheduler.task import WorkerCommand, TaskFinishType
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError

logger: Optional[Logger] = None


def worker_init():
    import signal

    def ignore_signals(sig_num, frame):
        pass

    signal.signal(signal.SIGINT, ignore_signals)
    # signal.signal(signal.SIGTERM, finish_logging)
    # Create and configure new logger
    global logger
    logger = setup_worker_logger()
    logger.info("Worker initialized.")


def task_executor(task: WorkerCommand, worker_com: mp.Queue) -> None:
    global logger
    worker_com.put(
        Message(
            task.task_ident,
            MessageType.TASK_EXECUTED,
            TaskExecuted(os.getpid()),
        )
    )
    logger.info(f"Task {task.task_ident} executed.")

    env = LibraryEnvironment(
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
        logger.exception("Task raised a LibraryException.")
        return
    except Exception as e:
        # For unhandled exceptions during execution
        worker_com.put(
            Message(
                task.task_ident,
                MessageType.TASK_FINISHED,
                TaskFinished(TaskFinishType.UNHANDLED_EXCEPTION, None),
            )
        )
        logger.exception("Task raised an unhandled exception.")
        return
    worker_com.put(
        Message(
            task.task_ident,
            MessageType.TASK_FINISHED,
            TaskFinished(TaskFinishType.SUCCESS, task_retval),
        )
    )
    logger.info("Task finished.")
