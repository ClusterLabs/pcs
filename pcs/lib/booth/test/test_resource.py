from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

from lxml import etree

import pcs.lib.booth.resource as booth_resource
from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.pcs_mock import mock


class CreateResourceIdTest(TestCase):
    @mock.patch("pcs.lib.booth.resource.find_unique_id")
    def test_return_new_uinq_id(self, mock_find_unique_id):
        mock_find_unique_id.side_effect = lambda cib, id: "{0}-n".format(id)
        self.assertEqual(
            "booth-some-name-ip-n",
            booth_resource.create_resource_id("cib", "some-name", "ip")
        )

class ValidateNoBoothResourceUsingConfigTest(TestCase):
    def test_raises_when_config_already_used(self):
        cib = etree.fromstring('''
            <cib>
                <primitive type="booth-site">
                    <instance_attributes>
                        <nvpair name="config" value="/PATH/TO/CONF"/>
                    </instance_attributes>
                </primitive>
            </cib>
        ''')
        assert_raise_library_error(
            lambda: booth_resource.validate_no_booth_resource_using_config(
                cib,
                "/PATH/TO/CONF"
            ),
            (
                severities.ERROR,
                report_codes.BOOTH_ALREADY_CREATED,
                {
                    'config_file_path': '/PATH/TO/CONF',
                }
            ),
        )

    def test_not_raises_when_not_used(self):
        cib = etree.fromstring('''
            <cib>
                <primitive type="booth-site">
                    <instance_attributes>
                        <nvpair name="config" value="/ANOTHER/PATH/TO/CONF"/>
                    </instance_attributes>
                </primitive>
            </cib>
        ''')
        booth_resource.validate_no_booth_resource_using_config(
            cib,
            "/PATH/TO/CONF"
        )
