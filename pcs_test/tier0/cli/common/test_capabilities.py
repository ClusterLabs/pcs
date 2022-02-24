from unittest import (
    TestCase,
    mock,
)

from pcs.cli.common import capabilities

from pcs_test.tools.misc import get_test_resource as rc


@mock.patch("pcs.settings.pcsd_exec_location", rc(""))
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
                    "description": (
                        "This capability is available in both pcs and pcsd."
                    ),
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
            ],
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
                    "description": (
                        "This capability is available in both pcs and pcsd."
                    ),
                },
                {
                    "id": "test.empty-description",
                    "description": "",
                },
                {
                    "id": "test.no-description",
                    "description": "",
                },
            ],
        )
