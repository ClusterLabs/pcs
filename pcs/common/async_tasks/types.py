from enum import auto

from pcs.common.types import AutoNameEnum


class TaskFinishType(AutoNameEnum):
    UNFINISHED = auto()
    UNHANDLED_EXCEPTION = auto()
    FAIL = auto()
    SUCCESS = auto()
    KILL = auto()


class TaskState(AutoNameEnum):
    CREATED = auto()
    QUEUED = auto()
    EXECUTED = auto()
    FINISHED = auto()


class TaskKillReason(AutoNameEnum):
    USER = auto()
    COMPLETION_TIMEOUT = auto()
    ABANDONED = auto()
    INTERNAL_MESSAGING_ERROR = auto()
