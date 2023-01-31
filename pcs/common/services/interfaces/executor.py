from pcs.common.types import StringSequence

from ..types import ExecutorResult


class ExecutorInterface:
    """
    Simple interface for executing external programs.
    """

    def run(self, args: StringSequence) -> ExecutorResult:
        """
        args -- Program and its arguments to execute. First item is path to a
            executable and rest of the items are arguments which will be provided
            to the executable.

        Execute a specified program synchronously and return its result after
        it's finished.
        """
        raise NotImplementedError()
