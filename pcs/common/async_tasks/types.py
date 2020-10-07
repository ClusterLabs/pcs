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


class TaskKillOrigin(AutoNameEnum):
    USER = auto()
    SCHEDULER = auto()
