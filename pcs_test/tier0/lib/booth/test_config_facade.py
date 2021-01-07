from unittest import TestCase

from pcs.lib.booth.config_facade import ConfigFacade
from pcs.lib.booth.config_parser import ConfigItem

### peers


class GetSitesArbitrators(TestCase):
    def test_no_addrs(self):
        sites = []
        arbitrators = []
        conf = ConfigFacade.create(sites, arbitrators)
        self.assertEqual(sites, conf.get_sites())
        self.assertEqual(arbitrators, conf.get_arbitrators())

    def test_sites(self):
        sites = ["1.1.1.1", "2.2.2.2", "3.3.3.3"]
        arbitrators = []
        conf = ConfigFacade.create(sites, arbitrators)
        self.assertEqual(sites, conf.get_sites())
        self.assertEqual(arbitrators, conf.get_arbitrators())

    def test_arbitrators(self):
        sites = []
        arbitrators = ["4.4.4.4", "5.5.5.5"]
        conf = ConfigFacade.create(sites, arbitrators)
        self.assertEqual(sites, conf.get_sites())
        self.assertEqual(arbitrators, conf.get_arbitrators())

    def test_both(self):
        sites = ["1.1.1.1", "2.2.2.2", "3.3.3.3"]
        arbitrators = ["4.4.4.4", "5.5.5.5"]
        conf = ConfigFacade.create(sites, arbitrators)
        self.assertEqual(sites, conf.get_sites())
        self.assertEqual(arbitrators, conf.get_arbitrators())


### tickets


class AddTicket(TestCase):
    def setUp(self):
        self.conf_struct = [
            ConfigItem("site", "site1", []),
            ConfigItem("site", "site2", []),
            ConfigItem("arbitrator", "arbitrator1", []),
            ConfigItem("ticket", "ticketA", []),
        ]
        self.conf = ConfigFacade(self.conf_struct[:])

    def test_add_no_options(self):
        self.conf.add_ticket("ticketB", {})
        self.assertEqual(
            self.conf.config,
            self.conf_struct
            + [
                ConfigItem("ticket", "ticketB", []),
            ],
        )

    def test_add_with_options(self):
        self.conf.add_ticket("ticketB", {"timeout": "10"})
        self.assertEqual(
            self.conf.config,
            self.conf_struct
            + [
                ConfigItem(
                    "ticket", "ticketB", [ConfigItem("timeout", "10", [])]
                ),
            ],
        )


class HasTicket(TestCase):
    def setUp(self):
        self.conf_struct = [
            ConfigItem("site", "site1", []),
            ConfigItem("site", "site2", []),
            ConfigItem("arbitrator", "arbitrator1", []),
            ConfigItem("ticket", "ticketA", []),
            ConfigItem("ticket", "ticketB", [ConfigItem("timeout", "10", [])]),
        ]
        self.conf = ConfigFacade(self.conf_struct[:])

    def test_ticket_exists(self):
        self.assertTrue(self.conf.has_ticket("ticketA"))
        self.assertTrue(self.conf.has_ticket("ticketB"))

    def test_ticket_missing(self):
        self.assertFalse(self.conf.has_ticket("ticketX"))

    def test_not_a_ticket(self):
        self.assertFalse(self.conf.has_ticket("site1"))
        self.assertFalse(self.conf.has_ticket("arbitrator1"))
        self.assertFalse(self.conf.has_ticket("timeout"))


class RemoveTicket(TestCase):
    def setUp(self):
        self.conf_struct_base = [
            ConfigItem("site", "site1", []),
            ConfigItem("site", "site2", []),
            ConfigItem("arbitrator", "arbitrator1", []),
        ]
        self.conf_struct_ticket_a = [
            ConfigItem("ticket", "ticketA", []),
        ]
        self.conf_struct_ticket_b = [
            ConfigItem("ticket", "ticketB", []),
        ]
        self.conf_struct = (
            self.conf_struct_base
            + self.conf_struct_ticket_a
            + self.conf_struct_ticket_b
        )
        self.conf = ConfigFacade(self.conf_struct[:])

    def test_existing_ticket(self):
        self.conf.remove_ticket("ticketA")
        self.assertEqual(
            self.conf.config, self.conf_struct_base + self.conf_struct_ticket_b
        )

    def test_missing_ticket(self):
        self.conf.remove_ticket("ticketX")
        self.assertEqual(self.conf.config, self.conf_struct)

    def test_not_a_ticket(self):
        self.conf.remove_ticket("site1")
        self.assertEqual(self.conf.config, self.conf_struct)


### authfile


class SetAuthfile(TestCase):
    def setUp(self):
        self.conf_struct_base = [
            ConfigItem("site", "site1", []),
            ConfigItem("site", "site2", []),
            ConfigItem("arbitrator", "arbitrator1", []),
        ]
        self.conf_struct_tickets = [
            ConfigItem("ticket", "ticketA", []),
            ConfigItem("ticket", "ticketB", []),
        ]

    def test_add_authfile(self):
        conf = ConfigFacade(self.conf_struct_base + self.conf_struct_tickets)
        conf.set_authfile("/path/to/auth.file")
        self.assertEqual(
            conf.config,
            (
                [ConfigItem("authfile", "/path/to/auth.file", [])]
                + self.conf_struct_base
                + self.conf_struct_tickets
            ),
        )

    def test_change_authfile(self):
        conf = ConfigFacade(
            self.conf_struct_base
            + [
                ConfigItem("authfile", "/old/path/to/auth1.file", []),
                ConfigItem("authfile", "/old/path/to/auth2.file", []),
            ]
            + self.conf_struct_tickets
        )
        conf.set_authfile("/path/to/auth.file")
        self.assertEqual(
            conf.config,
            (
                [ConfigItem("authfile", "/path/to/auth.file", [])]
                + self.conf_struct_base
                + self.conf_struct_tickets
            ),
        )
