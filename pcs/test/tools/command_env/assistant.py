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
from pcs.test.tools.integration_lib import Runner, EffectQueue
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.pcs_unittest import mock


def patch_env(effect_queue):
    patchers = {
        "cmd_runner": mock.patch.object(
            LibraryEnvironment,
            "cmd_runner",
            lambda env: Runner(effect_queue)
        ),
        "get_corosync_conf_data": mock.patch.object(
            LibraryEnvironment,
            "get_corosync_conf_data",
            lambda env: open(rc("corosync.conf")).read()
        )
    }
    for key in patchers:
        patchers[key].start()

    def unpatch():
        for key in patchers:
            patchers[key].stop()

    return unpatch

class EnvAssistant(object):
    def __init__(self, config=None, test_case=None):
        """
        TestCase test_case -- cleanup callback is registered to test_case if is
            provided
        """
        self.__effect_queue = None
        self.__config = config if config else Config()
        self.__reports_asserted = False
        self.__extra_reports = []

        self.__env = LibraryEnvironment(
            mock.MagicMock(logging.Logger),
            MockLibraryReportProcessor()
        )

        self.__unpatch = None

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

        if self.__effect_queue and self.__effect_queue.remaining:
            raise AssertionError(
                "There are remaining expected commands: \n    '{0}'"
                .format("'\n    '".join([
                    call.command
                    for call in self.__effect_queue.remaining
                ]))
            )
        if self.__unpatch:
            self.__unpatch()

    def get_env(self):
        self.__effect_queue = EffectQueue(self.__config.runner_calls)
        self.__unpatch = patch_env(self.__effect_queue)
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
