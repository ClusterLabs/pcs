from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.command_env.config_runner import (
    RunnerConfig,
    CallCollection,
)


class Config(object):
    def __init__(self, runner=None):
        self.__runner_calls = CallCollection()
        self.runner = runner if runner else RunnerConfig(self.__runner_calls)

    @property
    def runner_calls(self):
        return self.__runner_calls.calls
