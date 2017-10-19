from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.pcs_unittest import mock, TestCase

from pcs.cli.common import capabilities


@mock.patch("pcs.cli.common.capabilities.get_pcsd_dir", lambda: rc(""))
class Capabilities(TestCase):
    def test_get_definition(self):
        self.assertEqual(
            capabilities.get_capabilities_definition(),
            [
                {
                    "id": "test.in-pcs",
                    "in-pcs": "1",
                    "in-pcsd": "0",
                    "description": "This capability is available in pcs.",
                },
                {
                    "id": "test.in-pcsd",
                    "in-pcs": "0",
                    "in-pcsd": "1",
                    "description": "This capability is available in pcsd.",
                },
                {
                    "id": "test.both",
                    "in-pcs": "1",
                    "in-pcsd": "1",
                    "description":
                        "This capability is available in both pcs and pcsd.",
                },
                {
                    "id": "test.empty-description",
                    "in-pcs": "1",
                    "in-pcsd": "1",
                    "description": "",
                },
                {
                    "id": "test.no-description",
                    "in-pcs": "1",
                    "in-pcsd": "1",
                    "description": "",
                },
            ]
        )

    def test_get_pcs(self):
        self.assertEqual(
            capabilities.get_pcs_capabilities(),
            [
                {
                    "id": "test.in-pcs",
                    "description": "This capability is available in pcs.",
                },
                {
                    "id": "test.both",
                    "description":
                        "This capability is available in both pcs and pcsd.",
                },
                {
                    "id": "test.empty-description",
                    "description": "",
                },
                {
                    "id": "test.no-description",
                    "description": "",
                },
            ]
        )
