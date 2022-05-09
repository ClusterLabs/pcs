# pylint: disable=global-statement
import dataclasses
import inspect
import multiprocessing as mp
import os
import signal
from dataclasses import dataclass
from logging import getLogger
from typing import (
    Any,
    Tuple,
    Union,
)

import dacite

from pcs.common import reports
from pcs.common.async_tasks.dto import CommandDto
from pcs.common.async_tasks.types import TaskFinishType
from pcs.common.interface import dto
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError

from .command_mapping import command_map
from .logging import (
    WORKER_LOGGER,
    setup_worker_logger,
)
from .messaging import (
    Message,
    TaskExecuted,
    TaskFinished,
)
from .report_proc import WorkerReportProcessor

worker_com: mp.Queue


@dataclass(frozen=True)
class WorkerCommand:
    task_ident: str
    command: CommandDto


def worker_init(message_q: mp.Queue, logging_q: mp.Queue) -> None:
    """
    Runs in every new worker process after its creation
    :param message_q: Queue instance for sending messages to the scheduler
    :param logging_q: Queue instance for sending log records to the scheduler
    """
    # Create and configure new logger
    logger = setup_worker_logger(logging_q)
    logger.info("Worker initialized.")

    # Let task_executor use worker_com for sending messages to the scheduler
    global worker_com
    worker_com = message_q

    def ignore_signals(sig_num, frame):  # type: ignore
        # pylint: disable=unused-argument
        pass

    signal.signal(signal.SIGINT, ignore_signals)


def pause_worker() -> None:
    logger = getLogger(WORKER_LOGGER)
    logger.debug(
        "Pausing worker until the scheduler updates status of this task."
    )
    os.kill(os.getpid(), signal.SIGSTOP)
    logger.debug("Worker unpaused.")


def task_executor(task: WorkerCommand) -> None:
    """
    Launches the task inside the worker
    :param task: Task identifier, command and parameter object
    """
    logger = getLogger(WORKER_LOGGER)

    worker_com.put(
        Message(
            task.task_ident,
            TaskExecuted(os.getpid()),
        )
    )
    logger.info("Task %s executed.", task.task_ident)

    env = LibraryEnvironment(  # type: ignore
        logger,
        WorkerReportProcessor(worker_com, task.task_ident),
    )

    task_retval = None
    command = task.command.command_name
    try:
        if command not in command_map:
            raise LibraryError(
                reports.ReportItem.error(
                    reports.messages.CommandUnknown(command)
                )
            )
        # Dacite will validate command.params against command signature.
        # Dacite works only with dataclasses so we need to dinamically create
        # one
        try:
            dto.from_dict(
                dataclasses.make_dataclass(
                    f"{command}_params",
                    [
                        _param_to_field_tuple(param)
                        for param in list(
                            inspect.signature(
                                command_map[command]
                            ).parameters.values()
                        )[1:]
                    ],
                ),
                task.command.params,
                strict=True,
            )
        except dacite.DaciteError as e:
            # TODO: make custom message from exception without mentioning
            # dataclasses and fields
            raise LibraryError(
                reports.ReportItem.error(
                    reports.messages.CommandInvalidPayload(str(e))
                )
            ) from e

        task_retval = command_map[command](  # type: ignore
            env, **task.command.params
        )
    except LibraryError as e:
        # Some code uses args for storing ReportList, sending them to the report
        # processor here

        for report in e.args:
            # pylint: disable=no-member
            worker_com.put(Message(task.task_ident, report.to_dto()))
        worker_com.put(
            Message(
                task.task_ident,
                TaskFinished(TaskFinishType.FAIL, None),
            )
        )
        logger.exception("Task %s raised a LibraryError.", task.task_ident)
        pause_worker()
        return
    except Exception as e:  # pylint: disable=broad-except
        # For unhandled exceptions during execution
        worker_com.put(
            Message(
                task.task_ident,
                TaskFinished(TaskFinishType.UNHANDLED_EXCEPTION, None),
            )
        )
        logger.exception(
            "Task %s raised an unhandled exception: %s", task.task_ident, e
        )
        pause_worker()
        return
    worker_com.put(
        Message(
            task.task_ident,
            TaskFinished(TaskFinishType.SUCCESS, task_retval),
        )
    )
    logger.info("Task %s finished.", task.task_ident)
    pause_worker()


def _param_to_field_tuple(
    param: inspect.Parameter,
) -> Union[Tuple[str, Any], Tuple[str, Any, dataclasses.Field]]:
    field_type = Any
    if param.annotation != inspect.Parameter.empty:
        field_type = param.annotation
    if param.default != inspect.Parameter.empty:
        return (
            param.name,
            field_type,
            dataclasses.field(default=param.default),
        )
    return (param.name, field_type)
