from __future__ import (
    absolute_import,
    division,
    print_function,
)

import logging

from pcs.lib.env import LibraryEnvironment
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.command_env.calls import Queue as CallQueue
from pcs.test.tools.command_env.config import Config
from pcs.test.tools.command_env.mock_push_cib import(
    get_push_cib,
    is_push_cib_call_in,
)
from pcs.test.tools.command_env.mock_runner import Runner
from pcs.test.tools.command_env.mock_get_local_corosync_conf import(
    get_get_local_corosync_conf
)
from pcs.test.tools.command_env.mock_node_communicator import (
    NodeCommunicator,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
# from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.pcs_unittest import mock


def patch_env(call_queue, config=None):
    #It is mandatory to patch some env objects/methods. It is ok when command
    #does not use this objects/methods and specify no call for it. But it would
    #be a problem when the test succeded because the live call respond correctly
    #by accident. Such test would fails on different machine (with another live
    #environment)

    patchers = {
        "cmd_runner": mock.patch.object(
            LibraryEnvironment,
            "cmd_runner",
            lambda env: Runner(call_queue)
        ),

        "get_local_corosync_conf": mock.patch(
            "pcs.lib.env.get_local_corosync_conf",
            get_get_local_corosync_conf(call_queue)
        ),

        "get_node_communicator": mock.patch.object(
            LibraryEnvironment,
            "get_node_communicator",

            lambda env: NodeCommunicator(call_queue)
        )
    }

    #It is not always desirable to patch the method push_cib. Some tests can
    #patch only the internals (runner...). So push_cib is patched only when it
    #is explicitly configured
    if is_push_cib_call_in(call_queue):
        push_cib = get_push_cib(call_queue)
        patchers["push_cib"] = mock.patch.object(
             LibraryEnvironment,
             "push_cib",
             lambda env, cib, wait=False: push_cib(cib, wait)
        )

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
        self.__call_queue = None
        self.__config = config if config else Config()
        self.__reports_asserted = False
        self.__extra_reports = []

        self.__unpatch = None

        if test_case:
            test_case.addCleanup(self.cleanup)

    @property
    def config(self):
        return self.__config

    def cleanup(self):
        if self.__unpatch:
            self.__unpatch()

        if not self.__reports_asserted:
            self.__assert_environment_created()
            self._env.report_processor.assert_reports(
                self.__extra_reports,
                hint="EnvAssistant.cleanup - is param 'expected_in_processor'"
                " in the method 'assert_raise_library_error' set correctly?"
            )

        if self.__call_queue and self.__call_queue.remaining:
            raise AssertionError(
                "There are remaining expected calls: \n    '{0}'"
                .format("'\n    '".join([
                    repr(call) for call in self.__call_queue.remaining
                ]))
            )

    def get_env(self):
        self.__call_queue = CallQueue(self.__config.calls)
        self.__unpatch = patch_env(self.__call_queue, self.__config)
        #pylint: disable=attribute-defined-outside-init
        self._env =  LibraryEnvironment(
            mock.MagicMock(logging.Logger),
            MockLibraryReportProcessor()
        )
        return self._env

    def assert_reports(self, reports):
        self.__reports_asserted = True
        self.__assert_environment_created()
        self._env.report_processor.assert_reports(
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

    def __assert_environment_created(self):
        if not hasattr(self, "_env"):
            raise AssertionError(
                "LibraryEnvironment was not created in EnvAssitant."
                " Have you been called method get_env?"
            )

    def __list_of_reports_expected(self, reports):
        return AssertionError(
            "{0}.{1} expects 'list' as reports parameter, '{2}' was given"
            .format(
                self.__class__.__name__,
                "assert_raise",
                type(reports).__name__
            )
        )
