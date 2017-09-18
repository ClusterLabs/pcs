from __future__ import (
    absolute_import,
    division,
    print_function,
)

import logging
from functools import partial

from lxml import etree

from pcs.common import report_codes
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import ReportItemSeverity as severity
from pcs.test.tools import fixture
from pcs.test.tools.assertions import assert_xml_equal
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.misc import get_test_resource as rc, create_patcher
from pcs.test.tools.pcs_unittest import TestCase, mock
from pcs.test.tools.xml import etree_to_str


patch_env = create_patcher("pcs.lib.env")
patch_env_object = partial(mock.patch.object, LibraryEnvironment)

def mock_tmpfile(filename):
    mock_file = mock.MagicMock()
    mock_file.name = rc(filename)
    return mock_file

@patch_env_object("push_cib_diff")
@patch_env_object("push_cib_full")
class CibPushProxy(TestCase):
    def setUp(self):
        self.env = LibraryEnvironment(
            mock.MagicMock(logging.Logger),
            MockLibraryReportProcessor()
        )
        get_cib_patcher = patch_env_object(
            "get_cib",
            lambda self: "<cib />"
        )
        self.addCleanup(get_cib_patcher.stop)
        get_cib_patcher.start()

    def test_push_loaded(self, mock_push_full, mock_push_diff):
        self.env.get_cib()
        self.env.push_cib()
        mock_push_full.assert_not_called()
        mock_push_diff.assert_called_once_with(False)

    def test_push_loaded_wait(self, mock_push_full, mock_push_diff):
        self.env.get_cib()
        self.env.push_cib(wait=10)
        mock_push_full.assert_not_called()
        mock_push_diff.assert_called_once_with(10)

    def test_push_custom(self, mock_push_full, mock_push_diff):
        self.env.get_cib()
        self.env.push_cib(custom_cib="<cib />")
        mock_push_full.assert_called_once_with("<cib />", False)
        mock_push_diff.assert_not_called()

    def test_push_custom_wait(self, mock_push_full, mock_push_diff):
        self.env.get_cib()
        self.env.push_cib(custom_cib="<cib />", wait=10)
        mock_push_full.assert_called_once_with("<cib />", 10)
        mock_push_diff.assert_not_called()


class IsCibLive(TestCase):
    def test_is_live_when_no_cib_data_specified(self):
        env_assist, _ = get_env_tools(test_case=self)
        self.assertTrue(env_assist.get_env().is_cib_live)

    def test_is_not_live_when_cib_data_specified(self):
        env_assist, _ = get_env_tools(test_case=self, cib_data="<cib/>")
        self.assertFalse(env_assist.get_env().is_cib_live)

class WaitSupportWithLiveCib(TestCase):
    wait_timeout = 10

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load()

    def test_supports_timeout(self):
        (self.config
            .runner.pcmk.can_wait()
            .runner.cib.push()
            .runner.pcmk.wait(timeout=self.wait_timeout)
        )

        env = self.env_assist.get_env()
        env.get_cib()
        env.push_cib_full(wait=self.wait_timeout)

        self.env_assist.assert_reports([])

    def test_does_not_support_timeout_without_pcmk_support(self):
        self.config.runner.pcmk.can_wait(stdout="cannot wait")

        env = self.env_assist.get_env()
        env.get_cib()
        self.env_assist.assert_raise_library_error(
            lambda: env.push_cib_full(wait=self.wait_timeout),
            [
                fixture.error(report_codes.WAIT_FOR_IDLE_NOT_SUPPORTED),
            ],
            expected_in_processor=False
        )

    def test_raises_on_invalid_value(self):
        self.config.runner.pcmk.can_wait()

        env = self.env_assist.get_env()
        env.get_cib()
        self.env_assist.assert_raise_library_error(
            lambda: env.push_cib_full(wait="abc"),
            [
                fixture.error(
                    report_codes.INVALID_TIMEOUT_VALUE,
                    timeout="abc"
                ),
            ],
            expected_in_processor=False
        )


class WaitSupportWithMockedCib(TestCase):
    def test_does_not_suport_timeout(self):
        env_assist, config = get_env_tools(test_case=self, cib_data="<cib/>")
        config.runner.cib.load()

        env = env_assist.get_env()
        env.get_cib()
        env_assist.assert_raise_library_error(
            lambda: env.push_cib_full(wait=10),
            [
                fixture.error(report_codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER),
            ],
            expected_in_processor=False
        )

