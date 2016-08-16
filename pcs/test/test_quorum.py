from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import shutil
from pcs.test.tools.pcs_unittest import TestCase

from pcs.test.tools.assertions import AssertPcsMixin
from pcs.test.tools.misc import (
    get_test_resource as rc,
)
from pcs.test.tools.pcs_runner import PcsRunner


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


class QuorumUpdateTest(TestBase):
    def test_no_options(self):
        self.assert_pcs_fail(
            "quorum update",
            stdout_start="\nUsage: pcs quorum <command>\n    update "
        )

    def test_invalid_option(self):
        self.assert_pcs_fail(
            "quorum update nonsense=invalid",
            "Error: invalid quorum option 'nonsense', allowed options are: "
                + "auto_tie_breaker, last_man_standing, "
                + "last_man_standing_window, wait_for_all\n"
        )

    def test_invalid_value(self):
        self.assert_pcs_fail(
            "quorum update wait_for_all=invalid",
            "Error: 'invalid' is not a valid wait_for_all value, use 0, 1\n"
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
            stdout_start="\nUsage: pcs quorum <command>\n    device add "
        )

        self.assert_pcs_fail(
            "quorum device add option=value host=127.0.0.1 --force",
            stdout_start="\nUsage: pcs quorum <command>\n    device add "
        )

    def test_no_model_value(self):
        self.assert_pcs_fail(
            "quorum device add option=value model host=127.0.0.1",
            stdout_start="\nUsage: pcs quorum <command>\n    device add "
        )
        self.assert_pcs_fail(
            "quorum device add option=value model host=127.0.0.1 --force",
            stdout_start="\nUsage: pcs quorum <command>\n    device add "
        )

    def test_more_models(self):
        self.assert_pcs_fail(
            "quorum device add model net host=127.0.0.1 model disk",
            stdout_start="\nUsage: pcs quorum <command>\n    device add "
        )
        self.assert_pcs_fail(
            "quorum device add model net host=127.0.0.1 model disk --force",
            stdout_start="\nUsage: pcs quorum <command>\n    device add "
        )

    def test_model_in_options(self):
        self.assert_pcs_fail(
            "quorum device add model=disk model net host=127.0.0.1",
            "Error: Model cannot be specified in generic options\n"
        )
        self.assert_pcs_fail(
            "quorum device add model=disk model net host=127.0.0.1 --force",
            "Error: Model cannot be specified in generic options\n"
        )

    def test_device_already_set(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_fail(
            "quorum device add model net host=127.0.0.1",
            "Error: quorum device is already defined\n"
        )
        self.assert_pcs_fail(
            "quorum device add model net host=127.0.0.1 --force",
            "Error: quorum device is already defined\n"
        )

    def test_success_model_only(self):
        self.assert_pcs_success(
            "quorum device add model net host=127.0.0.1 algorithm=lms"
        )
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
Device:
  Model: net
    algorithm: lms
    host: 127.0.0.1
"""
        )

    def test_succes_generic_and_model_options(self):
        self.assert_pcs_success(
            "quorum device add timeout=12345 model net host=127.0.0.1 algorithm=ffsplit"
        )
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
Device:
  timeout: 12345
  votes: 1
  Model: net
    algorithm: ffsplit
    host: 127.0.0.1
"""
        )

    def test_missing_required_options(self):
        self.assert_pcs_fail(
            "quorum device add model net",
            """\
Error: required option 'algorithm' is missing
Error: required option 'host' is missing
"""
        )
        self.assert_pcs_fail(
            "quorum device add model net --force",
            """\
Error: required option 'algorithm' is missing
Error: required option 'host' is missing
"""
        )

    def test_bad_options(self):
        self.assert_pcs_fail(
            "quorum device add a=b timeout=-1 model net host=127.0.0.1 algorithm=x c=d",
            """\
Error: 'x' is not a valid algorithm value, use ffsplit, lms, use --force to override
Error: invalid quorum device model option 'c', allowed options are: algorithm, connect_timeout, force_ip_version, host, port, tie_breaker, use --force to override
Error: invalid quorum device option 'a', allowed options are: sync_timeout, timeout, use --force to override
Error: '-1' is not a valid timeout value, use positive integer, use --force to override
"""
        )

        self.assert_pcs_success(
            "quorum device add a=b timeout=-1 model net host=127.0.0.1 algorithm=x c=d --force",
            """\
Warning: 'x' is not a valid algorithm value, use ffsplit, lms
Warning: invalid quorum device model option 'c', allowed options are: algorithm, connect_timeout, force_ip_version, host, port, tie_breaker
Warning: invalid quorum device option 'a', allowed options are: sync_timeout, timeout
Warning: '-1' is not a valid timeout value, use positive integer
"""
        )
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
Device:
  a: b
  timeout: -1
  Model: net
    algorithm: x
    c: d
    host: 127.0.0.1
