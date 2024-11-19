from unittest import TestCase

from lxml import etree

from pcs.lib.booth import cib as cib_commands


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

    def test_success(self):
        self.assertEqual(
            ["T1", "T2", "T3", "T-self-managed"],
            cib_commands.get_ticket_names(self.cib),
        )
