from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.command_env.assistant import EnvAssistant
from pcs.test.tools.command_env.config_runner_cib import CIB_FILENAME
from pcs.test.tools.command_env.config_runner_pcmk import (
    DEFAULT_WAIT_TIMEOUT,
    DEFAULT_WAIT_ERROR_RETURNCODE,
)


def get_env_tools(
    test_case,
    base_cib_filename=CIB_FILENAME,
    default_wait_timeout=DEFAULT_WAIT_TIMEOUT,
    default_wait_error_returncode=DEFAULT_WAIT_ERROR_RETURNCODE,
):
    """
    Shortcut for preparing EnvAssistant and Config

    TestCase test_case -- corresponding test_case is used to registering cleanup
        method - to assert that everything is finished
    """

    env_assistant = EnvAssistant(test_case=test_case)

    runner = env_assistant.config.runner
    runner.cib.cib_filename = base_cib_filename
    runner.pcmk.default_wait_timeout = default_wait_timeout
    runner.pcmk.default_wait_error_returncode = default_wait_error_returncode

    return env_assistant, env_assistant.config
