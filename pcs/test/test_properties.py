import os,sys
import shutil
import unittest
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir) 
import utils
from pcs_test_functions import pcs,ac

empty_cib = "empty.xml"
temp_cib = "temp.xml"

class PropertyTest(unittest.TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)

    def testEmpty(self):
        output, returnVal = pcs(temp_cib, "property") 
        assert returnVal == 0, 'Unable to list resources'
        assert output == "Cluster Properties:\n", [output]

    def testDefaults(self):
        output, returnVal = pcs(temp_cib, "property --defaults")
        prop_defaults = output
        assert returnVal == 0, 'Unable to list resources'
        assert output.startswith('Cluster Properties:\n batch-limit')

        output, returnVal = pcs(temp_cib, "property --all")
        assert returnVal == 0, 'Unable to list resources'
        assert output.startswith('Cluster Properties:\n batch-limit')
        ac(output,prop_defaults)

        output, returnVal = pcs(temp_cib, "property set blahblah=blah")
        assert returnVal == 1
        assert output == "Error: unknown cluster property: 'blahblah', (use --force to override)\n",[output]

        output, returnVal = pcs(temp_cib, "property set blahblah=blah --force")
        assert returnVal == 0,output
        assert output == "",output

        output, returnVal = pcs(temp_cib, "property set stonith-enabled=false")
        assert returnVal == 0,output
        assert output == "",output

        output, returnVal = pcs(temp_cib, "property")
        assert returnVal == 0
        assert output == "Cluster Properties:\n blahblah: blah\n stonith-enabled: false\n", [output]

        output, returnVal = pcs(temp_cib, "property --defaults")
        assert returnVal == 0, 'Unable to list resources'
        assert output.startswith('Cluster Properties:\n batch-limit')
        ac(output,prop_defaults)

        output, returnVal = pcs(temp_cib, "property --all")
        assert returnVal == 0, 'Unable to list resources'
        assert "blahblah: blah" in output
        assert "stonith-enabled: false" in output
        assert output.startswith('Cluster Properties:\n batch-limit')

    def testNodeProperties(self):
        utils.usefile = True
        utils.filename = temp_cib
        o,r = utils.run(["cibadmin","-M", '--xml-text', '<nodes><node id="1" uname="rh7-1"><instance_attributes id="nodes-1"/></node><node id="2" uname="rh7-2"><instance_attributes id="nodes-2"/></node></nodes>'])
        ac(o,"")
        assert r == 0

        o,r = pcs("property set --node=rh7-1 IP=192.168.1.1")
        ac(o,"")
        assert r==0

        o,r = pcs("property set --node=rh7-2 IP=192.168.2.2")
        ac(o,"")
        assert r==0

        o,r = pcs("property")
        ac(o,"Cluster Properties:\nNode Attributes:\n rh7-1: IP=192.168.1.1\n rh7-2: IP=192.168.2.2\n")
        assert r==0

        o,r = pcs("property set --node=rh7-2 IP=")
        ac(o,"")
        assert r==0

        o,r = pcs("property")
        ac(o,"Cluster Properties:\nNode Attributes:\n rh7-1: IP=192.168.1.1\n")
        assert r==0

        o,r = pcs("property set --node=rh7-1 IP=192.168.1.1")
        ac(o,"")
        assert r==0

        o,r = pcs("property set --node=rh7-2 IP=192.168.2.2")
        ac(o,"")
        assert r==0

        o,r = pcs("property")
        ac(o,"Cluster Properties:\nNode Attributes:\n rh7-1: IP=192.168.1.1\n rh7-2: IP=192.168.2.2\n")
        assert r==0

        o,r = pcs("property unset --node=rh7-1 IP")
        ac(o,"")
        assert r==0

        o,r = pcs("property")
        ac(o,"Cluster Properties:\nNode Attributes:\n rh7-2: IP=192.168.2.2\n")
        assert r==0

        o,r = pcs("property unset --node=rh7-1 IP")
        ac(o,"Error: attribute: 'IP' doesn't exist for node: 'rh7-1'\n")
        assert r==1

        o,r = pcs("property unset --node=rh7-1 IP --force")
        ac(o,"")
        assert r==0

    def testBadProperties(self):
        o,r = pcs("property set xxxx=zzzz")
        assert r==1
        ac(o,"Error: unknown cluster property: 'xxxx', (use --force to override)\n")

        output, returnVal = pcs("property set 1234=5678 --force")
        ac(output, "Error: invalid property name '1234', '1' is not a valid first character for a property name\n")
        assert returnVal == 1

        o,r = pcs("property unset zzzzz")
        assert r==1
        ac(o,"Error: can't remove property: 'zzzzz' that doesn't exist\n")

        o,r = pcs("property unset zzzz --force")
        assert r==0
        ac(o,"")

if __name__ == "__main__":
    unittest.main()