"""
        )

    def test_bad_model(self):
        self.assert_pcs_fail(
            "quorum device add model invalid x=y",
            "Error: 'invalid' is not a valid model value, use net, use --force to override\n"
        )
        self.assert_pcs_success(
            "quorum device add model invalid x=y --force",
            "Warning: 'invalid' is not a valid model value, use net\n"
        )
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
Device:
  Model: invalid
    x: y
"""
        )


class DeviceRemoveTest(TestBase):
    def test_no_device(self):
        self.assert_pcs_fail(
            "quorum device remove",
            "Error: no quorum device is defined in this cluster\n"
        )
        self.assert_pcs_fail(
            "quorum device remove --force",
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

    def test_bad_options(self):
        self.assert_pcs_fail(
            "quorum device remove net",
            stdout_start="\nUsage: pcs quorum <command>\n    device remove\n"
        )
        self.assert_pcs_fail(
            "quorum device remove net --force",
            stdout_start="\nUsage: pcs quorum <command>\n    device remove\n"
        )


class DeviceUpdateTest(TestBase):
    def test_no_device(self):
        self.assert_pcs_fail(
            "quorum device update option=new_value model host=127.0.0.2",
            "Error: no quorum device is defined in this cluster\n"
        )
        self.assert_pcs_fail(
            "quorum device update option=new_value model host=127.0.0.2 --force",
            "Error: no quorum device is defined in this cluster\n"
        )

    def test_generic_options_change(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success("quorum device update timeout=12345")
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
        self.assert_pcs_success("quorum device update model host=127.0.0.2")
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
            "quorum device update timeout=12345 model host=127.0.0.2 port=1"
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
            stdout_start="\nUsage: pcs quorum <command>\n    device update "
        )
        self.assert_pcs_fail(
            "quorum device update model host=127.0.0.2 model port=1 --force",
            stdout_start="\nUsage: pcs quorum <command>\n    device update "
        )

    def test_model_in_options(self):
        self.assert_pcs_fail(
            "quorum device update model=disk",
            "Error: Model cannot be specified in generic options\n"
        )
        self.assert_pcs_fail(
            "quorum device update model=disk --force",
            "Error: Model cannot be specified in generic options\n"
        )

    def test_missing_required_options(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_fail(
            "quorum device update model host=",
            "Error: required option 'host' is missing\n"
        )
        self.assert_pcs_fail(
            "quorum device update model host= --force",
            "Error: required option 'host' is missing\n"
        )

    def test_bad_options(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_fail(
            "quorum device update a=b timeout=-1 model port=x c=d",
            """\
Error: invalid quorum device model option 'c', allowed options are: algorithm, connect_timeout, force_ip_version, host, port, tie_breaker, use --force to override
Error: 'x' is not a valid port value, use 1-65535, use --force to override
Error: invalid quorum device option 'a', allowed options are: sync_timeout, timeout, use --force to override
Error: '-1' is not a valid timeout value, use positive integer, use --force to override
"""
        )
        self.assert_pcs_success(
            "quorum device update a=b timeout=-1 model port=x c=d --force",
            """\
Warning: invalid quorum device model option 'c', allowed options are: algorithm, connect_timeout, force_ip_version, host, port, tie_breaker
Warning: 'x' is not a valid port value, use 1-65535
Warning: invalid quorum device option 'a', allowed options are: sync_timeout, timeout
Warning: '-1' is not a valid timeout value, use positive integer
"""
        )
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
Device:
  a: b
  timeout: -1
  Model: net
    c: d
    host: 127.0.0.1
    port: x
"""
        )
