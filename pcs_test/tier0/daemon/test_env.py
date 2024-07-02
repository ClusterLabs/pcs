import os.path
from ssl import OP_NO_SSLv2
from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.daemon import env

from pcs_test.tools.misc import (
    create_setup_patch_mixin,
    skip_unless_webui_installed,
)


def webui_fallback(public_dir):
    return os.path.join(public_dir, env.WEBUI_FALLBACK_FILE)


class Logger:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, error):
        self.errors.append(error)

    def warning(self, warning):
        self.warnings.append(warning)


class Prepare(TestCase, create_setup_patch_mixin(env)):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.path_exists = self.setup_patch("os.path.exists", return_value=True)
        self.logger = Logger()
        self.maxDiff = None

    def assert_environ_produces_modified_pcsd_env(
        self, environ=None, specific_env_values=None, errors=None, warnings=None
    ):
        default_env_values = {
            env.PCSD_PORT: settings.pcsd_default_port,
            env.PCSD_SSL_CIPHERS: settings.default_ssl_ciphers,
            env.PCSD_SSL_OPTIONS: env.str_to_ssl_options(
                settings.default_ssl_options, []
            ),
            env.PCSD_BIND_ADDR: {None},
            env.NOTIFY_SOCKET: None,
            env.PCSD_DEBUG: False,
            env.PCSD_DISABLE_GUI: False,
            env.PCSD_SESSION_LIFETIME: settings.gui_session_lifetime_seconds,
            env.WEBUI_DIR: settings.pcsd_webui_dir,
            env.WEBUI_FALLBACK: webui_fallback(settings.pcsd_public_dir),
            env.PCSD_DEV: False,
            env.PCSD_WORKER_COUNT: settings.pcsd_worker_count,
            env.PCSD_WORKER_RESET_LIMIT: settings.pcsd_worker_reset_limit,
            env.PCSD_MAX_WORKER_COUNT: settings.pcsd_worker_count
            + settings.pcsd_temporary_workers,
            env.PCSD_DEADLOCK_THRESHOLD_TIMEOUT: settings.pcsd_deadlock_threshold_timeout,
            env.PCSD_CHECK_INTERVAL_MS: settings.async_api_scheduler_interval_ms,
            env.PCSD_TASK_ABANDONED_TIMEOUT: settings.task_abandoned_timeout_seconds,
            env.PCSD_TASK_UNRESPONSIVE_TIMEOUT: settings.task_unresponsive_timeout_seconds,
            env.PCSD_TASK_DELETION_TIMEOUT: settings.task_deletion_timeout_seconds,
            "has_errors": False,
        }
        if specific_env_values is None:
            specific_env_values = {}

        # compare as dict because of clearer error report
        self.assertEqual(
            dict(env.prepare_env(environ or {}, self.logger)._asdict()),
            {**default_env_values, **specific_env_values},
        )
        self.assertEqual(self.logger.errors, errors or [])
        self.assertEqual(self.logger.warnings, warnings or [])

    def test_nothing_in_environ(self):
        self.assert_environ_produces_modified_pcsd_env()

    def test_many_valid_environment_changes(self):
        session_lifetime = 10
        environ = {
            env.PCSD_PORT: "1234",
            env.PCSD_SSL_CIPHERS: "DEFAULT:!3DES:@STRENGTH",
            env.PCSD_SSL_OPTIONS: "OP_NO_SSLv2",
            env.PCSD_BIND_ADDR: "abc",
            env.NOTIFY_SOCKET: "xyz",
            env.PCSD_DEBUG: "true",
            env.PCSD_DISABLE_GUI: "true",
            env.PCSD_SESSION_LIFETIME: str(session_lifetime),
            env.PCSD_DEV: "true",
            env.PCSD_WORKER_COUNT: "1",
            env.PCSD_WORKER_RESET_LIMIT: "2",
            env.PCSD_MAX_WORKER_COUNT: "3",
            env.PCSD_DEADLOCK_THRESHOLD_TIMEOUT: "4",
            env.PCSD_CHECK_INTERVAL_MS: "5",
            env.PCSD_TASK_ABANDONED_TIMEOUT: "6",
            env.PCSD_TASK_UNRESPONSIVE_TIMEOUT: "7",
            env.PCSD_TASK_DELETION_TIMEOUT: "8",
        }
        self.assert_environ_produces_modified_pcsd_env(
            environ=environ,
            specific_env_values={
                env.PCSD_PORT: environ[env.PCSD_PORT],
                env.PCSD_SSL_CIPHERS: environ[env.PCSD_SSL_CIPHERS],
                env.PCSD_SSL_OPTIONS: OP_NO_SSLv2,
                env.PCSD_BIND_ADDR: {environ[env.PCSD_BIND_ADDR]},
                env.NOTIFY_SOCKET: environ[env.NOTIFY_SOCKET],
                env.PCSD_DEBUG: True,
                env.PCSD_DISABLE_GUI: True,
                env.PCSD_SESSION_LIFETIME: session_lifetime,
                env.WEBUI_DIR: env.LOCAL_WEBUI_DIR,
                env.WEBUI_FALLBACK: webui_fallback(env.LOCAL_PUBLIC_DIR),
                env.PCSD_DEV: True,
                env.PCSD_WORKER_COUNT: 1,
                env.PCSD_WORKER_RESET_LIMIT: 2,
                env.PCSD_MAX_WORKER_COUNT: 3,
                env.PCSD_DEADLOCK_THRESHOLD_TIMEOUT: 4,
                env.PCSD_CHECK_INTERVAL_MS: 5,
                env.PCSD_TASK_ABANDONED_TIMEOUT: 6,
                env.PCSD_TASK_UNRESPONSIVE_TIMEOUT: 7,
                env.PCSD_TASK_DELETION_TIMEOUT: 8,
            },
        )

    def test_error_on_noninteger_session_lifetime(self):
        environ = {env.PCSD_SESSION_LIFETIME: "invalid"}
        self.assert_environ_produces_modified_pcsd_env(
            environ,
            specific_env_values={**environ, "has_errors": True},
            errors=[
                "Invalid PCSD_SESSION_LIFETIME value 'invalid'"
                " (it must be an integer)"
            ],
        )

    def test_report_invalid_ssl_ciphers(self):
        environ = {env.PCSD_SSL_CIPHERS: "invalid ;@{}+ ciphers"}
        self.assert_environ_produces_modified_pcsd_env(
            environ,
            specific_env_values={**environ, "has_errors": True},
            errors=["Invalid ciphers: '('No cipher can be selected.',)'"],
        )

    def test_report_invalid_ssl_options(self):
        self.assert_environ_produces_modified_pcsd_env(
            environ={env.PCSD_SSL_OPTIONS: "invalid"},
            specific_env_values={env.PCSD_SSL_OPTIONS: 0, "has_errors": True},
            errors=["Ignoring unknown SSL option 'invalid'"],
        )

    @mock.patch.object(env.settings, "default_ssl_options", "invalid")
    def test_report_invalid_ssl_options_warning(self):
        self.assert_environ_produces_modified_pcsd_env(
            specific_env_values={env.PCSD_SSL_OPTIONS: 0},
            warnings=["Ignoring unknown SSL option 'invalid'"],
        )

    def test_empty_bind_addresses(self):
        self.assert_environ_produces_modified_pcsd_env(
            environ={env.PCSD_BIND_ADDR: " "},
            specific_env_values={env.PCSD_BIND_ADDR: {""}},
        )

    def test_no_disable_gui_explicitly(self):
        self.assert_environ_produces_modified_pcsd_env(
            environ={env.PCSD_DISABLE_GUI: "false"},
        )

    def test_debug_explicitly(self):
        self.assert_environ_produces_modified_pcsd_env(
            environ={env.PCSD_DEBUG: "true"},
            specific_env_values={env.PCSD_DEBUG: True},
        )

    def test_no_debug_explicitly(self):
        self.assert_environ_produces_modified_pcsd_env(
            {env.PCSD_DEBUG: "false"}
        )

    @skip_unless_webui_installed()
    def test_errors_on_missing_paths(self):
        self.path_exists.return_value = False
        self.assert_environ_produces_modified_pcsd_env(
            specific_env_values={"has_errors": True},
            errors=[
                f"Webui assets directory '{settings.pcsd_webui_dir}' or"
                + f" falback html '{webui_fallback(settings.pcsd_public_dir)}'"
                + " does not exist",
            ],
        )

    def test_no_errors_on_missing_paths_disabled_gui(self):
        self.path_exists.return_value = False
        self.assert_environ_produces_modified_pcsd_env(
            environ={env.PCSD_DISABLE_GUI: "true"},
            specific_env_values={
                env.PCSD_DISABLE_GUI: True,
                "has_errors": False,
            },
            errors=[],
        )

    def test_invalid_worker_count(self):
        self.assert_environ_produces_modified_pcsd_env(
            environ={env.PCSD_WORKER_COUNT: "0"},
            specific_env_values={
                env.PCSD_WORKER_COUNT: settings.pcsd_worker_count,
                "has_errors": True,
            },
            errors=[
                f"Value '0' for '{env.PCSD_WORKER_COUNT}' is not a positive integer"
            ],
        )

    def test_invalid_worker_reset_limit(self):
        self.assert_environ_produces_modified_pcsd_env(
            environ={env.PCSD_WORKER_RESET_LIMIT: "a"},
            specific_env_values={
                env.PCSD_WORKER_RESET_LIMIT: settings.pcsd_worker_reset_limit,
                "has_errors": True,
            },
            errors=[
                f"Value 'a' for '{env.PCSD_WORKER_RESET_LIMIT}' is not a positive integer"
            ],
        )

    def test_invalid_max_worker_count(self):
        self.assert_environ_produces_modified_pcsd_env(
            environ={env.PCSD_MAX_WORKER_COUNT: "0"},
            specific_env_values={
                env.PCSD_MAX_WORKER_COUNT: settings.pcsd_worker_count
                + settings.pcsd_temporary_workers,
                "has_errors": True,
            },
            errors=[
                f"Value '0' for '{env.PCSD_MAX_WORKER_COUNT}' is not a positive integer"
            ],
        )

    def test_max_worker_count_dependent_on_worker_count(self):
        self.assert_environ_produces_modified_pcsd_env(
            environ={env.PCSD_WORKER_COUNT: "1"},
            specific_env_values={
                env.PCSD_WORKER_COUNT: 1,
                env.PCSD_MAX_WORKER_COUNT: 1 + settings.pcsd_temporary_workers,
            },
        )

    def test_invalid_deadlock_threshold_timeout(self):
        self.assert_environ_produces_modified_pcsd_env(
            environ={env.PCSD_DEADLOCK_THRESHOLD_TIMEOUT: "-1"},
            specific_env_values={
                env.PCSD_DEADLOCK_THRESHOLD_TIMEOUT: settings.pcsd_deadlock_threshold_timeout,
                "has_errors": True,
            },
            errors=[
                f"Value '-1' for '{env.PCSD_DEADLOCK_THRESHOLD_TIMEOUT}' is not a non-negative integer"
            ],
        )

    def test_invalid_check_interval(self):
        self.assert_environ_produces_modified_pcsd_env(
            environ={env.PCSD_CHECK_INTERVAL_MS: "0"},
            specific_env_values={
                env.PCSD_CHECK_INTERVAL_MS: settings.async_api_scheduler_interval_ms,
                "has_errors": True,
            },
            errors=[
                f"Value '0' for '{env.PCSD_CHECK_INTERVAL_MS}' is not a positive integer"
            ],
        )

    def test_invalid_task_abandoned_timeout(self):
        self.assert_environ_produces_modified_pcsd_env(
            environ={env.PCSD_TASK_ABANDONED_TIMEOUT: "0"},
            specific_env_values={
                env.PCSD_TASK_ABANDONED_TIMEOUT: settings.task_abandoned_timeout_seconds,
                "has_errors": True,
            },
            errors=[
                f"Value '0' for '{env.PCSD_TASK_ABANDONED_TIMEOUT}' is not a positive integer"
            ],
        )

    def test_invalid_task_unresponsive_interval(self):
        self.assert_environ_produces_modified_pcsd_env(
            environ={env.PCSD_TASK_UNRESPONSIVE_TIMEOUT: "0"},
            specific_env_values={
                env.PCSD_TASK_UNRESPONSIVE_TIMEOUT: settings.task_unresponsive_timeout_seconds,
                "has_errors": True,
            },
            errors=[
                f"Value '0' for '{env.PCSD_TASK_UNRESPONSIVE_TIMEOUT}' is not a positive integer"
            ],
        )

    def test_invalid_task_deletion_timeout(self):
        self.assert_environ_produces_modified_pcsd_env(
            environ={env.PCSD_TASK_DELETION_TIMEOUT: "-1"},
            specific_env_values={
                env.PCSD_TASK_DELETION_TIMEOUT: settings.task_deletion_timeout_seconds,
                "has_errors": True,
            },
            errors=[
                f"Value '-1' for '{env.PCSD_TASK_DELETION_TIMEOUT}' is not a non-negative integer"
            ],
        )
