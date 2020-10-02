import multiprocessing as mp
import os

from logging import Logger
from typing import Optional

from pcs.daemon.async_tasks.command_mapping import command_map
from pcs.daemon.async_tasks.logging import setup_worker_logger
from pcs.daemon.async_tasks.messaging import (
    Message,
    MessageType,
    TaskExecuted,
    TaskFinished,
)
from pcs.daemon.async_tasks.report_proc import WorkerReportProcessor
from pcs.daemon.async_tasks.task import WorkerCommand, TaskFinishType
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError

logger: Optional[Logger] = None


def worker_init():
    import signal

    # Create and configure new logger
    global logger
    logger = setup_worker_logger()
    logger.info("Worker initialized.")

    def ignore_signals(sig_num, frame):
        pass

    def flush_logs(sig_num, frame):
        for handler in logger.handlers:
            handler.flush()
            handler.close()

    signal.signal(signal.SIGINT, ignore_signals)
    signal.signal(signal.SIGTERM, flush_logs)


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