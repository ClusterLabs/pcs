import logging
import multiprocessing as mp
import os

from pcs.lib.env import LibraryEnvironment
from pcs.lib.commands import status
from .messaging import (
    Message,
    MessageType,
    TaskExecuted,
    TaskFinished,
)
from .report_proc import WorkerReportProcessor
from .task import WorkerCommand



def worker_init():
    import signal

    def ignore_signals(sig_num, frame):
        pass

    signal.signal(signal.SIGINT, ignore_signals)

def worker_error():
    pass

def task_executor(task: WorkerCommand, worker_com: mp.Queue) -> None:
    worker_com.put(Message(
        task.task_ident, MessageType.TASK_EXECUTED, TaskExecuted(os.getpid())
        )
    )

    env = LibraryEnvironment(
        logging.getLogger("pcs worker"),
        WorkerReportProcessor(worker_com, task.task_ident)
    )

    task_retval = None
    try:
        task_retval = \
            command_map[task.command.command_name](env, **task.command.params)
        #TODO Implement command map
    except:
        #TODO Pass error to the scheduler (new message type?)
        pass
    worker_com.put(
        Message(
            task.task_ident,
            MessageType.TASK_FINISHED,
            TaskFinished(task_retval)
        )
    )