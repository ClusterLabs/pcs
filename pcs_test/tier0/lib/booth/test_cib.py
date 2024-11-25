from unittest import TestCase

from lxml import etree

from pcs.lib.booth import cib as cib_commands


class GetTicketNamesBase:
    def setUp(self):
        self.cib = etree.fromstring(
            """
            <cib>
                <configuration/>
                <status>
                    <tickets>
                        <ticket_state id="T1" granted="false" booth-cfg-name="booth"/>
                        <ticket_state id="T2" granted="false" booth-cfg-name="booth"/>
                        <ticket_state id="T3" granted="false" booth-cfg-name="custom_booth"/>
                        <ticket_state id="T-self-managed" granted="false"/>
                    </tickets>
                </status>
            </cib>
        """
        )


class GetBoothTicketNames(GetTicketNamesBase, TestCase):
    def test_default(self):
        self.assertEqual(
            ["T1", "T2"], cib_commands.get_booth_ticket_names(self.cib)
        )

    def test_custom_booth_name(self):
        self.assertEqual(
            ["T3"],
            cib_commands.get_booth_ticket_names(self.cib, "custom_booth"),
        )

    def test_no_tickets(self):
        self.assertEqual(
            [],
            cib_commands.get_booth_ticket_names(self.cib, "nonexistent_booth"),
        )


class GetTicketNames(GetTicketNamesBase, TestCase):
    def test_success(self):
        self.assertEqual(
            ["T1", "T2", "T3", "T-self-managed"],
            cib_commands.get_ticket_names(self.cib),
        )
