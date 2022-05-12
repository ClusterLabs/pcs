import multiprocessing as mp
from threading import Lock

from .messaging import Message


class WorkerCommunicator:
    def __init__(self, queue: mp.Queue):
        self._queue = queue
        self._lock = Lock()
        self._terminate = False

    def set_terminate(self) -> None:
        self._terminate = True

    @property
    def is_locked(self) -> bool:
        return self._lock.locked()

    def put(self, msg: Message) -> None:
        with self._lock:
            self._queue.put(msg)
        if self._terminate:
            raise SystemExit(0)
