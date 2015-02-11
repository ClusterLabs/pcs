import os,sys
import shutil
import unittest
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir) 
import utils
from pcs_test_functions import pcs,ac,isMinimumPacemakerVersion

empty_cib = "empty-withnodes.xml"
temp_cib = "temp.xml"

class ClusterTest(unittest.TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)

    def testNodeStandby(self):
        output, returnVal = pcs(temp_cib, "cluster standby rh7-1") 
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "cluster standby nonexistant-node") 
        assert returnVal == 1
        assert output == "Error: node 'nonexistant-node' does not appear to exist in configuration\n"

    def testRemoteNode(self):
        o,r = pcs(temp_cib, "resource create D1 Dummy --no-default-ops")
        assert r==0 and o==""

        o,r = pcs(temp_cib, "resource create D2 Dummy --no-default-ops")
        assert r==0 and o==""

        o,r = pcs(temp_cib, "cluster remote-node rh7-2 D1")
        assert r==1 and o.startswith("\nUsage: pcs cluster remote-node")

        o,r = pcs(temp_cib, "cluster remote-node add rh7-2 D1")
        assert r==0 and o==""

        o,r = pcs(temp_cib, "cluster remote-node add rh7-1 D2 remote-port=100 remote-addr=400 remote-connect-timeout=50")
        assert r==0 and o==""

        o,r = pcs(temp_cib, "resource --full")
        assert r==0
        ac(o," Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n  Meta Attrs: remote-node=rh7-2 \n  Operations: monitor interval=60s (D1-monitor-interval-60s)\n Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n  Meta Attrs: remote-node=rh7-1 remote-port=100 remote-addr=400 remote-connect-timeout=50 \n  Operations: monitor interval=60s (D2-monitor-interval-60s)\n")

        o,r = pcs(temp_cib, "cluster remote-node remove")
        assert r==1 and o.startswith("\nUsage: pcs cluster remote-node")

        o,r = pcs(temp_cib, "cluster remote-node remove rh7-2")
        assert r==0 and o==""

        o,r = pcs(temp_cib, "cluster remote-node add rh7-2 NOTARESOURCE")
        assert r==1
        ac(o,"Error: unable to find resource 'NOTARESOURCE'\n")

        o,r = pcs(temp_cib, "cluster remote-node remove rh7-2")
        assert r==1
        ac(o,"Error: unable to remove: cannot find remote-node 'rh7-2'\n")

        o,r = pcs(temp_cib, "resource --full")
        assert r==0
        ac(o," Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (D1-monitor-interval-60s)\n Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n  Meta Attrs: remote-node=rh7-1 remote-port=100 remote-addr=400 remote-connect-timeout=50 \n  Operations: monitor interval=60s (D2-monitor-interval-60s)\n")

        o,r = pcs(temp_cib, "cluster remote-node remove rh7-1")
        assert r==0 and o==""

        o,r = pcs(temp_cib, "resource --full")
        assert r==0
        ac(o," Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (D1-monitor-interval-60s)\n Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (D2-monitor-interval-60s)\n")

    def testCreation(self):
        if utils.is_rhel6():
            return

        output, returnVal = pcs(temp_cib, "cluster") 
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs cluster [commands]...")

        output, returnVal = pcs(temp_cib, "cluster setup --local --corosync_conf=corosync.conf.tmp cname rh7-1 rh7-2")
        assert returnVal == 1
        assert output.startswith("Error: A cluster name (--name <name>) is required to setup a cluster\n")

