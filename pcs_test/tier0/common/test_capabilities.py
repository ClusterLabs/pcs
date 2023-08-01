from unittest import (
    TestCase,
    mock,
)

from pcs.common import capabilities

from pcs_test.tools.misc import get_test_resource as rc


@mock.patch("pcs.settings.pcs_capabilities", rc("capabilities.xml"))
class Capabilities(TestCase):
    def test_get_definition(self):
        self.assertEqual(
            capabilities.get_capabilities_definition(),
            [
                capabilities.Capability(
                    code="test.in-pcs",
                    in_pcs=True,
                    in_pcsd=False,
                    description="This capability is available in pcs.",
                ),
                capabilities.Capability(
                    code="test.in-pcsd",
                    in_pcs=False,
                    in_pcsd=True,
                    description="This capability is available in pcsd.",
                ),
                capabilities.Capability(
                    code="test.both",
                    in_pcs=True,
                    in_pcsd=True,
                    description=(
                        "This capability is available in both pcs and pcsd."
                    ),
                ),
                capabilities.Capability(
                    code="test.empty-description",
                    in_pcs=True,
                    in_pcsd=True,
                    description="",
                ),
                capabilities.Capability(
                    code="test.no-description",
                    in_pcs=True,
                    in_pcsd=True,
                    description="",
                ),
            ],
        )

    def test_get_pcs(self):
        self.assertEqual(
            capabilities.get_pcs_capabilities(),
            [
                capabilities.Capability(
                    code="test.in-pcs",
                    in_pcs=True,
                    in_pcsd=False,
                    description="This capability is available in pcs.",
                ),
                capabilities.Capability(
                    code="test.both",
                    in_pcs=True,
                    in_pcsd=True,
                    description=(
                        "This capability is available in both pcs and pcsd."
                    ),
                ),
                capabilities.Capability(
                    code="test.empty-description",
                    in_pcs=True,
                    in_pcsd=True,
                    description="",
                ),
                capabilities.Capability(
                    code="test.no-description",
                    in_pcs=True,
                    in_pcsd=True,
                    description="",
                ),
            ],
        )

    def test_get_pcsd(self):
        self.assertEqual(
            capabilities.get_pcsd_capabilities(),
            [
                capabilities.Capability(
                    code="test.in-pcsd",
                    in_pcs=False,
                    in_pcsd=True,
                    description="This capability is available in pcsd.",
                ),
                capabilities.Capability(
                    code="test.both",
                    in_pcs=True,
                    in_pcsd=True,
                    description=(
                        "This capability is available in both pcs and pcsd."
                    ),
                ),
                capabilities.Capability(
                    code="test.empty-description",
                    in_pcs=True,
                    in_pcsd=True,
                    description="",
                ),
                capabilities.Capability(
                    code="test.no-description",
                    in_pcs=True,
                    in_pcsd=True,
                    description="",
                ),
            ],
        )
