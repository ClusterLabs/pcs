import os,sys
import shutil
import unittest
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir) 
import utils

pcs_location = "../pcs.py"
empty_cib = "empty.xml"
temp_cib = "temp.xml"

class ConstraintTest(unittest.TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.setupClusterA(temp_cib)

    # Setups up a cluster with Resources, groups, master/slave resource and clones
    def setupClusterA(self,temp_cib):
        line = "resource create D1 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D2 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D3 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D4 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D5 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D6 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D7 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D8 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D9 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D0 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource group add G1 D0"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource group add G2 D1 D2"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource clone D3"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource master Master D4"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

    def testEmptyConstraints(self):
        output, returnVal = pcs(temp_cib, "constraint")
        assert returnVal == 0 and output == "Location Constraints:\nOrdering Constraints:\nColocation Constraints:\n", output

    def testLocationConstraints(self):
        output, returnVal = pcs(temp_cib, "constraint location D5 prefers node1")
        assert returnVal == 0 and output == "", output
        
        output, returnVal = pcs(temp_cib, "constraint location D5 avoids node1")
        assert returnVal == 0 and output == "", output
        
        output, returnVal = pcs(temp_cib, "constraint location D5 prefers node1")
        assert returnVal == 0 and output == "", output
        
        output, returnVal = pcs(temp_cib, "constraint location D5 avoids node2")
        assert returnVal == 0 and output == "", output

        output, returnVal = pcs(temp_cib, "constraint location add location-D5-node1-INFINITY ")
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs constraint"), output

    def testConstraintRemoval(self):
        output, returnVal = pcs(temp_cib, "constraint location D5 prefers node1")
        assert returnVal == 0 and output == "", output
        
        output, returnVal = pcs(temp_cib, "constraint rm blahblah")
        assert returnVal == 1 and output.startswith("Error: Unable to find constraint - 'blahblah'"), output
        


# Run pcs with -f on specified file
def pcs(testfile, args):
    return utils.run([pcs_location, "-f", testfile] + args.split())

if __name__ == "__main__":
    unittest.main()