# Setup a 2 node cluster and make sure the two node config is set, then add a
# node and make sure that it's unset, then remove a node and make sure it's
# set again
        output, returnVal = pcs(temp_cib, "cluster setup --force --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2")
        ac (output,"")
        assert returnVal == 0

        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udpu\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

        output, returnVal = pcs(temp_cib, "cluster localnode add --corosync_conf=corosync.conf.tmp rh7-3")
        ac(output,"rh7-3: successfully added!\n")
        assert returnVal == 0

        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udpu\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n  node {\n        ring0_addr: rh7-3\n        nodeid: 3\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\n}\n\nlogging {\nto_syslog: yes\n}\n')

        output, returnVal = pcs(temp_cib, "cluster localnode remove --corosync_conf=corosync.conf.tmp rh7-3")
        assert returnVal == 0
        assert output == "rh7-3: successfully removed!\n",output

        with open("corosync.conf.tmp") as f:
            data = f.read()
            assert data == 'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udpu\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n',[data]

        o,r = pcs(temp_cib, "cluster localnode add --corosync_conf=corosync.conf.tmp rh7-3,192.168.1.3")
        assert r == 0
        assert o == "rh7-3,192.168.1.3: successfully added!\n",[o]
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udpu\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n  node {\n        ring0_addr: rh7-3\n        ring1_addr: 192.168.1.3\n        nodeid: 3\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\n}\n\nlogging {\nto_syslog: yes\n}\n')

        o,r = pcs(temp_cib, "cluster localnode remove --corosync_conf=corosync.conf.tmp rh7-2")
        assert r == 0
        assert o == "rh7-2: successfully removed!\n",[o]
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udpu\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-3\n        ring1_addr: 192.168.1.3\n        nodeid: 3\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

        o,r = pcs(temp_cib, "cluster localnode remove --corosync_conf=corosync.conf.tmp rh7-3,192.168.1.3")
        assert r == 0
        assert o == "rh7-3,192.168.1.3: successfully removed!\n",[o]
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udpu\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

        output, returnVal = pcs(temp_cib, "cluster setup --force --local --corosync_conf=corosync.conf2.tmp --name cname rh7-1 rh7-2 rh7-3")
        ac(output,"")
        assert returnVal == 0

        with open("corosync.conf2.tmp") as f:
            data = f.read()
            assert data == 'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udpu\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n  node {\n        ring0_addr: rh7-3\n        nodeid: 3\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\n\n}\n\nlogging {\nto_syslog: yes\n}\n',[data]

