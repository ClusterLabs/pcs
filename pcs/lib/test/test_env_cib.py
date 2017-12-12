from __future__ import (
    absolute_import,
    division,
    print_function,
)

import logging
from functools import partial

from lxml import etree

from pcs.common import report_codes
from pcs.common.tools import Version
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import ReportItemSeverity as severity
from pcs.test.tools import fixture
from pcs.test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)
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

@patch_env_object("_push_cib_diff")
@patch_env_object("_push_cib_full")
@patch_env("get_cib_xml")
class CibPushProxy(TestCase):
    def setUp(self):
        self.mock_reporter = MockLibraryReportProcessor()
        self.env = LibraryEnvironment(
            mock.MagicMock(logging.Logger),
            self.mock_reporter
        )
        self.cib_can_diff = '<cib crm_feature_set="3.0.9"/>'
        self.cib_cannot_diff = '<cib crm_feature_set="3.0.8"/>'
        self.cib_no_features = '<cib />'

    def test_push_loaded_goes_with_diff(
        self, mock_get_cib, mock_push_full, mock_push_diff
    ):
        mock_get_cib.return_value = self.cib_can_diff
        self.env.get_cib()
        self.env.push_cib()
        mock_push_full.assert_not_called()
        mock_push_diff.assert_called_once_with(wait=False)
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            []
        )

    def test_push_loaded_wait(
        self, mock_get_cib, mock_push_full, mock_push_diff
    ):
        mock_get_cib.return_value = self.cib_can_diff
        self.env.get_cib()
        self.env.push_cib(wait=10)
        mock_push_full.assert_not_called()
        mock_push_diff.assert_called_once_with(wait=10)
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            []
        )

    def test_push_custom_goes_always_full(
        self, mock_get_cib, mock_push_full, mock_push_diff
    ):
        mock_get_cib.return_value = self.cib_can_diff
        self.env.get_cib()
        self.env.push_cib(custom_cib=self.cib_can_diff)
        mock_push_full.assert_called_once_with(self.cib_can_diff, False)
        mock_push_diff.assert_not_called()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            []
        )

    def test_push_custom_wait(
        self, mock_get_cib, mock_push_full, mock_push_diff
    ):
        mock_get_cib.return_value = self.cib_can_diff
        self.env.get_cib()
        self.env.push_cib(custom_cib=self.cib_can_diff, wait=10)
        mock_push_full.assert_called_once_with(self.cib_can_diff, 10)
        mock_push_diff.assert_not_called()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            []
        )

    def test_push_prior_load_goes_with_diff(
        self, mock_get_cib, mock_push_full, mock_push_diff
    ):
        self.env.push_cib()
        mock_push_full.assert_not_called()
        mock_push_diff.assert_called_once_with(wait=False)
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            []
        )

    def test_push_cannot_diff_goes_with_full(
        self, mock_get_cib, mock_push_full, mock_push_diff
    ):
        mock_get_cib.return_value = self.cib_cannot_diff
        self.env.get_cib()
        self.env.push_cib()
        mock_push_full.assert_called_once_with(wait=False)
        mock_push_diff.assert_not_called()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                fixture.warn(
                    report_codes.CIB_PUSH_FORCED_FULL_DUE_TO_CRM_FEATURE_SET,
                    current_set="3.0.8",
                    required_set="3.0.9"
                )
            ]
        )

    def test_push_no_features_goes_with_full(
        self, mock_get_cib, mock_push_full, mock_push_diff
    ):
        mock_get_cib.return_value = self.cib_no_features
        self.env.get_cib()
        self.env.push_cib()
        mock_push_full.assert_called_once_with(wait=False)
        mock_push_diff.assert_not_called()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                fixture.warn(
                    report_codes.CIB_PUSH_FORCED_FULL_DUE_TO_CRM_FEATURE_SET,
                    current_set="0.0.0",
                    required_set="3.0.9"
                )
            ]
        )

    def test_modified_cib_features_do_not_matter(
        self, mock_get_cib, mock_push_full, mock_push_diff
    ):
        mock_get_cib.return_value = self.cib_can_diff
        cib = self.env.get_cib()
        cib.set("crm_feature_set", "3.0.8")
        self.env.push_cib()
        mock_push_full.assert_not_called()
        mock_push_diff.assert_called_once_with(wait=False)
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            []
        )