class CibPushFull(TestCase):
    custom_cib = "<custom_cib />"
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_push_custom_without_get(self):
        self.config.runner.cib.push_independent(self.custom_cib)
        self.env_assist.get_env().push_cib_full(etree.XML(self.custom_cib))

    def test_push_custom_after_get(self):
        self.config.runner.cib.load()
        env = self.env_assist.get_env()
        env.get_cib()

        with self.assertRaises(AssertionError) as context_manager:
            env.push_cib_full(etree.XML(self.custom_cib))
            self.assertEqual(
                str(context_manager.exception),
                "CIB has been loaded, cannot push custom CIB"
            )

    def test_push_fails(self):
        (self.config
            .runner.cib.load()
            .runner.cib.push(stderr="invalid cib", returncode=1)
        )
        env = self.env_assist.get_env()
        env.get_cib()
        self.env_assist.assert_raise_library_error(
            env.push_cib_full,
            [
                (
                    severity.ERROR,
                    report_codes.CIB_PUSH_ERROR,
                    {
                        "reason": "invalid cib",
                    },
                    None
                )
            ],
            expected_in_processor=False
        )


class CibPushDiff(TestCase):
    def setUp(self):
        tmpfile_patcher = mock.patch("pcs.lib.pacemaker.live.write_tmpfile")
        self.addCleanup(tmpfile_patcher.stop)
        self.mock_write_tmpfile = tmpfile_patcher.start()
        self.tmpfile_old = mock_tmpfile("old.cib")
        self.tmpfile_new = mock_tmpfile("new.cib")
        self.mock_write_tmpfile.side_effect = [
            self.tmpfile_old, self.tmpfile_new
        ]

        self.env_assist, self.config = get_env_tools(test_case=self)

    def config_load_and_push(self, filename="cib-empty.xml"):
        (self.config
            .runner.cib.load(filename=filename)
            .runner.cib.diff(self.tmpfile_old.name, self.tmpfile_new.name)
            .runner.cib.push_diff()
        )

    def push_reports(self, strip_old=False):
        # No test changes the CIB between load and push. The point is to test
        # loading and pushing, not editing the CIB.
        loaded_cib = self.config.calls.get("runner.cib.load").stdout
        return [
            (
                severity.DEBUG,
                report_codes.TMP_FILE_WRITE,
                {
                    "file_path": self.tmpfile_old.name,
                    "content": loaded_cib.strip() if strip_old else loaded_cib,
                },
                None
            ),
            (
                severity.DEBUG,
                report_codes.TMP_FILE_WRITE,
                {
                    "file_path": self.tmpfile_new.name,
                    "content": loaded_cib.strip(),
                },
                None
            ),
        ]

    def assert_tmps_write_reported(self):
        self.env_assist.assert_reports(self.push_reports())


    def assert_raises_cib_error(self, callable_obj, message):
        with self.assertRaises(AssertionError) as context_manager:
            callable_obj()
            self.assertEqual(str(context_manager.exception), message)

    def assert_raises_cib_not_loaded(self, callable_obj):
        self.assert_raises_cib_error(callable_obj,  "CIB has not been loaded")

    def test_tmpfile_fails(self):
        self.config.runner.cib.load()
        self.mock_write_tmpfile.side_effect = EnvironmentError("test error")
        env = self.env_assist.get_env()
        env.get_cib()
        self.env_assist.assert_raise_library_error(
            env.push_cib_diff,
            [
                (
                    severity.ERROR,
                    report_codes.CIB_SAVE_TMP_ERROR,
                    {
                        "reason": "test error",
                    },
                    None
                )
            ],
            expected_in_processor=False
        )

    def test_diff_fails(self):
        (self.config
            .runner.cib.load()
            .runner.cib.diff(
                self.tmpfile_old.name,
                self.tmpfile_new.name,
                stderr="invalid cib",
                returncode=1
            )
        )
        env = self.env_assist.get_env()
        env.get_cib()
        self.env_assist.assert_raise_library_error(
            env.push_cib_diff,
            [
                (
                    severity.ERROR,
                    report_codes.CIB_DIFF_ERROR,
                    {
                        "reason": "invalid cib",
                    },
                    None
                )
            ],
            expected_in_processor=False
        )
        self.assert_tmps_write_reported()

    def test_push_fails(self):
        (self.config
            .runner.cib.load()
            .runner.cib.diff(self.tmpfile_old.name, self.tmpfile_new.name)
            .runner.cib.push_diff(stderr="invalid cib", returncode=1)
        )
        env = self.env_assist.get_env()
        env.get_cib()
        self.env_assist.assert_raise_library_error(
            env.push_cib_diff,
            [
                (
                    severity.ERROR,
                    report_codes.CIB_PUSH_ERROR,
                    {
                        "reason": "invalid cib",
                    },
                    None
                )
            ],
            expected_in_processor=False
        )
        self.assert_tmps_write_reported()

    def test_get_and_push(self):
        self.config_load_and_push()

        env = self.env_assist.get_env()

        env.get_cib()
        env.push_cib_diff()
        self.assert_tmps_write_reported()

    def test_get_and_push_cib_version_upgrade_needed(self):
        (self.config
            .runner.cib.load(name="load_cib_old")
            .runner.cib.upgrade()
        )
        self.config_load_and_push(filename="cib-empty-2.8.xml")
        env = self.env_assist.get_env()
        env.get_cib((2, 8, 0))
        env.push_cib_diff()

        self.env_assist.assert_reports(
            [fixture.info(report_codes.CIB_UPGRADE_SUCCESSFUL)]
            +
            self.push_reports(strip_old=True)
        )

    def test_get_and_push_cib_version_upgrade_not_needed(self):
        self.config_load_and_push(filename="cib-empty-2.6.xml")

        env = self.env_assist.get_env()

        env.get_cib((2, 5, 0))
        env.push_cib_diff()
        self.assert_tmps_write_reported()


    def test_get_and_property(self):
        self.config.runner.cib.load()
        env = self.env_assist.get_env()
        self.assertEqual(env.get_cib(), env.cib)

    def test_property_without_get(self):
        env = self.env_assist.get_env()
        # need to use lambda because env.cib is a property
        self.assert_raises_cib_not_loaded(lambda: env.cib)

    def test_double_get(self):
        self.config.runner.cib.load()
        env = self.env_assist.get_env()
        env.get_cib()
        self.assert_raises_cib_error(env.get_cib, "CIB has already been loaded")

    def test_push_without_get(self):
        env = self.env_assist.get_env()
        self.assert_raises_cib_not_loaded(env.push_cib_diff)

    def test_can_get_after_push(self):
        self.config_load_and_push()
        self.config.runner.cib.load(name="load_cib_2")

        env = self.env_assist.get_env()
        env.get_cib()
        env.push_cib_diff()
        # need to use lambda because env.cib is a property
        self.assert_raises_cib_not_loaded(lambda: env.cib)
        env.get_cib()

        self.assert_tmps_write_reported()


class GetCib(TestCase):
    def test_raise_library_error_when_cibadmin_failed(self):
        stderr = "cibadmin: Connection to local file failed..."
        env_assist, config = get_env_tools(
            test_case=self,
            #Value of cib_data is unimportant here. This content is only put
            #into tempfile when the runner is not mocked. And content is then
            #loaded from tempfile by `cibadmin --local --query`. In tests is
            #runner mocked so the value of cib_data is not used in the fact.
            cib_data="whatever",
        )
        config.runner.cib.load(returncode=203, stderr=stderr)

        env_assist.assert_raise_library_error(
            env_assist.get_env().get_cib,
            [
                fixture.error(report_codes.CIB_LOAD_ERROR, reason=stderr)
            ],
            expected_in_processor=False
        )

    def test_returns_cib_from_cib_data(self):
        env_assist, config = get_env_tools(
            test_case=self,
            #Value of cib_data is unimportant here. See details in sibling test.
            cib_data="whatever",
        )
        cib_filename = "cib-empty.xml"
        config.runner.cib.load(filename=cib_filename)
        assert_xml_equal(
            etree_to_str(env_assist.get_env().get_cib()),
            open(rc(cib_filename)).read()
        )
