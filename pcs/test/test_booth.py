from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os
import shutil

from pcs.test.tools import pcs_unittest as unittest
from pcs.test.tools.assertions import AssertPcsMixin, console_report
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.pcs_runner import PcsRunner


EMPTY_CIB = rc("cib-empty.xml")
TEMP_CIB = rc("temp-cib.xml")

BOOTH_CONFIG_FILE = rc("temp-booth.cfg")
BOOTH_KEY_FILE = rc("temp-booth.key")

BOOTH_RESOURCE_AGENT_INSTALLED = os.path.exists(
    "/usr/lib/ocf/resource.d/pacemaker/booth-site"
)
need_booth_resource_agent = unittest.skipUnless(
    BOOTH_RESOURCE_AGENT_INSTALLED,
    "test requires resource agent ocf:pacemaker:booth-site"
    " which is not istalled"
)


def fake_file(command):
    return "{0} --booth-conf={1} --booth-key={2}".format(
        command,
        BOOTH_CONFIG_FILE,
        BOOTH_KEY_FILE,
    )

def ensure_booth_config_exists():
    if not os.path.exists(BOOTH_CONFIG_FILE):
        with open(BOOTH_CONFIG_FILE, "w") as config_file:
            config_file.write("")

def ensure_booth_config_not_exists():
    if os.path.exists(BOOTH_CONFIG_FILE):
        os.remove(BOOTH_CONFIG_FILE)
    if os.path.exists(BOOTH_KEY_FILE):
        os.remove(BOOTH_KEY_FILE)

class BoothMixin(AssertPcsMixin):
    def setUp(self):
        shutil.copy(EMPTY_CIB, TEMP_CIB)
        self.pcs_runner = PcsRunner(TEMP_CIB)

    def assert_pcs_success(self, command, *args, **kwargs):
        return super(BoothMixin, self).assert_pcs_success(
            fake_file(command), *args, **kwargs
        )

    def assert_pcs_fail(self, command, *args, **kwargs):
        return super(BoothMixin, self).assert_pcs_fail(
            fake_file(command), *args, **kwargs
        )

    def assert_pcs_fail_original(self, *args, **kwargs):
        return super(BoothMixin, self).assert_pcs_fail(*args, **kwargs)

class SetupTest(BoothMixin, unittest.TestCase):
    def test_sucess_setup_booth_config(self):
        ensure_booth_config_not_exists()
        self.assert_pcs_success(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3"
        )
        self.assert_pcs_success(
            "booth config",
            stdout_full=console_report(
                "authfile = {0}".format(BOOTH_KEY_FILE),
                "site = 1.1.1.1",
                "site = 2.2.2.2",
                "arbitrator = 3.3.3.3",
            )
        )
        with open(BOOTH_KEY_FILE) as key_file:
            self.assertEqual(64, len(key_file.read()))


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
            stdout_full=[
                "Warning: booth config file"
                    " {0} already exists".format(BOOTH_CONFIG_FILE)
                ,
                "Warning: booth key file"
                    " {0} already exists".format(BOOTH_KEY_FILE)
                ,
            ]
        )
        ensure_booth_config_not_exists()


    def test_fail_on_multiple_reasons(self):
        self.assert_pcs_fail(
            "booth setup sites 1.1.1.1 arbitrators 1.1.1.1 2.2.2.2 3.3.3.3",
            console_report(
                "Error: lack of sites for booth configuration (need 2 at least)"
                    ": sites 1.1.1.1"
                ,
                "Error: odd number of peers is required (entered 4 peers)",
                "Error: duplicate address for booth configuration: 1.1.1.1",
            )
        )

    def test_refuse_partialy_mocked_environment(self):
        self.assert_pcs_fail_original(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3"
                " --booth-conf=/some/file" #no --booth-key!
            ,
            "Error: With --booth-conf must be specified --booth-key as well\n"
        )
        self.assert_pcs_fail_original(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3"
                " --booth-key=/some/file" #no --booth-conf!
            ,
            "Error: With --booth-key must be specified --booth-conf as well\n"
        )

    def test_show_usage_when_no_site_specified(self):
        self.assert_pcs_fail("booth setup arbitrators 3.3.3.3", stdout_start=[
            "",
            "Usage: pcs booth <command>"
        ])


class DestroyTest(BoothMixin, unittest.TestCase):
    def test_failed_when_using_mocked_booth_env(self):
        self.assert_pcs_fail(
            "booth destroy",
            "Error: This command does not support --booth-conf, --booth-key\n"
        )

    @need_booth_resource_agent
    def test_failed_when_booth_in_cib(self):
        ensure_booth_config_not_exists()
        name = " --name=some-weird-booth-name"
        self.assert_pcs_success(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3" + name
        )
        self.assert_pcs_success("booth create ip 1.1.1.1" + name)
        self.assert_pcs_fail_original(
            "booth destroy" + name,
            #If there is booth@some-weird-booth-name in systemd (enabled or
            #started) the message continue with it because destroy command works
            #always on live environment. "Cleaner" solution takes more effort
            #than what it's worth
            stdout_start=(
                "Error: booth instance 'some-weird-booth-name' is used in"
                " cluster resource\n"
            ),
        )

