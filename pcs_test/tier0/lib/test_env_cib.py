from functools import partial
from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs.common.reports import codes as report_codes
from pcs.common.tools import Version
from pcs.lib.env import LibraryEnvironment

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_xml_equal
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.custom_mock import (
    TmpFileCall,
    TmpFileMock,
)
from pcs_test.tools.misc import create_setup_patch_mixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.xml import etree_to_str


def mock_tmpfile(filename):
    mock_file = mock.MagicMock()
    mock_file.name = rc(filename)
    return mock_file


SetupPatchMixin = create_setup_patch_mixin(
    partial(mock.patch.object, LibraryEnvironment)
)


class ManageCibAssertionMixin:
    def assert_raises_cib_error(self, callable_obj, message):
        with self.assertRaises(AssertionError) as context_manager:
            callable_obj()
            self.assertEqual(str(context_manager.exception), message)

    def assert_raises_cib_not_loaded(self, callable_obj):
        self.assert_raises_cib_error(callable_obj, "CIB has not been loaded")

    def assert_raises_cib_already_loaded(self, callable_obj):
        self.assert_raises_cib_error(
            callable_obj, "CIB has already been loaded"
        )

    def assert_raises_cib_loaded_cannot_custom(self, callable_obj):
        self.assert_raises_cib_error(
            callable_obj, "CIB has been loaded, cannot push custom CIB"
        )


class IsCibLive(TestCase):
    def test_is_live_when_no_cib_data_specified(self):
        env_assist, _ = get_env_tools(test_case=self)
        self.assertTrue(env_assist.get_env().is_cib_live)

    def test_is_not_live_when_cib_data_specified(self):
        env_assist, config = get_env_tools(test_case=self)
        config.env.set_cib_data("<cib/>")
        self.assertFalse(env_assist.get_env().is_cib_live)


