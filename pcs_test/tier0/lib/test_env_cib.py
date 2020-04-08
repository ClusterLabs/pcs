from functools import partial
from unittest import mock, TestCase
from lxml import etree

from pcs_test.tools import fixture
from pcs_test.tools.assertions import  assert_xml_equal
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import (
    get_test_resource as rc,
    create_setup_patch_mixin,
)
from pcs_test.tools.xml import etree_to_str

from pcs.common.reports import codes as report_codes
from pcs.common.tools import Version
from pcs.lib.env import LibraryEnvironment


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
        self.assert_raises_cib_error(
            callable_obj,
            "CIB has not been loaded"
        )

    def assert_raises_cib_already_loaded(self, callable_obj):
        self.assert_raises_cib_error(
            callable_obj,
            "CIB has already been loaded"
        )

    def assert_raises_cib_loaded_cannot_custom(self, callable_obj):
        self.assert_raises_cib_error(
            callable_obj,
            "CIB has been loaded, cannot push custom CIB"
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
        (self.config
            .runner.cib.load(name="load_cib_old", filename="cib-empty-2.6.xml")
            .runner.cib.upgrade()
            .runner.cib.load(filename="cib-empty-2.8.xml")
        )
        env = self.env_assist.get_env()
        env.get_cib(Version(2, 8, 0))

        self.env_assist.assert_reports(
            [fixture.info(report_codes.CIB_UPGRADE_SUCCESSFUL)]
        )

    def test_get_and_push_cib_version_upgrade_not_needed(self):
        self.config.runner.cib.load(filename="cib-empty-2.6.xml")
        env = self.env_assist.get_env()
        env.get_cib(Version(2, 5, 0))


class GetCib(TestCase, ManageCibAssertionMixin):
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
        with open(rc(cib_filename)) as cib_file:
            assert_xml_equal(
                etree_to_str(self.env_assist.get_env().get_cib()),
                cib_file.read()
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
    # pylint: disable=too-many-public-methods
    wait_timeout = 10
    def setUp(self):
        tmpfile_patcher = mock.patch("pcs.lib.pacemaker.live.write_tmpfile")
        self.addCleanup(tmpfile_patcher.stop)
        self.mock_write_tmpfile = tmpfile_patcher.start()
        self.tmpfile_old = mock_tmpfile("old.cib")
        self.tmpfile_new = mock_tmpfile("new.cib")
        self.mock_write_tmpfile.side_effect = [
            self.tmpfile_old, self.tmpfile_new
        ]
        self.cib_can_diff = "cib-empty-2.0.xml"
        self.cib_cannot_diff = "cib-empty-1.2.xml"
        self.env_assist, self.config = get_env_tools(test_case=self)

    def config_load_and_push_diff(self):
        (self.config
            .runner.cib.load(filename=self.cib_can_diff)
            .runner.cib.diff(self.tmpfile_old.name, self.tmpfile_new.name)
            .runner.cib.push_diff()
        )

    def config_load_and_push(self):
        (self.config
            .runner.cib.load(filename=self.cib_cannot_diff)
            .runner.cib.push()
        )

    def push_reports(self, cib_old=None, cib_new=None):
        # No test changes the CIB between load and push. The point is to test
        # loading and pushing, not editing the CIB.
        loaded_cib = self.config.calls.get("runner.cib.load").stdout
        return [
            fixture.debug(
                report_codes.TMP_FILE_WRITE,
                file_path=self.tmpfile_old.name,
                content=(cib_old if cib_old is not None else loaded_cib)
            ),
            fixture.debug(
                report_codes.TMP_FILE_WRITE,
                file_path=self.tmpfile_new.name,
                content=(cib_new if cib_new is not None else loaded_cib).strip()
            ),
        ]

    @staticmethod
    def push_full_forced_reports(version):
        return [
            fixture.warn(
                report_codes.CIB_PUSH_FORCED_FULL_DUE_TO_CRM_FEATURE_SET,
                current_set=version,
                required_set="3.0.9"
            )
        ]

    def test_get_and_push(self):
        self.config_load_and_push_diff()
        env = self.env_assist.get_env()

        env.get_cib()
        env.push_cib()
        self.env_assist.assert_reports(self.push_reports())

    def test_get_and_push_cannot_diff(self):
        self.config_load_and_push()
        env = self.env_assist.get_env()

        env.get_cib()
        env.push_cib()
        self.env_assist.assert_reports(
            self.push_full_forced_reports("3.0.8")
        )

    def test_modified_cib_features_do_not_matter(self):
        self.config_load_and_push_diff()
        env = self.env_assist.get_env()

        cib = env.get_cib()
        cib.set("crm_feature_set", "3.0.8")
        env.push_cib()
        self.env_assist.assert_reports(self.push_reports(
            cib_new=self.config.calls.get("runner.cib.load").stdout.replace(
                "3.0.9",
                "3.0.8"
            )
        ))

    def test_push_no_features_goes_with_full(self):
        (self.config
            .runner.cib.load_content("<cib />", name="runner.cib.load_content")
            .runner.cib.push(load_key="runner.cib.load_content")
        )
        env = self.env_assist.get_env()

        env.get_cib()
        env.push_cib()
        self.env_assist.assert_reports(
            self.push_full_forced_reports("0.0.0")
        )

    def test_can_get_after_push(self):
        self.config_load_and_push_diff()
        self.config.runner.cib.load(
            name="load_cib_2",
            filename=self.cib_can_diff
        )
        env = self.env_assist.get_env()

        env.get_cib()
        env.push_cib()
        # need to use lambda because env.cib is a property
        self.assert_raises_cib_not_loaded(lambda: env.cib)
        env.get_cib()
        self.env_assist.assert_reports(self.push_reports())

    def test_can_get_after_push_cannot_diff(self):
        self.config_load_and_push()
        self.config.runner.cib.load(
            name="load_cib_2",
            filename=self.cib_cannot_diff
         )
        env = self.env_assist.get_env()

        env.get_cib()
        env.push_cib()
        # need to use lambda because env.cib is a property
        self.assert_raises_cib_not_loaded(lambda: env.cib)
        env.get_cib()
        self.env_assist.assert_reports(
            self.push_full_forced_reports("3.0.8")
        )

    def test_not_loaded(self):
        env = self.env_assist.get_env()
        self.assert_raises_cib_not_loaded(env.push_cib)

    def test_tmpfile_fails(self):
        self.config.runner.cib.load(filename=self.cib_can_diff)
        self.mock_write_tmpfile.side_effect = EnvironmentError("test error")
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
            expected_in_processor=False
        )

    def test_diff_is_empty(self):
        (self.config
            .runner.cib.load(filename=self.cib_can_diff)
            .runner.cib.diff(
                self.tmpfile_old.name,
                self.tmpfile_new.name,
                stdout="",
                stderr="",
                returncode=1
            )
        )
        env = self.env_assist.get_env()
        env.get_cib()
        env.push_cib()
        self.env_assist.assert_reports(self.push_reports())

    def test_diff_fails(self):
        (self.config
            .runner.cib.load(filename=self.cib_can_diff)
            .runner.cib.diff(
                self.tmpfile_old.name,
                self.tmpfile_new.name,
                stderr="invalid cib",
                returncode=65
            )
        )
        with open(rc(self.cib_can_diff)) as a_file:
            cib_data = a_file.read()
        env = self.env_assist.get_env()
        env.get_cib()
        self.env_assist.assert_raise_library_error(
            env.push_cib,
            [
                fixture.error(
                    report_codes.CIB_DIFF_ERROR,
                    reason="invalid cib",
                    cib_old=cib_data,
                    cib_new=cib_data.strip(),
                )
            ],
            expected_in_processor=False
        )
        self.env_assist.assert_reports(self.push_reports())

    def test_push_diff_fails(self):
        (self.config
            .runner.cib.load(filename=self.cib_can_diff)
            .runner.cib.diff(self.tmpfile_old.name, self.tmpfile_new.name)
            .runner.cib.push_diff(stderr="invalid cib", returncode=1)
        )
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
            expected_in_processor=False
        )
        self.env_assist.assert_reports(self.push_reports())

    def test_push_fails(self):
        (self.config
            .runner.cib.load(filename=self.cib_cannot_diff)
            .runner.cib.push(stderr="invalid cib", returncode=1)
        )
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
            expected_in_processor=False
        )
        self.env_assist.assert_reports(
            self.push_full_forced_reports("3.0.8")
        )

    def test_wait(self):
        (self.config
            .runner.cib.load(filename=self.cib_can_diff)
            .runner.pcmk.can_wait()
            .runner.cib.diff(self.tmpfile_old.name, self.tmpfile_new.name)
            .runner.cib.push_diff()
            .runner.pcmk.wait(timeout=self.wait_timeout)
        )
        env = self.env_assist.get_env()

        env.get_cib()
        env.push_cib(wait=self.wait_timeout)
        self.env_assist.assert_reports(self.push_reports())

    def test_wait_cannot_diff(self):
        (self.config
            .runner.cib.load(filename=self.cib_cannot_diff)
            .runner.pcmk.can_wait()
            .runner.cib.push()
            .runner.pcmk.wait(timeout=self.wait_timeout)
        )
        env = self.env_assist.get_env()

        env.get_cib()
        env.push_cib(wait=self.wait_timeout)
        self.env_assist.assert_reports(
            self.push_full_forced_reports("3.0.8")
        )

    def test_wait_not_supported(self):
        (self.config
            .runner.cib.load(filename=self.cib_can_diff)
            .runner.pcmk.can_wait(stdout="cannot wait")
        )
        env = self.env_assist.get_env()

        env.get_cib()
        self.env_assist.assert_raise_library_error(
            lambda: env.push_cib(wait=self.wait_timeout),
            [
                fixture.error(report_codes.WAIT_FOR_IDLE_NOT_SUPPORTED),
            ],
            expected_in_processor=False
        )

    def test_wait_raises_on_invalid_value(self):
        (self.config
            .runner.cib.load(filename=self.cib_can_diff)
            .runner.pcmk.can_wait()
        )
        env = self.env_assist.get_env()

        env.get_cib()
        self.env_assist.assert_raise_library_error(
            lambda: env.push_cib(wait="abc"),
            [
                fixture.error(
                    report_codes.INVALID_TIMEOUT_VALUE,
                    timeout="abc"
                ),
            ],
            expected_in_processor=False
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
        (self.config
            .runner.pcmk.can_wait()
            .runner.cib.push_independent(self.custom_cib)
            .runner.pcmk.wait(timeout=self.wait_timeout)
        )
        env = self.env_assist.get_env()

        env.push_cib(
            etree.XML(self.custom_cib),
            wait=self.wait_timeout
        )

    def test_wait_not_supported(self):
        self.config.runner.pcmk.can_wait(stdout="cannot wait")
        env = self.env_assist.get_env()

        self.env_assist.assert_raise_library_error(
            lambda: env.push_cib(
                etree.XML(self.custom_cib),
                wait=self.wait_timeout
            ),
            [
                fixture.error(report_codes.WAIT_FOR_IDLE_NOT_SUPPORTED),
            ],
            expected_in_processor=False
        )

    def test_wait_raises_on_invalid_value(self):
        self.config.runner.pcmk.can_wait()
        env = self.env_assist.get_env()

        self.env_assist.assert_raise_library_error(
            lambda: env.push_cib(etree.XML(self.custom_cib), wait="abc"),
            [
                fixture.error(
                    report_codes.INVALID_TIMEOUT_VALUE,
                    timeout="abc"
                ),
            ],
            expected_in_processor=False
        )


class PushCibMockedWithWait(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_wait_not_suported_for_mocked_cib(self):
        (self.config
            .env.set_cib_data("<cib/>")
            .runner.cib.load()
        )

        env = self.env_assist.get_env()
        env.get_cib()
        self.env_assist.assert_raise_library_error(
            lambda: env.push_cib(wait=10),
            [
                fixture.error(report_codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER),
            ],
            expected_in_processor=False
        )
