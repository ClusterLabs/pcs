import os,sys
import shutil
import unittest
currentdir = os.path.dirname(os.path.abspath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)
import utils
from pcs_test_functions import pcs,ac

empty_cib = os.path.join(currentdir, "empty-withnodes.xml")
temp_cib = os.path.join(currentdir, "temp.xml")

class ClusterTest(unittest.TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)

    def test_node_maintenance(self):
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
"""
        ac(expected_out, output)
        output, returnVal = pcs(temp_cib, "node maintenance rh7-1")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
Node Attributes:
 rh7-1: maintenance=on
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node maintenance rh7-1")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
Node Attributes:
 rh7-1: maintenance=on
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node maintenance --all")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
Node Attributes:
 rh7-1: maintenance=on
 rh7-2: maintenance=on
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node unmaintenance rh7-2 rh7-1")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node maintenance rh7-1 rh7-2")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
Node Attributes:
 rh7-1: maintenance=on
 rh7-2: maintenance=on
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node maintenance nonexistant-node")
        self.assertEqual(returnVal, 1)
        self.assertEqual(
            output,
            "Error: Node 'nonexistant-node' does not appear to exist in configuration\n"
        )
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
Node Attributes:
 rh7-1: maintenance=on
 rh7-2: maintenance=on
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node unmaintenance rh7-1")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
Node Attributes:
 rh7-2: maintenance=on
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node unmaintenance rh7-1")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
Node Attributes:
 rh7-2: maintenance=on
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node unmaintenance --all")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node unmaintenance nonexistant-node")
        self.assertEqual(returnVal, 1)
        self.assertEqual(
            output,
            "Error: Node 'nonexistant-node' does not appear to exist in configuration\n"
        )
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
"""
        ac(expected_out, output)

if __name__ == "__main__":
    unittest.main()
