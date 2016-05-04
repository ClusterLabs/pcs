from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import shutil
from unittest import TestCase

from pcs.test.tools.assertions import AssertPcsMixin
from pcs.test.tools.misc import (
    get_test_resource as rc,
)
from pcs.test.tools.pcs_runner import PcsRunner

from pcs import quorum as quorum_cmd
from pcs.cli.common.errors import CmdLineInputError


coro_conf = rc("corosync.conf")
coro_qdevice_conf = rc("corosync-3nodes-qdevice.conf")
temp_conf = rc("corosync.conf.tmp")


class TestBase(TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(coro_conf, temp_conf)
        self.pcs_runner = PcsRunner(corosync_conf_file=temp_conf)

    def fixture_conf_qdevice(self):
        shutil.copy(coro_qdevice_conf, temp_conf)


class QuorumConfigTest(TestBase):
    def test_no_device(self):
        self.assert_pcs_success(
            "quorum config",
            "Options:\n"
        )

    def test_with_device(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
Device:
 Model: net
  host: 127.0.0.1
"""
        )


class QuorumUpdateCmdTest(TestBase):
    def test_no_options(self):
        self.assert_pcs_fail(
            "quorum update",
            stdout_start="\nUsage: pcs quorum <command>\n    update "
        )
        return

    def test_invalid_option(self):
        self.assert_pcs_fail(
            "quorum update nonsense=invalid",
            "Error: invalid quorum option 'nonsense', allowed options are: "
                + "auto_tie_breaker or last_man_standing or "
                + "last_man_standing_window or wait_for_all\n"
        )

    def test_invalid_value(self):
        self.assert_pcs_fail(
            "quorum update wait_for_all=invalid",
            "Error: 'invalid' is not a valid value for wait_for_all"
                + ", use 0 or 1\n"
        )

    def test_success(self):
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
"""
        )
        self.assert_pcs_success(
            "quorum update wait_for_all=1"
        )
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
 wait_for_all: 1
"""
        )


class DeviceAddTest(TestBase):
    def test_no_model_keyword(self):
        self.assert_pcs_fail(
            "quorum device add option=value host=127.0.0.1",
            "Error: missing value of 'model' option\n"
        )

    def test_no_model_value(self):
        self.assert_pcs_fail(
            "quorum device add option=value model host=127.0.0.1",
            "Error: missing value of 'model' option\n"
        )

    def test_more_models(self):
        self.assert_pcs_fail(
            "quorum device add model net host=127.0.0.1 model disk",
            "Error: Model can be specified only once\n"
        )

    def test_device_already_set(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_fail(
            "quorum device add model net host=127.0.0.1",
            "Error: quorum device is already defined\n"
        )

    def test_success_model_only(self):
        self.assert_pcs_success(
            "quorum device add model net host=127.0.0.1"
        )
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
Device:
 Model: net
  host: 127.0.0.1
"""
        )

    def test_succes_all_options(self):
        self.assert_pcs_success(
            "quorum device add timeout=12345 model net host=127.0.0.1"
        )
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
Device:
 timeout: 12345
 Model: net
  host: 127.0.0.1
"""
        )

    def test_missing_required_options(self):
        print("TODO implement {0}.{1}.test_missing_required_options".format(
            self.__module__,
            self.__class__.__name__
        ))


class DeviceRemoveTest(TestBase):
    def test_no_device(self):
        self.assert_pcs_fail(
            "quorum device remove",
            "Error: no quorum device is defined in this cluster\n"
        )

    def test_success(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            "quorum device remove"
        )
        self.assert_pcs_success(
            "quorum config",
            "Options:\n"
        )


class DeviceUpdateTest(TestBase):
    def test_no_device(self):
        self.assert_pcs_fail(
            "quorum device update option=new_value model host=127.0.0.2",
            "Error: no quorum device is defined in this cluster\n"
        )

    def test_generic_options_change(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            "quorum device update timeout=12345"
        )
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
Device:
 timeout: 12345
 Model: net
  host: 127.0.0.1
"""
        )

    def test_model_options_change(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            "quorum device update model host=127.0.0.2"
        )
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
Device:
 Model: net
  host: 127.0.0.2
"""
        )

    def test_both_options_change(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            "quorum device update timeout=12345 model host=127.0.0.2 port=1",
        )
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
Device:
 timeout: 12345
 Model: net
  host: 127.0.0.2
  port: 1
"""
        )

    def test_more_models(self):
        self.assert_pcs_fail(
            "quorum device update model host=127.0.0.2 model port=1",
            "Error: Model can be specified only once\n"
        )


class PrepareDeviceOptionsTest(TestCase):
    def test_empty(self):
        self.assertEqual(
            quorum_cmd.prepare_device_options([]),
            (None, {}, {})
        )

    def test_only_generic(self):
        self.assertEqual(
            quorum_cmd.prepare_device_options(["a=A", "b=B"]),
            (None, {}, {"a": "A", "b": "B"})
        )

    def test_all_set(self):
        self.assertEqual(
            quorum_cmd.prepare_device_options([
                "a=A", "b=B", "model", "net", "c=C", "d=D"
            ]),
            ("net", {"c": "C", "d": "D"}, {"a": "A", "b": "B"})
        )

    def test_missing_model_value(self):
        self.assertEqual(
            quorum_cmd.prepare_device_options([
                "a=A", "b=B", "model", "c=C", "d=D"
            ]),
            (None, {"c": "C", "d": "D"}, {"a": "A", "b": "B"})
        )

    def test_no_model_value_nor_opts(self):
        self.assertEqual(
            quorum_cmd.prepare_device_options(["a=A", "b=B", "model"]),
            (None, {}, {"a": "A", "b": "B"})
        )

    def test_model_2times(self):
        self.assertEqual(
            quorum_cmd.prepare_device_options([
                "a=A", "b=B", "model", "model", "c=C", "d=D"
            ]),
            ("model", {"c": "C", "d": "D"}, {"a": "A", "b": "B"})
        )

    def test_model_3times(self):
        self.assertRaises(
            quorum_cmd.ModelSpecifiedMoreThanOnce,
            lambda: quorum_cmd.prepare_device_options([
                "a=A", "b=B", "model", "model", "model", "c=C", "d=D"
            ])
        )

    def test_model_set_twice(self):
        self.assertRaises(
            quorum_cmd.ModelSpecifiedMoreThanOnce,
            lambda: quorum_cmd.prepare_device_options([
                "a=A", "model", "modelA", "c=C", "model", "modelB", "d=D"
            ])
        )

    def test_missing_value(self):
        self.assertEqual(
            quorum_cmd.prepare_device_options([
                "a=A", "b=", "model", "net", "c=", "d=D"
            ]),
            ("net", {"c": "", "d": "D"}, {"a": "A", "b": ""})
        )

    def test_mising_equals(self):
        self.assertRaises(
            CmdLineInputError,
            lambda: quorum_cmd.prepare_device_options([
                "a", "b=B", "model", "net", "c=C", "d=D"
            ])
        )

    def test_mising_option_name(self):
        self.assertRaises(
            CmdLineInputError,
            lambda: quorum_cmd.prepare_device_options([
                "a=A", "b=B", "model", "net", "=C", "d=D"
            ])
        )
