from unittest import TestCase

from lxml import etree

from pcs.lib.cib.resource import hierarchy

from pcs_test.tools.assertions import assert_xml_equal
from pcs_test.tools.xml import etree_to_str


def _resource(cib, id_):
    return cib.find(f".//*[@id='{id_}']")


def _resources(cib, *ids):
    return [_resource(cib, id_) for id_ in ids]


class MoveResourcesToGroup(TestCase):
    cib_resources = """
        <resources>
            <group id="G">
                <primitive id="RG1" />
                <primitive id="RG2" />
                <primitive id="RG3" />
            </group>
            <primitive id="R1" />
            <primitive id="R2" />
            <primitive id="R3" />
        </resources>
    """

    def test_no_adjacent(self):
        cib_before = self.cib_resources
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RG3" />
                    <primitive id="R3" />
                    <primitive id="R1" />
                </group>
                <primitive id="R2" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"), _resources(cib, "R3", "R1")
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_after_adjacent(self):
        cib_before = self.cib_resources
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="R3" />
                    <primitive id="R1" />
                    <primitive id="RG3" />
                    <primitive id="RG2" />
                </group>
                <primitive id="R2" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R3", "R1", "RG3"),
            adjacent_resource=_resource(cib, "RG1"),
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_after_adjacent_last(self):
        cib_before = self.cib_resources
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG3" />
                    <primitive id="R3" />
                    <primitive id="R1" />
                    <primitive id="RG2" />
                </group>
                <primitive id="R2" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R3", "R1", "RG2"),
            adjacent_resource=_resource(cib, "RG3"),
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_before_adjacent(self):
        cib_before = self.cib_resources
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="R3" />
                    <primitive id="R1" />
                    <primitive id="RG3" />
                    <primitive id="RG2" />
                </group>
                <primitive id="R2" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R3", "R1", "RG3"),
            adjacent_resource=_resource(cib, "RG2"),
            put_after_adjacent=False,
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_before_adjacent_first(self):
        cib_before = self.cib_resources
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="R3" />
                    <primitive id="R1" />
                    <primitive id="RG3" />
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                </group>
                <primitive id="R2" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R3", "R1", "RG3"),
            adjacent_resource=_resource(cib, "RG1"),
            put_after_adjacent=False,
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_move_from_another_group(self):
        # pylint: disable=no-self-use
        cib_before = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RG3" />
                </group>
                <group id="X">
                    <primitive id="R1" />
                    <primitive id="R2" />
                </group>
                <primitive id="R3" />
            </resources>
        """
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RG3" />
                    <primitive id="R2" />
                </group>
                <group id="X">
                    <primitive id="R1" />
                </group>
                <primitive id="R3" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R2"),
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_move_last_from_group(self):
        # pylint: disable=no-self-use
        cib_before = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RG3" />
                </group>
                <group id="X">
                    <primitive id="R1" />
                </group>
                <primitive id="R3" />
            </resources>
        """
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RG3" />
                    <primitive id="R1" />
                </group>
                <primitive id="R3" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R1"),
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def _assert_move_last_from_cloned_group(self, clone_type):
        # pylint: disable=no-self-use
        cib_before = f"""
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RG3" />
                </group>
                <{clone_type} id="X-{clone_type}">
                    <group id="X">
                        <primitive id="R1" />
                    </group>
                </{clone_type}>
                <primitive id="R3" />
            </resources>
        """
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RG3" />
                    <primitive id="R1" />
                </group>
                <primitive id="R3" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R1"),
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_move_last_from_cloned_group(self):
        self._assert_move_last_from_cloned_group("clone")

    def test_move_last_from_mastered_group(self):
        self._assert_move_last_from_cloned_group("master")
