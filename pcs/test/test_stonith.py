import os,sys
import shutil
import unittest
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir) 
import utils

pcs_location = "../pcs.py"
empty_cib = "empty.xml"
temp_cib = "temp.xml"

class StonithTest(unittest.TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)

    def testStonithCreation(self):
        output, returnVal = pcs(temp_cib, "stonith create test1 fence_noxist")
        assert returnVal == 1
        assert output == "Error: Unable to create resource 'stonith:fence_noxist', it is not installed on this system (use --force to override)\n"

        output, returnVal = pcs(temp_cib, "stonith create test1 fence_noxist --force")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "stonith create test2 fence_ilo")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "stonith create test3 fence_ilo bad_argument=test")
        assert returnVal == 1
        assert output == "Error: resource option(s): 'bad_argument', are not recognized for resource type: 'stonith:fence_ilo' (use --force to override)\n",[output]

        output, returnVal = pcs(temp_cib, "stonith create test3 fence_ilo ipaddr=test")
        assert returnVal == 0
        assert output == "",[output]

        output, returnVal = pcs(temp_cib, "stonith update test3 bad_ipaddr=test")
        assert returnVal == 1
        assert output == "Error: resource option(s): 'bad_ipaddr', are not recognized for resource type: 'stonith::fence_ilo' (use --force to override)\n",[output]

        output, returnVal = pcs(temp_cib, "stonith update test3 login=testA")
        assert returnVal == 0
        assert output == "",[output]

        output, returnVal = pcs(temp_cib, "stonith show test2")
        assert returnVal == 0
        assert output == " Resource: test2 (type=fence_ilo class=stonith)\n",[output]

        output, returnVal = pcs(temp_cib, "stonith show --all")
        assert returnVal == 0
        assert output == " Resource: test1 (type=fence_noxist class=stonith)\n Resource: test2 (type=fence_ilo class=stonith)\n Resource: test3 (type=fence_ilo class=stonith)\n  Attributes: ipaddr=test login=testA \n",[output]


    def testStonithFenceConfirm(self):
        output, returnVal = pcs(temp_cib, "stonith fence blah blah")
        assert returnVal == 1
        assert output == "Error: must specify one (and only one) node to fence\n"

        output, returnVal = pcs(temp_cib, "stonith confirm blah blah")
        assert returnVal == 1
        assert output == "Error: must specify one (and only one) node to confirm fenced\n"


# Run pcs with -f on specified file
def pcs(testfile, args):
    return utils.run([pcs_location, "-f", testfile] + args.split())

if __name__ == "__main__":
    unittest.main()

