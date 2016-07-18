from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os
import shutil
from unittest import TestCase

from pcs.test.tools.assertions import AssertPcsMixin, console_report
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.pcs_runner import PcsRunner


EMPTY_CIB = rc("cib-empty.xml")
TEMP_CIB = rc("temp-cib.xml")

BOOTH_CONFIG_FILE = rc("temp-booth.cfg")

def fake_file(command):
    return "{0} --booth-conf={1}".format(command, BOOTH_CONFIG_FILE)

def ensure_booth_config_exists():
    if not os.path.exists(BOOTH_CONFIG_FILE):
        with open(BOOTH_CONFIG_FILE, "w") as config_file:
            config_file.write("")

def ensure_booth_config_not_exists():
    if os.path.exists(BOOTH_CONFIG_FILE):
        os.remove(BOOTH_CONFIG_FILE)

class BoothTest(TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(EMPTY_CIB, TEMP_CIB)
        self.pcs_runner = PcsRunner(TEMP_CIB)

    def assert_pcs_success(self, command, *args, **kwargs):
        return super(BoothTest, self).assert_pcs_success(
            fake_file(command), *args, **kwargs
        )
    def assert_pcs_fail(self, command, *args, **kwargs):
        return super(BoothTest, self).assert_pcs_fail(
            fake_file(command), *args, **kwargs
        )

class SetupTest(BoothTest):
    def test_sucess_setup_booth_config(self):
        ensure_booth_config_not_exists()
        self.assert_pcs_success(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3"
        )
        self.assert_pcs_success(
            "booth config",
            stdout_full=console_report(
                "site = 1.1.1.1",
                "site = 2.2.2.2",
                "arbitrator = 3.3.3.3",
            )
        )

    def test_fail_when_config_exists_already(self):
        ensure_booth_config_exists()
        try:
            self.assert_pcs_fail(
                "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3",
                (
                    "Error: booth config file {0} already exists, use --force"
                    " to override\n"
                ).format(BOOTH_CONFIG_FILE)
            )
        finally:
            if os.path.exists(BOOTH_CONFIG_FILE):
                os.remove(BOOTH_CONFIG_FILE)

    def test_warn_when_config_file_exists_already_but_is_forced(self):
        ensure_booth_config_exists()
        self.assert_pcs_success(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3 --force",
            stdout_full="Warning: booth config file {0} already exists\n"
            .format(BOOTH_CONFIG_FILE)
        )
        ensure_booth_config_not_exists()


    def test_fail_on_multiple_reasons(self):
        self.assert_pcs_fail(
            "booth setup sites 1.1.1.1 arbitrators 1.1.1.1 2.2.2.2 3.3.3.3",
            console_report(
                "Error: lack of sites for booth configuration (need 2 at least)"
                    ": sites 1.1.1.1"
                ,
                "Error: odd number of participants (4)",
                "Error: duplicate address for booth configuration: 1.1.1.1",
            )
        )

class ConfigTest(BoothTest):
    def test_fail_when_config_file_do_not_exists(self):
        ensure_booth_config_not_exists()
        self.assert_pcs_fail(
            "booth config",
            "Error: Booth config file '{0}' does no exist\n".format(
                BOOTH_CONFIG_FILE
            )
        )
