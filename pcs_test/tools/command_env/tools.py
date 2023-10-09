from pcs_test.tools.command_env.assistant import EnvAssistant
from pcs_test.tools.command_env.config_runner_cib import CIB_FILENAME
from pcs_test.tools.command_env.config_runner_pcmk import (
    DEFAULT_WAIT_TIMEOUT,
    WAIT_TIMEOUT_EXPIRED_RETURNCODE,
)


def get_env_tools(
    test_case,
    base_cib_filename=CIB_FILENAME,
    default_wait_timeout=DEFAULT_WAIT_TIMEOUT,
    default_wait_error_returncode=WAIT_TIMEOUT_EXPIRED_RETURNCODE,
    exception_reports_in_processor_by_default=True,
    local_extensions=None,
    booth_env=None,
):
    """
    Shortcut for preparing EnvAssistant and Config

    TestCase test_case -- corresponding test_case is used to registering cleanup
        method - to assert that everything is finished
    dict local_extensions -- key is name of a local extension, value is a class
        that will be used for local extension. So it will be possible to use
        something like this in a config :
            config.my_local_extension.my_local_call_shortcut()
    """
    del booth_env
    env_assistant = EnvAssistant(
        test_case=test_case,
        exception_reports_in_processor_by_default=(
            exception_reports_in_processor_by_default
        ),
    )

    runner = env_assistant.config.runner
    runner.cib.cib_filename = base_cib_filename
    runner.pcmk.default_wait_timeout = default_wait_timeout
    runner.pcmk.default_wait_error_returncode = default_wait_error_returncode

    if local_extensions:
        # pylint: disable=invalid-name
        for name, ExtensionClass in local_extensions.items():
            env_assistant.config.add_extension(
                name,
                ExtensionClass,
            )

    return env_assistant, env_assistant.config
