import os,sys
import shutil
import unittest
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir) 
import utils
from pcs_test_functions import pcs

empty_cib = "empty.xml"
temp_cib = "temp.xml"

class ClusterTest(unittest.TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)

    def testCreation(self):
        output, returnVal = pcs(temp_cib, "cluster") 
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs cluster [commands]...")

        output, returnVal = pcs(temp_cib, "cluster setup --local --corosync_conf=corosync.conf.tmp cname rh7-1 rh7-2")
        assert returnVal == 1
        assert output.startswith("Error: A cluster name (--name <name>) is required to setup a cluster\n")

        output, returnVal = pcs(temp_cib, "cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2")
        assert returnVal == 0
        assert output == ""

if __name__ == "__main__":
    unittest.main()

