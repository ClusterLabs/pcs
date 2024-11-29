"""
This is the set of tools for testing commands (pcs.lib.commands).

The principle is to patch some parts of the library environment object
(pcs.lib.env.LibraryEnvironment) that is passed as first argument to each
command.

Important parts:
================
CallListBuilder + (Call)Queue
-----------------------------
Both objects stores list of calls (messages to the mocked parts of environment).
CallListBuilder is used in configuration phase (before command run) to build
the call list.
Queue is used in run phase (during command run) to check that everything is done
as expected.

Mocks (Runner, push_cib, ...)
-----------------------------
Mocks replaces real environment parts. Every Mock has an access to Queue.
Everytime when the mock obtain a message from tested command it takes expected
message from Queue. Then the mock compares expected and real message. When the
messages match each other then the Mock returns expected result. Otherwise Mock
call fails.

With each Mock comes Call that represent message appropriate for the concrete
Mock.

Config (with RunnerConfig, CibShortcuts, EnvConfig, ...)
--------------------------------------------------------
The tests use the Config for building list of expected calls (messages to
the mocked parts). Config stores list of calls in CallListBuilder.

EnvAssistant
-----------
EnvAssistant provides CallListBuilder to Config. When test requests an
environment (from the EnvAssistant) then the EnvAssistant:
* takes calls from Config and prepares the Queue (of calls)
* creates appropriate mock and provide them the Queue
* patches environment by appropriate mocks
* returns patched environment

When the test is done the EnvAssistant unpatches the environment and do requeired
checks (that whole Queue is consumed, that there was no extra reports, ...)

Example:
========
from unittest import TestCase

from pcs.lib.commands import resource
from pcs_test.tools.command_env import get_env_tools

class ExampleTest(TestCase):
    def test_success(self):
        env_assist, config = get_env_tools(test_case=self)
        (config
            .runner.cib.load()
            .runner.cib.push(
                resources='''
                    <resources>
                        <bundle id="B1">
                            <docker image="pcs:test" />
                        </bundle>
                    </resources>
                '''
            )
        )
        resource.bundle_create(
            self.env_assist.get_env(),
            "B1",
            "docker",
            container_options={"image": "pcs:test"},
            ensure_disabled=disabled,
            wait=False,
        )
"""

from pcs_test.tools.command_env.assistant import EnvAssistant
from pcs_test.tools.command_env.config import Config
from pcs_test.tools.command_env.tools import get_env_tools

__all__ = ["Config", "EnvAssistant", "get_env_tools"]