class UpgradeCib(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_get_and_push_cib_version_upgrade_needed(self):
        (
            self.config.runner.cib.load(
                name="load_cib_old", filename="cib-empty-3.1.xml"
            )
            .runner.cib.upgrade()
            .runner.cib.load(filename="cib-empty-3.2.xml")
        )
        env = self.env_assist.get_env()
        env.get_cib(Version(3, 2, 0))

        self.env_assist.assert_reports(
            [fixture.info(report_codes.CIB_UPGRADE_SUCCESSFUL)]
        )

    def test_get_and_push_cib_version_upgrade_not_needed(self):
        self.config.runner.cib.load(filename="cib-empty-3.2.xml")
        env = self.env_assist.get_env()
        env.get_cib(Version(3, 1, 0))

    def test_nice_to_have_lower_than_required(self):
        (
            self.config.runner.cib.load(
                name="load_cib_old", filename="cib-empty-3.1.xml"
            )
            .runner.cib.upgrade()
            .runner.cib.load(filename="cib-empty-3.3.xml")
        )
        env = self.env_assist.get_env()
        env.get_cib(Version(3, 3, 0), Version(3, 2, 0))

        self.env_assist.assert_reports(
            [fixture.info(report_codes.CIB_UPGRADE_SUCCESSFUL)]
        )

    def test_nice_to_have_equal_required(self):
        (
            self.config.runner.cib.load(
                name="load_cib_old", filename="cib-empty-3.1.xml"
            )
            .runner.cib.upgrade()
            .runner.cib.load(filename="cib-empty-3.3.xml")
        )
        env = self.env_assist.get_env()
        env.get_cib(Version(3, 3, 0), Version(3, 3, 0))

        self.env_assist.assert_reports(
            [fixture.info(report_codes.CIB_UPGRADE_SUCCESSFUL)]
        )

    def test_satisfied_nice_to_have_greater_than_required(self):
        (
            self.config.runner.cib.load(
                name="load_cib_old", filename="cib-empty-3.1.xml"
            )
            .runner.cib.upgrade()
            .runner.cib.load(filename="cib-empty-3.3.xml")
        )
        env = self.env_assist.get_env()
        env.get_cib(Version(3, 2, 0), Version(3, 3, 0))

        self.env_assist.assert_reports(
            [fixture.info(report_codes.CIB_UPGRADE_SUCCESSFUL)]
        )

    def test_not_satisfied_nice_to_have_greater_than_required(self):
        (
            self.config.runner.cib.load(
                name="load_cib_old", filename="cib-empty-3.1.xml"
            )
            .runner.cib.upgrade()
            .runner.cib.load(filename="cib-empty-3.3.xml")
        )
        env = self.env_assist.get_env()
        env.get_cib(Version(3, 3, 0), Version(3, 4, 0))

        self.env_assist.assert_reports(
            [fixture.info(report_codes.CIB_UPGRADE_SUCCESSFUL)]
        )


class GetCib(TestCase, ManageCibAssertionMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.tmp_file = "/fake/tmp/file"

    def test_raise_library_error_when_cibadmin_failed(self):
        stderr = "cibadmin: Connection to local file failed..."
        (
            self.config
            # Value of cib_data is unimportant here. This content is only put
            # into tempfile when the runner is not mocked. And content is then
            # loaded from tempfile by `cibadmin --local --query`. Runner is
            # mocked in tests so the value of cib_data is not in the fact used.
            .env.set_cib_data(
                "whatever", cib_tempfile=self.tmp_file
            ).runner.cib.load(
                returncode=203, stderr=stderr, env=dict(CIB_file=self.tmp_file)
            )
        )

        self.env_assist.assert_raise_library_error(
            self.env_assist.get_env().get_cib,
            [fixture.error(report_codes.CIB_LOAD_ERROR, reason=stderr)],
            expected_in_processor=False,
        )

    def test_returns_cib_from_cib_data(self):
        cib_filename = "cib-empty.xml"
        (
            self.config
            # Value of cib_data is unimportant here. See details in sibling test
            .env.set_cib_data(
                "whatever", cib_tempfile=self.tmp_file
            ).runner.cib.load(
                filename=cib_filename, env=dict(CIB_file=self.tmp_file)
            )
        )
        with open(rc(cib_filename)) as cib_file:
            assert_xml_equal(
                etree_to_str(self.env_assist.get_env().get_cib()),
                cib_file.read(),
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
        self.assert_raises_cib_already_loaded(env.get_cib)


class PushLoadedCib(TestCase, ManageCibAssertionMixin):
    wait_timeout = 10

    def setUp(self):
        self.tmpfile_old = "old.cib"
        self.tmpfile_new = "new.cib"
        self.load_cib_name = "load_cib"
        self.tmp_file_mock_obj = TmpFileMock(
            file_content_checker=assert_xml_equal,
        )
        self.addCleanup(self.tmp_file_mock_obj.assert_all_done)
        tmp_file_patcher = mock.patch("pcs.lib.tools.get_tmp_file")
        self.addCleanup(tmp_file_patcher.stop)
        tmp_file_mock = tmp_file_patcher.start()
        tmp_file_mock.side_effect = (
            self.tmp_file_mock_obj.get_mock_side_effect()
        )
        self.env_assist, self.config = get_env_tools(test_case=self)

    def config_load_cib_files(self):
        self.config.runner.cib.load(name=self.load_cib_name)
        loaded_cib = self.config.calls.get(self.load_cib_name).stdout
        self.tmp_file_mock_obj.set_calls(
            [
                TmpFileCall(self.tmpfile_old, orig_content=loaded_cib),
                TmpFileCall(self.tmpfile_new, orig_content=loaded_cib),
            ]
        )

    def config_load_and_push_diff(self):
        self.config_load_cib_files()
        self.config.runner.cib.diff(self.tmpfile_old, self.tmpfile_new)
        self.config.runner.cib.push_diff()

    def push_reports(self, cib_old=None, cib_new=None):
        # No test changes the CIB between load and push. The point is to test
        # loading and pushing, not editing the CIB.
        loaded_cib = self.config.calls.get(self.load_cib_name).stdout
        return [
            fixture.debug(
                report_codes.TMP_FILE_WRITE,
                file_path=self.tmpfile_old,
                content=(cib_old if cib_old is not None else loaded_cib),
            ),
            fixture.debug(
                report_codes.TMP_FILE_WRITE,
                file_path=self.tmpfile_new,
                content=(
                    cib_new if cib_new is not None else loaded_cib
                ).strip(),
            ),
        ]

    def test_get_and_push(self):
        self.config_load_and_push_diff()
        env = self.env_assist.get_env()

        env.get_cib()
        env.push_cib()
        self.env_assist.assert_reports(self.push_reports())

    def test_can_get_after_push(self):
        self.config_load_and_push_diff()
        self.config.runner.cib.load(name="load_cib_2")
        env = self.env_assist.get_env()

        env.get_cib()
        env.push_cib()
        # need to use lambda because env.cib is a property
        self.assert_raises_cib_not_loaded(lambda: env.cib)
        env.get_cib()
        self.env_assist.assert_reports(self.push_reports())

    def test_not_loaded(self):
        env = self.env_assist.get_env()
        self.assert_raises_cib_not_loaded(env.push_cib)

    def test_tmpfile_fails(self):
        self.config.runner.cib.load()
        self.tmp_file_mock_obj.set_calls(
            [
                TmpFileCall(
                    self.tmpfile_old,
                    orig_content=EnvironmentError("test error"),
                ),
            ]
        )
        env = self.env_assist.get_env()

        env.get_cib()
        self.env_assist.assert_raise_library_error(
            env.push_cib,
            [
                fixture.error(
                    report_codes.CIB_SAVE_TMP_ERROR,
                    reason="test error",
                )
            ],
            expected_in_processor=False,
        )

    def test_diff_is_empty(self):
        self.config_load_cib_files()
        self.config.runner.cib.diff(
            self.tmpfile_old,
            self.tmpfile_new,
            stdout="",
            stderr="",
            returncode=1,
        )
        env = self.env_assist.get_env()
        env.get_cib()
        env.push_cib()
        self.env_assist.assert_reports(self.push_reports())

    def test_diff_fails(self):
        self.config_load_cib_files()
        self.config.runner.cib.diff(
            self.tmpfile_old,
            self.tmpfile_new,
            stderr="invalid cib",
            returncode=65,
        )
        loaded_cib = self.config.calls.get(self.load_cib_name).stdout
        env = self.env_assist.get_env()
        env.get_cib()
        self.env_assist.assert_raise_library_error(
            env.push_cib,
            [
                fixture.error(
                    report_codes.CIB_DIFF_ERROR,
                    reason="invalid cib",
                    cib_old=loaded_cib,
                    cib_new=loaded_cib.strip(),
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(self.push_reports())

    def test_push_diff_fails(self):
        self.config_load_cib_files()
        self.config.runner.cib.diff(self.tmpfile_old, self.tmpfile_new)
        self.config.runner.cib.push_diff(stderr="invalid cib", returncode=1)
        env = self.env_assist.get_env()
        env.get_cib()
        self.env_assist.assert_raise_library_error(
            env.push_cib,
            [
                fixture.error(
                    report_codes.CIB_PUSH_ERROR,
                    reason="invalid cib",
                    pushed_cib="",
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(self.push_reports())

    def test_wait(self):
        self.config_load_and_push_diff()
        self.config.runner.pcmk.wait(timeout=self.wait_timeout)
        env = self.env_assist.get_env()

        env.get_cib()
        env.push_cib(wait_timeout=self.wait_timeout)
        self.env_assist.assert_reports(
            self.push_reports()
            + [
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.wait_timeout,
                )
            ]
        )


class PushCustomCib(TestCase, ManageCibAssertionMixin):
    custom_cib = "<custom_cib />"
    wait_timeout = 10

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_push_without_get(self):
        self.config.runner.cib.push_independent(self.custom_cib)
        self.env_assist.get_env().push_cib(etree.XML(self.custom_cib))

    def test_push_after_get(self):
        self.config.runner.cib.load()
        env = self.env_assist.get_env()

        env.get_cib()
        self.assert_raises_cib_loaded_cannot_custom(
            partial(env.push_cib, etree.XML(self.custom_cib))
        )

    def test_wait(self):
        (
            self.config.runner.cib.push_independent(
                self.custom_cib
            ).runner.pcmk.wait(timeout=self.wait_timeout)
        )
        env = self.env_assist.get_env()

        env.push_cib(etree.XML(self.custom_cib), wait_timeout=self.wait_timeout)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.wait_timeout,
                )
            ]
        )


class PushCibMockedWithWait(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_wait_not_supported_for_mocked_cib(self):
        tmp_file = "/fake/tmp/file"
        (
            self.config.env.set_cib_data(
                "<cib/>", cib_tempfile=tmp_file
            ).runner.cib.load(env=dict(CIB_file=tmp_file))
        )

        env = self.env_assist.get_env()
        env.get_cib()
        self.env_assist.assert_raise_library_error(
            lambda: env.push_cib(wait_timeout=10),
            [
                fixture.error(report_codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER),
            ],
            expected_in_processor=False,
        )