## Test to make transport is set
        output, returnVal = pcs(temp_cib, "cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --transport udp")
        ac(output,"Error: corosync.conf.tmp already exists, use --force to overwrite\n")
        assert returnVal == 1

        output, returnVal = pcs(temp_cib, "cluster setup --force --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --transport udp")
        ac(output,"")
        assert returnVal == 0

        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udp\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

    def testCreationRhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(temp_cib, "cluster") 
        self.assertTrue(output.startswith("\nUsage: pcs cluster [commands]..."))
        self.assertEquals(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp cname rh7-1 rh7-2"
        )
        ac(output, """\
Error: A cluster name (--name <name>) is required to setup a cluster
""")
        self.assertEquals(returnVal, 1)

        # Setup a 2 node cluster and make sure the two node config is set, then
        # add a node and make sure that it's unset, then remove a node and make
        # sure it's set again
        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2"
        )
        ac(output, "")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="9" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode add --cluster_conf=cluster.conf.tmp rh7-3"
        )
        ac(output, "rh7-3: successfully added!\n")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="13" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3" nodeid="3">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-3"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" transport="udp"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode remove --cluster_conf=cluster.conf.tmp rh7-3"
        )
        ac(output, "rh7-3: successfully removed!\n")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="15" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode add --cluster_conf=cluster.conf.tmp rh7-3,192.168.1.3"
        )
        ac(output, "rh7-3,192.168.1.3: successfully added!\n")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="20" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3" nodeid="3">
      <altname name="192.168.1.3"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-3"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" transport="udp"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode remove --cluster_conf=cluster.conf.tmp rh7-2"
        )
        ac(output, "rh7-2: successfully removed!\n")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="22" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3" nodeid="3">
      <altname name="192.168.1.3"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-3"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode remove --cluster_conf=cluster.conf.tmp rh7-3,192.168.1.3"
        )
        ac(output, "rh7-3,192.168.1.3: successfully removed!\n")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="23" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf=cluster.conf2.tmp --name cname rh7-1 rh7-2 rh7-3"
        )
        ac(output, "")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf2.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="12" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3" nodeid="3">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-3"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" transport="udp"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

        # Test to make transport is set
        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --transport udpu"
        )
        ac(output, """\
Warning: Using udpu transport on a CMAN cluster, cluster restart is required after node add or remove
Error: cluster.conf.tmp already exists, use --force to overwrite
""")
        self.assertEquals(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --transport udpu"
        )
        ac(output, """\
Warning: Using udpu transport on a CMAN cluster, cluster restart is required after node add or remove
""")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="9" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udpu" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

    def testIPV6(self):
        if utils.is_rhel6():
            return

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name cnam rh7-1 rh7-2 --ipv6")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: cnam\ntransport: udpu\nip_version: ipv6\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

    def testIPV6Rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf=cluster.conf.tmp --name cnam rh7-1 rh7-2 --ipv6"
        )
        ac(output, """\
Warning: --ipv6 ignored as it is not supported on CMAN clusters
""")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="9" name="cnam">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")


    def testRRPConfig(self):
        if utils.is_rhel6():
            return

        o,r = pcs("cluster setup --transport udp --force --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udp\nrrp_mode: passive\n  interface {\n    ringnumber: 0\n    bindnetaddr: 1.1.1.0\n    mcastaddr: 239.255.1.1\n    mcastport: 5405\n  }\n  interface {\n    ringnumber: 1\n    bindnetaddr: 1.1.2.0\n    mcastaddr: 239.255.2.1\n    mcastport: 5405\n  }\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

        o,r = pcs("cluster setup --transport udp --force --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --mcast0 8.8.8.8 --addr1 1.1.2.0 --mcast1 9.9.9.9")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udp\nrrp_mode: passive\n  interface {\n    ringnumber: 0\n    bindnetaddr: 1.1.1.0\n    mcastaddr: 8.8.8.8\n    mcastport: 5405\n  }\n  interface {\n    ringnumber: 1\n    bindnetaddr: 1.1.2.0\n    mcastaddr: 9.9.9.9\n    mcastport: 5405\n  }\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

        o,r = pcs("cluster setup --transport udp --force --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --mcastport0 9999 --mcastport1 9998 --addr1 1.1.2.0")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udp\nrrp_mode: passive\n  interface {\n    ringnumber: 0\n    bindnetaddr: 1.1.1.0\n    mcastaddr: 239.255.1.1\n    mcastport: 9999\n  }\n  interface {\n    ringnumber: 1\n    bindnetaddr: 1.1.2.0\n    mcastaddr: 239.255.2.1\n    mcastport: 9998\n  }\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --ttl0 4 --ttl1 5 --transport udp")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udp\nrrp_mode: passive\n  interface {\n    ringnumber: 0\n    bindnetaddr: 1.1.1.0\n    mcastaddr: 239.255.1.1\n    mcastport: 5405\n    ttl: 4\n  }\n  interface {\n    ringnumber: 1\n    bindnetaddr: 1.1.2.0\n    mcastaddr: 239.255.2.1\n    mcastport: 5405\n    ttl: 5\n  }\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --transport udp")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udp\nrrp_mode: active\n  interface {\n    ringnumber: 0\n    bindnetaddr: 1.1.1.0\n    mcastaddr: 239.255.1.1\n    mcastport: 5405\n  }\n  interface {\n    ringnumber: 1\n    bindnetaddr: 1.1.2.0\n    mcastaddr: 239.255.2.1\n    mcastport: 5405\n  }\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --broadcast0 --transport udp")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udp\nrrp_mode: active\n  interface {\n    ringnumber: 0\n    bindnetaddr: 1.1.1.0\n    broadcast: yes\n  }\n  interface {\n    ringnumber: 1\n    bindnetaddr: 1.1.2.0\n    mcastaddr: 239.255.2.1\n    mcastport: 5405\n  }\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name cname rh7-1,192.168.99.1 rh7-2,192.168.99.2,192.168.99.3")
        ac(o,"Error: You cannot specify more than two addresses for a node: rh7-2,192.168.99.2,192.168.99.3\n")
        assert r == 1

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name cname rh7-1,192.168.99.1 rh7-2,192.168.99.2")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: cname\ntransport: udpu\nrrp_mode: passive\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        ring1_addr: 192.168.99.1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        ring1_addr: 192.168.99.2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1,192.168.99.1 rh7-2")
        ac(o,"Error: if one node is configured for RRP, all nodes must configured for RRP\n")
        assert r == 1

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr0 1.1.2.0")
        assert r == 1
        ac(o, "Error: --addr0 can only be used once\n")

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname nonexistant-address")
        assert r == 1
        ac(o,"Error: Unable to resolve all hostnames (use --force to override).\nWarning: Unable to resolve hostname: nonexistant-address\n")

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname nonexistant-address --force")
        assert r == 0
        ac(o,"Warning: Unable to resolve hostname: nonexistant-address\n")

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name test99 rh7-1 rh7-2 --wait_for_all=2 --auto_tie_breaker=3 --last_man_standing=4 --last_man_standing_window=5")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: test99\ntransport: udpu\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\nwait_for_all: 2\nauto_tie_breaker: 3\nlast_man_standing: 4\nlast_man_standing_window: 5\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name test99 rh7-1 rh7-2 --wait_for_all=1 --auto_tie_breaker=1 --last_man_standing=1 --last_man_standing_window=12000")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: test99\ntransport: udpu\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\nwait_for_all: 1\nauto_tie_breaker: 1\nlast_man_standing: 1\nlast_man_standing_window: 12000\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

        o,r = pcs("cluster setup --force --local --name test99 rh7-1 rh7-2 --addr0 1.1.1.1")
        assert r == 1
        ac(o,"Error: --addr0 and --addr1 can only be used with --transport=udp\n")

        os.remove("corosync.conf.tmp")
        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --broadcast0 --transport udp")
        assert r == 1
        ac("Error: using a RRP mode of 'active' is not supported or tested, use --force to override\n",o)

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode blah --broadcast0 --transport udp")
        assert r == 1
        ac("Error: blah is an unknown RRP mode, use --force to override\n", o)

        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode passive --broadcast0 --transport udp")
        assert r == 0
        ac("", o)

        os.remove("corosync.conf.tmp")
        o,r = pcs("cluster setup --local --corosync_conf=corosync.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --broadcast0 --transport udp")
        assert r == 0
        ac("", o)

    def testRRPConfigRhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --transport udp --force --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0"
        )
        ac(output, "")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1">
    <multicast addr="239.255.1.1"/>
    <altmulticast addr="239.255.2.1"/>
  </cman>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="passive"/>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --transport udp --force --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --mcast0 8.8.8.8 --addr1 1.1.2.0 --mcast1 9.9.9.9"
        )
        ac(output, "")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1">
    <multicast addr="8.8.8.8"/>
    <altmulticast addr="9.9.9.9"/>
  </cman>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="passive"/>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --transport udp --force --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --mcastport0 9999 --mcastport1 9998 --addr1 1.1.2.0"
        )
        ac(output, "")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1">
    <multicast addr="239.255.1.1" port="9999"/>
    <altmulticast addr="239.255.2.1" port="9998"/>
  </cman>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="passive"/>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --ttl0 4 --ttl1 5 --transport udp"
        )
        ac(output, "")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1">
    <multicast addr="239.255.1.1" ttl="4"/>
    <altmulticast addr="239.255.2.1" ttl="5"/>
  </cman>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="passive"/>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --transport udp"
        )
        ac(output, "")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1">
    <multicast addr="239.255.1.1"/>
    <altmulticast addr="239.255.2.1"/>
  </cman>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="active"/>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --broadcast0 --transport udp"
        )
        ac(output, """\
Warning: Enabling broadcast for ring 1 as CMAN does not support broadcast in only one ring
""")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="12" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="yes" expected_votes="1" transport="udpb" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="active"/>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf=cluster.conf.tmp --name cname rh7-1,192.168.99.1 rh7-2,192.168.99.2,192.168.99.3"
        )
        ac(output, """\
Error: You cannot specify more than two addresses for a node: rh7-2,192.168.99.2,192.168.99.3
""")
        self.assertEquals(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf=cluster.conf.tmp --name cname rh7-1,192.168.99.1 rh7-2,192.168.99.2"
        )
        ac(output, "")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="12" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <altname name="192.168.99.1"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <altname name="192.168.99.2"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem rrp_mode="passive"/>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --name cname rh7-1,192.168.99.1 rh7-2"
        )
        ac(output, """\
Error: if one node is configured for RRP, all nodes must configured for RRP
""")
        self.assertEquals(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr0 1.1.2.0"
        )
        ac(output, "Error: --addr0 can only be used once\n")
        self.assertEquals(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --name cname nonexistant-address"
        )
        ac(output, """\
Error: Unable to resolve all hostnames (use --force to override).\nWarning: Unable to resolve hostname: nonexistant-address
""")
        self.assertEquals(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname nonexistant-address --force"
        )
        ac(output, """\
Warning: Unable to resolve hostname: nonexistant-address
""")
        self.assertEquals(returnVal, 0)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf=cluster.conf.tmp --name test99 rh7-1 rh7-2 --wait_for_all=2 --auto_tie_breaker=3 --last_man_standing=4 --last_man_standing_window=5"
        )
        ac(output, """\
Warning: --wait_for_all ignored as it is not supported on CMAN clusters
Warning: --auto_tie_breaker ignored as it is not supported on CMAN clusters
Warning: --last_man_standing ignored as it is not supported on CMAN clusters
Warning: --last_man_standing_window ignored as it is not supported on CMAN clusters
""")
        self.assertEquals(returnVal, 0)

        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="9" name="test99">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --name test99 rh7-1 rh7-2 --addr0 1.1.1.1 --transport=udpu"
        )
        ac(output, """\
Error: --addr0 and --addr1 can only be used with --transport=udp
Warning: Using udpu transport on a CMAN cluster, cluster restart is required after node add or remove
""")
        self.assertEquals(returnVal, 1)

        os.remove("cluster.conf.tmp")
        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --broadcast0 --transport udp"
        )
        ac(output, """\
Error: using a RRP mode of 'active' is not supported or tested, use --force to override
""")
        self.assertEquals(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode blah --broadcast0 --transport udp"
        )
        ac(output, """\
Error: blah is an unknown RRP mode, use --force to override
""")
        self.assertEquals(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode passive --broadcast0 --transport udp"
        )
        ac(output, """\
Warning: Enabling broadcast for ring 1 as CMAN does not support broadcast in only one ring
""")
        self.assertEquals(returnVal, 0)

        os.remove("cluster.conf.tmp")
        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf=cluster.conf.tmp --name cname rh7-1 rh7-2 --addr0 1.1.1.0 --addr1 1.1.2.0 --broadcast0 --transport udp"
        )
        ac(output, """\
Warning: Enabling broadcast for ring 1 as CMAN does not support broadcast in only one ring
""")
        self.assertEquals(returnVal, 0)

    def testTotemOptions(self):
        if utils.is_rhel6():
            return

        o,r = pcs("cluster setup --force --local --corosync_conf=corosync.conf.tmp --name test99 rh7-1 rh7-2 --token 20000 --join 20001 --consensus 20002 --miss_count_const 20003 --fail_recv_const 20004 --token_coefficient 20005")
        ac(o,"")
        assert r == 0
        with open("corosync.conf.tmp") as f:
            data = f.read()
            ac(data,'totem {\nversion: 2\nsecauth: off\ncluster_name: test99\ntransport: udpu\ntoken: 20000\ntoken_coefficient: 20005\njoin: 20001\nconsensus: 20002\nmiss_count_const: 20003\nfail_recv_const: 20004\n}\n\nnodelist {\n  node {\n        ring0_addr: rh7-1\n        nodeid: 1\n       }\n  node {\n        ring0_addr: rh7-2\n        nodeid: 2\n       }\n}\n\nquorum {\nprovider: corosync_votequorum\ntwo_node: 1\n}\n\nlogging {\nto_syslog: yes\n}\n')

    def testTotemOptionsRhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf=cluster.conf.tmp --name test99 rh7-1 rh7-2 --token 20000 --join 20001 --consensus 20002 --miss_count_const 20003 --fail_recv_const 20004 --token_coefficient 20005")
        ac(output, """\
Warning: --token_coefficient ignored as it is not supported on CMAN clusters
""")
        self.assertEquals(returnVal, 0)
        with open("cluster.conf.tmp") as f:
            data = f.read()
        ac(data, """\
<cluster config_version="10" name="test99">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="udp" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
  <totem consensus="20002" fail_recv_const="20004" join="20001" miss_count_const="20003" token="20000"/>
</cluster>
""")

    def testUIDGID(self):
        if utils.is_rhel6():
            os.system("cp cluster.conf cluster.conf.tmp")
            o,r = pcs("cluster uidgid --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "No uidgids configured in cluster.conf\n")

            o,r = pcs("cluster uidgid blah --cluster_conf=cluster.conf.tmp")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs("cluster uidgid rm --cluster_conf=cluster.conf.tmp")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs("cluster uidgid add --cluster_conf=cluster.conf.tmp")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs("cluster uidgid add blah --cluster_conf=cluster.conf.tmp")
            assert r == 1
            ac(o, "Error: uidgid options must be of the form uid=<uid> gid=<gid>\n")

            o,r = pcs("cluster uidgid rm blah --cluster_conf=cluster.conf.tmp")
            assert r == 1
            ac(o, "Error: uidgid options must be of the form uid=<uid> gid=<gid>\n")

            o,r = pcs("cluster uidgid add uid=zzz --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "")

            o,r = pcs("cluster uidgid add uid=zzz --cluster_conf=cluster.conf.tmp")
            assert r == 1
            ac(o, "Error: unable to add uidgid\nError: uidgid entry already exists with uid=zzz, gid=\n")

            o,r = pcs("cluster uidgid add gid=yyy --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "")

            o,r = pcs("cluster uidgid add uid=aaa gid=bbb --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "")

            o,r = pcs("cluster uidgid --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "UID/GID: gid=, uid=zzz\nUID/GID: gid=yyy, uid=\nUID/GID: gid=bbb, uid=aaa\n")

            o,r = pcs("cluster uidgid rm gid=bbb --cluster_conf=cluster.conf.tmp")
            assert r == 1
            ac(o, "Error: unable to remove uidgid\nError: unable to find uidgid with uid=, gid=bbb\n")

            o,r = pcs("cluster uidgid rm uid=aaa gid=bbb --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "")

            o,r = pcs("cluster uidgid --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "UID/GID: gid=, uid=zzz\nUID/GID: gid=yyy, uid=\n")

            o,r = pcs("cluster uidgid rm uid=zzz --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "")

            o,r = pcs("config --cluster_conf=cluster.conf.tmp")
            assert r == 0
            assert o.find("UID/GID: gid=yyy, uid=") != -1

            o,r = pcs("cluster uidgid rm gid=yyy --cluster_conf=cluster.conf.tmp")
            assert r == 0
            ac(o, "")

            o,r = pcs("config --cluster_conf=cluster.conf.tmp")
            assert r == 0
            assert o.find("No uidgids") == -1
        else:
            o,r = pcs("cluster uidgid")
            assert r == 0
            ac(o, "No uidgids configured in cluster.conf\n")

            o,r = pcs("cluster uidgid add")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs("cluster uidgid rm")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs("cluster uidgid xx")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs("cluster uidgid add uid=testuid gid=testgid")
            assert r == 0
            ac(o, "")

            o,r = pcs("cluster uidgid add uid=testuid gid=testgid")
            assert r == 1
            ac(o, "Error: uidgid file with uid=testuid and gid=testgid already exists\n")

            o,r = pcs("cluster uidgid rm uid=testuid2 gid=testgid2")
            assert r == 1
            ac(o, "Error: no uidgid files with uid=testuid2 and gid=testgid2 found\n")

            o,r = pcs("cluster uidgid rm uid=testuid gid=testgid2")
            assert r == 1
            ac(o, "Error: no uidgid files with uid=testuid and gid=testgid2 found\n")

            o,r = pcs("cluster uidgid rm uid=testuid2 gid=testgid")
            assert r == 1
            ac(o, "Error: no uidgid files with uid=testuid2 and gid=testgid found\n")

            o,r = pcs("cluster uidgid")
            assert r == 0
            ac(o, "UID/GID: uid=testuid gid=testgid\n")

            o,r = pcs("cluster uidgid rm uid=testuid gid=testgid")
            assert r == 0
            ac(o, "")

            o,r = pcs("cluster uidgid")
            assert r == 0
            ac(o, "No uidgids configured in cluster.conf\n")

    def testClusterUpgrade(self):
        if not isMinimumPacemakerVersion(1,1,11):
            print "WARNING: Unable to test cluster upgrade because pacemaker is older than 1.1.11"
            return
        with open(temp_cib) as myfile:
            data = myfile.read()
            assert data.find("pacemaker-1.2") != -1
            assert data.find("pacemaker-2.") == -1

        o,r = pcs("cluster cib-upgrade")
        ac(o,"Cluster CIB has been upgraded to latest version\n")
        assert r == 0

        with open(temp_cib) as myfile:
            data = myfile.read()
            assert data.find("pacemaker-1.2") == -1
            assert data.find("pacemaker-2.") != -1

        o,r = pcs("cluster cib-upgrade")
        ac(o,"Cluster CIB has been upgraded to latest version\n")
        assert r == 0

if __name__ == "__main__":
    unittest.main()

