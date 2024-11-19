from unittest import TestCase

from lxml import etree

from pcs.lib.booth.cib import get_ticket_names


class GetTicketNames(TestCase):
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

    def test_default(self):
        self.assertEqual(["T1", "T2"], get_ticket_names(self.cib))

    def test_custom_booth_name(self):
        self.assertEqual(["T3"], get_ticket_names(self.cib, "custom_booth"))

    def test_no_tickets(self):
        self.assertEqual([], get_ticket_names(self.cib, "nonexistent_booth"))
