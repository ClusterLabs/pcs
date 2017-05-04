from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging

import pcs.lib.commands.test.resource.fixture as fixture
from pcs.lib.env import LibraryEnvironment
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.integration_lib import Runner
from pcs.test.tools.pcs_unittest import TestCase, mock

class CommonResourceTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = Runner()
        cls.patcher = mock.patch.object(
            LibraryEnvironment,
            "cmd_runner",
            lambda self: cls.runner
        )
        cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()

    def setUp(self):
        self.env = LibraryEnvironment(
            mock.MagicMock(logging.Logger),
            MockLibraryReportProcessor()
        )
        self.cib_base_file = "cib-empty.xml"


class ResourceWithoutStateTest(CommonResourceTest):
    def assert_command_effect(self, cib_pre, cmd, cib_post, reports=None):
        self.runner.set_runs(
            fixture.calls_cib(
                cib_pre,
                cib_post,
                cib_base_file=self.cib_base_file
            )
        )
        cmd()
        self.env.report_processor.assert_reports(reports if reports else [])
        self.runner.assert_everything_launched()


class ResourceWithStateTest(CommonResourceTest):
    def assert_command_effect(
        self, cib_pre, status, cmd, cib_post, reports=None
    ):
        self.runner.set_runs(
            fixture.calls_cib_and_status(
                cib_pre,
                status,
                cib_post,
                cib_base_file=self.cib_base_file
            )
        )
        cmd()
        self.env.report_processor.assert_reports(reports if reports else [])
        self.runner.assert_everything_launched()
