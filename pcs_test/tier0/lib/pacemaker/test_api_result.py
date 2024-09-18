from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs import settings
from pcs.lib.pacemaker import api_result

from pcs_test.tools import fixture_crm_mon
from pcs_test.tools.assertions import assert_xml_equal
from pcs_test.tools.misc import get_test_resource as rc


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class GetApiResultDom(TestCase):
    def test_valid_xml(self):
        # pylint: disable=no-self-use
        xml = """
            <pacemaker-result api-version="2.3" request="command">
                <status code="0" message="OK"/>
            </pacemaker-result>
        """
        result_el = api_result.get_api_result_dom(xml)
        assert_xml_equal(xml, etree.tostring(result_el).decode())

    def test_syntax_error_xml(self):
        xml = "<syntax_error>"
        self.assertRaises(
            etree.XMLSyntaxError, lambda: api_result.get_api_result_dom(xml)
        )

    def test_invalid_xml(self):
        xml = "<pacemaker-result/>"
        self.assertRaises(
            etree.DocumentInvalid, lambda: api_result.get_api_result_dom(xml)
        )


class GetStatusFromApiResult(TestCase):
    # pylint: disable=protected-access
    def test_errors(self):
        self.assertEqual(
            api_result.get_status_from_api_result(
                etree.fromstring(
                    fixture_crm_mon.error_xml(
                        123, "short message", ["error1", "error2"]
                    )
                )
            ),
            api_result.Status(123, "short message", ["error1", "error2"]),
        )

    def test_no_errors(self):
        self.assertEqual(
            api_result.get_status_from_api_result(
                etree.fromstring(
                    fixture_crm_mon.error_xml(123, "short message")
                )
            ),
            api_result.Status(123, "short message", []),
        )
