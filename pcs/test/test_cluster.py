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

# Setup a 2 node cluster and make sure the two node config is set, then add a
# node and make sure that it's unset, then remove a node and make sure it's
# set again
        output, returnVal = pcs(temp_cib, "cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2")
        assert returnVal == 0
        assert output == ""

        with open("corosync.conf.tmp") as f:
            data = f.read()
            assert data == 'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udpu\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n',[data]

        output, returnVal = pcs(temp_cib, "cluster localnode add --corosync_conf=corosync.conf.tmp rh7-3")
        assert returnVal == 0
        assert output == "rh7-3: successfully added!\n",output

        with open("corosync.conf.tmp") as f:
            data = f.read()
            assert data == 'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udpu\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n  node {\n        ring0_addr: rh7-3\n        nodeid: 3\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\n}\n\nlogging {\nto_syslog: yes\n}\n',[data]

        output, returnVal = pcs(temp_cib, "cluster localnode remove --corosync_conf=corosync.conf.tmp rh7-3")
        assert returnVal == 0
        assert output == "rh7-3: successfully removed!\n",output

        with open("corosync.conf.tmp") as f:
            data = f.read()
            assert data == 'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udpu\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n',[data]

        output, returnVal = pcs(temp_cib, "cluster setup --local --corosync_conf=corosync.conf2.tmp --name cname rh7-1 rh7-2 rh7-3")
        assert returnVal == 0
        assert output == ""

        with open("corosync.conf2.tmp") as f:
            data = f.read()
            assert data == 'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udpu\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n  node {\n        ring0_addr: rh7-3\n        nodeid: 3\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\n\n}\n\nlogging {\nto_syslog: yes\n}\n',[data]



if __name__ == "__main__":
    unittest.main()