class IsCibLive(TestCase):
    def test_is_live_when_no_cib_data_specified(self):
        env_assist, _ = get_env_tools(test_case=self)
        self.assertTrue(env_assist.get_env().is_cib_live)

    def test_is_not_live_when_cib_data_specified(self):
        env_assist, config = get_env_tools(test_case=self)
        config.env.set_cib_data("<cib/>")
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
        env._push_cib_full(wait=self.wait_timeout)

        self.env_assist.assert_reports([])

    def test_does_not_support_timeout_without_pcmk_support(self):
        self.config.runner.pcmk.can_wait(stdout="cannot wait")

        env = self.env_assist.get_env()
        env.get_cib()
        self.env_assist.assert_raise_library_error(
            lambda: env._push_cib_full(wait=self.wait_timeout),
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
            lambda: env._push_cib_full(wait="abc"),
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
        env_assist, config = get_env_tools(test_case=self)
        (config
            .env.set_cib_data("<cib/>")
            .runner.cib.load()
        )

        env = env_assist.get_env()
        env.get_cib()
        env_assist.assert_raise_library_error(
            lambda: env._push_cib_full(wait=10),
            [
                fixture.error(report_codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER),
            ],
            expected_in_processor=False
        )


class MangeCibAssertionMixin(object):
    def assert_raises_cib_error(self, callable_obj, message):
        with self.assertRaises(AssertionError) as context_manager:
            callable_obj()
            self.assertEqual(str(context_manager.exception), message)

    def assert_raises_cib_not_loaded(self, callable_obj):
        self.assert_raises_cib_error(callable_obj,  "CIB has not been loaded")



class CibPushFull(TestCase, MangeCibAssertionMixin):
    custom_cib = "<custom_cib />"
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_push_custom_without_get(self):
        self.config.runner.cib.push_independent(self.custom_cib)
        self.env_assist.get_env()._push_cib_full(etree.XML(self.custom_cib))

    def test_push_custom_after_get(self):
        self.config.runner.cib.load()
        env = self.env_assist.get_env()
        env.get_cib()

        with self.assertRaises(AssertionError) as context_manager:
            env._push_cib_full(etree.XML(self.custom_cib))
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
            env._push_cib_full,
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

    def test_get_and_push(self):
        (self.config
            .runner.cib.load()
            .runner.cib.push()
        )
        env = self.env_assist.get_env()
        env.get_cib()
        env._push_cib_full()

    def test_can_get_after_push(self):
        (self.config
            .runner.cib.load()
            .runner.cib.push()
            .runner.cib.load(name="load_cib_2")
         )

        env = self.env_assist.get_env()
        env.get_cib()
        env._push_cib_full()
        # need to use lambda because env.cib is a property
        self.assert_raises_cib_not_loaded(lambda: env.cib)
        env.get_cib()


class CibPushDiff(TestCase, MangeCibAssertionMixin):
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

    def test_tmpfile_fails(self):
        self.config.runner.cib.load()
        self.mock_write_tmpfile.side_effect = EnvironmentError("test error")
        env = self.env_assist.get_env()
        env.get_cib()
        self.env_assist.assert_raise_library_error(
            env._push_cib_diff,
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
            env._push_cib_diff,
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
            env._push_cib_diff,
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
        env._push_cib_diff()
        self.assert_tmps_write_reported()

    def test_can_get_after_push(self):
        self.config_load_and_push()
        self.config.runner.cib.load(name="load_cib_2")

        env = self.env_assist.get_env()
        env.get_cib()
        env._push_cib_diff()
        # need to use lambda because env.cib is a property
        self.assert_raises_cib_not_loaded(lambda: env.cib)
        env.get_cib()
        self.assert_tmps_write_reported()


class UpgradeCib(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_get_and_push_cib_version_upgrade_needed(self):
        (self.config
            .runner.cib.load(name="load_cib_old")
            .runner.cib.upgrade()
            .runner.cib.load(filename="cib-empty-2.8.xml")
        )
        env = self.env_assist.get_env()
        env.get_cib(Version(2, 8, 0))

        self.env_assist.assert_reports(
            [fixture.info(report_codes.CIB_UPGRADE_SUCCESSFUL)]
        )

    def test_get_and_push_cib_version_upgrade_needed_tuple(self):
        (self.config
            .runner.cib.load(name="load_cib_old")
            .runner.cib.upgrade()
            .runner.cib.load(filename="cib-empty-2.8.xml")
        )
        env = self.env_assist.get_env()
        env.get_cib((2, 8, 0))

        self.env_assist.assert_reports(
            [fixture.info(report_codes.CIB_UPGRADE_SUCCESSFUL)]
        )

    def test_get_and_push_cib_version_upgrade_not_needed(self):
        self.config.runner.cib.load(filename="cib-empty-2.6.xml")
        env = self.env_assist.get_env()
        env.get_cib(Version(2, 5, 0))

    def test_get_and_push_cib_version_upgrade_not_needed_tuple(self):
        self.config.runner.cib.load(filename="cib-empty-2.6.xml")
        env = self.env_assist.get_env()
        env.get_cib((2, 5, 0))


class ManageCib(TestCase, MangeCibAssertionMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_raise_library_error_when_cibadmin_failed(self):
        stderr = "cibadmin: Connection to local file failed..."
        (self.config
            #Value of cib_data is unimportant here. This content is only put
            #into tempfile when the runner is not mocked. And content is then
            #loaded from tempfile by `cibadmin --local --query`. Runner is
            #mocked in tests so the value of cib_data is not in the fact used.
            .env.set_cib_data("whatever")
            .runner.cib.load(returncode=203, stderr=stderr)
        )

        self.env_assist.assert_raise_library_error(
            self.env_assist.get_env().get_cib,
            [
                fixture.error(report_codes.CIB_LOAD_ERROR, reason=stderr)
            ],
            expected_in_processor=False
        )

    def test_returns_cib_from_cib_data(self):
        cib_filename = "cib-empty.xml"
        (self.config
            #Value of cib_data is unimportant here. See details in sibling test.
            .env.set_cib_data("whatever")
            .runner.cib.load(filename=cib_filename)
        )
        assert_xml_equal(
            etree_to_str(self.env_assist.get_env().get_cib()),
            open(rc(cib_filename)).read()
        )

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
        self.assert_raises_cib_not_loaded(env._push_cib_diff)
