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

        output, returnVal = pcs(temp_cib, "stonith show test2 --all")
        assert returnVal == 0
        assert output == "Resource: test2\n"

        output, returnVal = pcs(temp_cib, "stonith show --all")
        assert returnVal == 0
        assert output == " test1\t(stonith:fence_noxist):\tStopped \n test2\t(stonith:fence_ilo):\tStopped \n"


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

