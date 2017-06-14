from __future__ import (
    absolute_import,
    division,
    print_function,
)

import logging

from pcs.lib.env import LibraryEnvironment
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.command_env.config import Config
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.integration_lib import Runner
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.pcs_unittest import mock


class EnvPatcher(object):
    def __init__(self, runner):
        self.patchers = {
            "cmd_runner": mock.patch.object(
                LibraryEnvironment,
                "cmd_runner",
                lambda env: runner
            ),
            "get_corosync_conf_data": mock.patch.object(
                LibraryEnvironment,
                "get_corosync_conf_data",
                lambda env: open(rc("corosync.conf")).read()
            )
        }

    def patch(self):
        for key in self.patchers:
            self.patchers[key].start()

    def unpatch(self):
        for key in self.patchers:
            self.patchers[key].stop()

class EnvAssistant(object):
    def __init__(self, config=None, test_case=None):
        """
        TestCase test_case -- cleanup callback is registered to test_case if is
            provided
        """
        self.__runner = Runner()
        self.__config = config if config else Config()
        self.__patcher = EnvPatcher(self.__runner)
        self.__reports_asserted = False
        self.__extra_reports = []

        self.__env = LibraryEnvironment(
            mock.MagicMock(logging.Logger),
            MockLibraryReportProcessor()
        )

        self.__patcher.patch()

        if test_case:
            test_case.addCleanup(self.cleanup)

    @property
    def config(self):
        return self.__config

    def cleanup(self):
        if not self.__reports_asserted:
            self.__env.report_processor.assert_reports(
                self.__extra_reports,
                hint="EnvAssistant.cleanup - is param 'expected_in_processor'"
                " in the method 'assert_raise_library_error' set correctly?"
            )

        self.__runner.assert_everything_launched()
        self.__patcher.unpatch()

    def get_env(self):
        self.__runner.set_runs(self.__config.runner_calls)
        return self.__env

    def assert_reports(self, reports):
        self.__reports_asserted = True
        self.__env.report_processor.assert_reports(
            reports + self.__extra_reports
        )

    def assert_raise_library_error(
        self, command, reports, expected_in_processor=True
    ):
        if not isinstance(reports, list):
            raise self.__list_of_reports_expected(reports)

        assert_raise_library_error(command, *reports)
        if expected_in_processor:
            self.__extra_reports = reports

    def __list_of_reports_expected(self, reports):
        return AssertionError(
            "{0}.{1} expects 'list' as reports parameter, '{2}' was given"
            .format(
                self.__class__.__name__,
                "assert_raise",
                type(reports).__name__
            )
        )