class BoothTest(unittest.TestCase, BoothMixin):
    def setUp(self):
        shutil.copy(EMPTY_CIB, TEMP_CIB)
        self.pcs_runner = PcsRunner(TEMP_CIB)
        ensure_booth_config_not_exists()
        self.assert_pcs_success(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3"
        )

class AddTicketTest(BoothTest):
    def test_success_add_ticket(self):
        self.assert_pcs_success("booth ticket add TicketA expire=10")
        self.assert_pcs_success("booth config", stdout_full=console_report(
            "authfile = {0}".format(BOOTH_KEY_FILE),
            "site = 1.1.1.1",
            "site = 2.2.2.2",
            "arbitrator = 3.3.3.3",
            'ticket = "TicketA"',
            "  expire = 10",
        ))

    def test_fail_on_bad_ticket_name(self):
        self.assert_pcs_fail(
            "booth ticket add @TicketA",
            "Error: booth ticket name '@TicketA' is not valid, use alphanumeric"
            " chars or dash\n"
        )

    def test_fail_on_duplicit_ticket_name(self):
        self.assert_pcs_success("booth ticket add TicketA")
        self.assert_pcs_fail(
            "booth ticket add TicketA",
            "Error: booth ticket name 'TicketA' already exists in configuration"
            "\n"
        )

    def test_fail_on_invalid_options(self):
        self.assert_pcs_fail(
            "booth ticket add TicketA site=a timeout=", console_report(
                "Error: invalid booth ticket option 'site', allowed options"
                    " are: acquire-after, attr-prereq, before-acquire-handler,"
                    " expire, renewal-freq, retries, timeout, weights"
                ,
                "Error: '' is not a valid timeout value, use no-empty",
            )
        )

    def test_forceable_fail_on_unknown_options(self):
        msg = (
            "invalid booth ticket option 'unknown', allowed options"
            " are: acquire-after, attr-prereq, before-acquire-handler,"
            " expire, renewal-freq, retries, timeout, weights"
        )
        self.assert_pcs_fail(
            "booth ticket add TicketA unknown=a", console_report(
                "Error: "+msg+", use --force to override",
            )
        )
        self.assert_pcs_success(
            "booth ticket add TicketA unknown=a --force",
            "Warning: {0}\n".format(msg),
        )


class RemoveTicketTest(BoothTest):
    def test_success_remove_ticket(self):
        self.assert_pcs_success("booth ticket add TicketA")
        self.assert_pcs_success("booth config", stdout_full=console_report(
            "authfile = {0}".format(BOOTH_KEY_FILE),
            "site = 1.1.1.1",
            "site = 2.2.2.2",
            "arbitrator = 3.3.3.3",
            'ticket = "TicketA"',
        ))
        self.assert_pcs_success("booth ticket remove TicketA")
        self.assert_pcs_success("booth config", stdout_full=console_report(
            "authfile = {0}".format(BOOTH_KEY_FILE),
            "site = 1.1.1.1",
            "site = 2.2.2.2",
            "arbitrator = 3.3.3.3",
        ))

    def test_fail_when_ticket_does_not_exist(self):
        self.assert_pcs_fail(
            "booth ticket remove TicketA",
            "Error: booth ticket name 'TicketA' does not exist\n"
        )

@need_booth_resource_agent
class CreateTest(BoothTest):
    def test_sucessfully_create_booth_resource_group(self):
        self.assert_pcs_success("resource show", "NO resources configured\n")
        self.assert_pcs_success("booth create ip 192.168.122.120")
        self.assert_pcs_success("resource show", [
             " Resource Group: booth-booth-group",
             "     booth-booth-ip	(ocf::heartbeat:IPaddr2):	Stopped",
             "     booth-booth-service	(ocf::pacemaker:booth-site):	Stopped",
        ])
        self.assert_pcs_success("resource show booth-booth-ip", [
             " Resource: booth-booth-ip (class=ocf provider=heartbeat type=IPaddr2)",
             "  Attributes: ip=192.168.122.120",
             "  Operations: start interval=0s timeout=20s (booth-booth-ip-start-interval-0s)",
             "              stop interval=0s timeout=20s (booth-booth-ip-stop-interval-0s)",
             "              monitor interval=10s timeout=20s (booth-booth-ip-monitor-interval-10s)",
        ])

    def test_refuse_create_booth_when_config_is_already_in_use(self):
        self.assert_pcs_success("booth create ip 192.168.122.120")
        self.assert_pcs_fail("booth create ip 192.168.122.121", [
            "Error: booth instance 'booth' is already created as cluster"
                " resource"
        ])

