# pylint: disable=global-statement
import dataclasses
import inspect
import multiprocessing as mp
import os
import signal
from logging import (
    Logger,
    getLogger,
)
from typing import (
    Any,
    Tuple,
    Union,
)

import dacite

from pcs.common import reports
from pcs.common.async_tasks.dto import CommandOptionsDto
from pcs.common.async_tasks.types import TaskFinishType
from pcs.common.interface import dto
from pcs.lib.auth.tools import (
    DesiredUser,
    get_effective_user,
)
from pcs.lib.auth.types import AuthUser
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.permissions.checker import PermissionsChecker
from pcs.utils import read_known_hosts_file_not_cached

from .command_mapping import (
    API_V1_COMPATIBILITY_MODE,
    COMMAND_MAP,
)
from .communicator import WorkerCommunicator
from .logging import (
    WORKER_LOGGER,
    setup_worker_logger,
)
from .report_processor import WorkerReportProcessor
from .types import (
    Message,
    TaskExecuted,
    TaskFinished,
    WorkerCommand,
)

worker_com: WorkerCommunicator


def _sigterm_handler(sig_num: int, frame: Any) -> None:
    del sig_num, frame
    if worker_com.is_locked:
        worker_com.set_terminate()
    else:
        raise SystemExit(0)


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
    worker_com = WorkerCommunicator(message_q)

    def ignore_signals(sig_num, frame):  # type: ignore
        # pylint: disable=unused-argument
        pass

    signal.signal(signal.SIGINT, ignore_signals)
    signal.signal(signal.SIGTERM, _sigterm_handler)


def _pause_worker() -> None:
    logger = getLogger(WORKER_LOGGER)
    logger.debug(
        "Pausing worker until the scheduler updates status of this task."
    )
    os.kill(os.getpid(), signal.SIGSTOP)
    logger.debug("Worker unpaused.")


def _get_effective_user(
    logger: Logger, real_user: AuthUser, options: CommandOptionsDto
) -> AuthUser:
    effective_user = get_effective_user(
        real_user,
        DesiredUser(options.effective_username, options.effective_groups),
    )
    if real_user != effective_user:
        logger.debug(
            "Effective user=%s groups=%s",
            effective_user.username,
            ",".join(effective_user.groups),
        )
    return effective_user


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
    logger.info(
        "Task '%s' executed by user '%s'.",
        task.task_ident,
        task.auth_user.username,
    )
    request_timeout = task.command.command_dto.options.request_timeout
    if request_timeout is not None and request_timeout <= 0:
        logger.warning(
            "Invalid value '%s' for option 'request_timeout'", request_timeout
        )
        request_timeout = None
    auth_user = task.auth_user
    logger.debug(
        "Real user=%s groups=%s",
        auth_user.username,
        ",".join(auth_user.groups),
    )
    command_dto = task.command.command_dto
    if auth_user.is_superuser:
        auth_user = _get_effective_user(logger, auth_user, command_dto.options)

    env = LibraryEnvironment(  # type: ignore
        logger,
        WorkerReportProcessor(worker_com, task.task_ident),
        known_hosts_getter=read_known_hosts_file_not_cached,
        user_login=auth_user.username,
        user_groups=auth_user.groups,
        request_timeout=request_timeout,
    )

    task_retval = None
    command_name = command_dto.command_name
    try:
        if command_name not in COMMAND_MAP or (
            not task.command.api_v1_compatible
            and command_name in API_V1_COMPATIBILITY_MODE
        ):
            raise LibraryError(
                reports.ReportItem.error(
                    reports.messages.CommandUnknown(command_name)
                )
            )
        cmd = COMMAND_MAP[command_name]
        if not PermissionsChecker(logger).is_authorized(
            auth_user, cmd.required_permission
        ):
            raise LibraryError(
                reports.ReportItem.error(reports.messages.NotAuthorized())
            )
        # Dacite will validate command.params against command signature.
        # Dacite works only with dataclasses so we need to dynamically create
        # one
        try:
            data = dto.from_dict(
                dataclasses.make_dataclass(
                    f"{command_name}_params",
                    [
                        _param_to_field_tuple(param)
                        for param in list(
                            inspect.signature(cmd.cmd).parameters.values()
                        )[1:]
                    ],
                ),
                command_dto.params,
                strict=True,
            ).__dict__  # type: ignore
        except dacite.DaciteError as e:
            # TODO: make custom message from exception without mentioning
            # dataclasses and fields
            raise LibraryError(
                reports.ReportItem.error(
                    reports.messages.CommandInvalidPayload(str(e))
                )
            ) from e
        except dto.PayloadConversionError as e:
            raise LibraryError(
                reports.ReportItem.error(
                    reports.messages.CommandInvalidPayload("")
                )
            ) from e

        task_retval = cmd.cmd(env, **data)
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
        _pause_worker()
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
        _pause_worker()
        return
    worker_com.put(
        Message(
            task.task_ident,
            TaskFinished(TaskFinishType.SUCCESS, task_retval),
        )
    )
    logger.info("Task %s finished.", task.task_ident)
    _pause_worker()


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