@need_booth_resource_agent
class RemoveTest(BoothTest):
    def test_failed_when_no_booth_configuration_created(self):
        self.assert_pcs_success("resource show", "NO resources configured\n")
        self.assert_pcs_fail("booth remove", [
            "Error: booth instance 'booth' not found in cib"
        ])

    def test_failed_when_multiple_booth_configuration_created(self):
        self.assert_pcs_success("resource show", "NO resources configured\n")
        self.assert_pcs_success("booth create ip 192.168.122.120")
        self.assert_pcs_success(
            "resource create some-id ocf:pacemaker:booth-site"
            " config=/etc/booth/booth.conf"
        )
        self.assert_pcs_success("resource show", [
             " Resource Group: booth-booth-group",
             "     booth-booth-ip	(ocf::heartbeat:IPaddr2):	Stopped",
             "     booth-booth-service	(ocf::pacemaker:booth-site):	Stopped",
             " some-id	(ocf::pacemaker:booth-site):	Stopped",
        ])
        self.assert_pcs_fail("booth remove", [
            "Error: found more than one booth instance 'booth' in cib, use"
            " --force to override"
        ])

    def test_remove_added_booth_configuration(self):
        self.assert_pcs_success("resource show", "NO resources configured\n")
        self.assert_pcs_success("booth create ip 192.168.122.120")
        self.assert_pcs_success("resource show", [
             " Resource Group: booth-booth-group",
             "     booth-booth-ip	(ocf::heartbeat:IPaddr2):	Stopped",
             "     booth-booth-service	(ocf::pacemaker:booth-site):	Stopped",
        ])
        self.assert_pcs_success("booth remove", [
            "Deleting Resource - booth-booth-ip",
            "Deleting Resource (and group) - booth-booth-service",
        ])
        self.assert_pcs_success("resource show", "NO resources configured\n")


    def test_remove_multiple_booth_configuration(self):
        self.assert_pcs_success("resource show", "NO resources configured\n")
        self.assert_pcs_success("booth create ip 192.168.122.120")
        self.assert_pcs_success(
            "resource create some-id ocf:pacemaker:booth-site"
            " config=/etc/booth/booth.conf"
        )
        self.assert_pcs_success("resource show", [
             " Resource Group: booth-booth-group",
             "     booth-booth-ip	(ocf::heartbeat:IPaddr2):	Stopped",
             "     booth-booth-service	(ocf::pacemaker:booth-site):	Stopped",
             " some-id	(ocf::pacemaker:booth-site):	Stopped",
        ])
        self.assert_pcs_success("booth remove --force", [
            "Warning: found more than one booth instance 'booth' in cib",
            "Deleting Resource - booth-booth-ip",
            "Deleting Resource (and group) - booth-booth-service",
            "Deleting Resource - some-id",
        ])


class TicketGrantTest(BoothTest):
    def test_failed_when_implicit_site_but_not_correct_confgiuration_in_cib(
        self
    ):
        self.assert_pcs_success("booth ticket add T1")
        #no resource in cib
        self.assert_pcs_fail("booth ticket grant T1", [
            "Error: cannot determine local site ip, please specify site"
                " parameter"
            ,
        ])

class TicketRevokeTest(BoothTest):
    def test_failed_when_implicit_site_but_not_correct_confgiuration_in_cib(
        self
    ):
        self.assert_pcs_success("booth ticket add T1")
        #no resource in cib
        self.assert_pcs_fail("booth ticket revoke T1", [
            "Error: cannot determine local site ip, please specify site"
                " parameter"
            ,
        ])

class ConfigTest(unittest.TestCase, BoothMixin):
    def setUp(self):
        shutil.copy(EMPTY_CIB, TEMP_CIB)
        self.pcs_runner = PcsRunner(TEMP_CIB)

    def test_fail_when_config_file_do_not_exists(self):
        ensure_booth_config_not_exists()
        self.assert_pcs_fail(
            "booth config",
            "Error: Booth config file '{0}' does not exist\n".format(
                BOOTH_CONFIG_FILE
            )
        )

    def test_too_much_args(self):
        self.assert_pcs_fail(
            "booth config nodename surplus",
            stdout_start="\nUsage: pcs booth <command>\n    config ["
        )

    def test_show_unsupported_values(self):
        ensure_booth_config_not_exists()
        self.assert_pcs_success(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3"
        )
        with open(BOOTH_CONFIG_FILE, "a") as config_file:
            config_file.write("some = nonsense")
        self.assert_pcs_success("booth ticket add TicketA")
        with open(BOOTH_CONFIG_FILE, "a") as config_file:
            config_file.write("another = nonsense")

        self.assert_pcs_success(
            "booth config",
            stdout_full="\n".join((
                "authfile = {0}".format(BOOTH_KEY_FILE),
                "site = 1.1.1.1",
                "site = 2.2.2.2",
                "arbitrator = 3.3.3.3",
                "some = nonsense",
                'ticket = "TicketA"',
                "another = nonsense",
            ))
        )
