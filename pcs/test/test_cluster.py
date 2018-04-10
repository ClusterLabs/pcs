import os
import shutil
import socket
import unittest
from unittest import mock

from pcs.test.tools.assertions import (
    ac,
    AssertPcsMixin,
)
from pcs.test.tools.misc import (
    get_test_resource as rc,
    skip_unless_pacemaker_version,
    skip_if_service_enabled,
    outdent,
)
from pcs.test.tools.pcs_runner import (
    pcs,
    PcsRunner,
)

from pcs import cluster, utils
from pcs.cli.common.errors import CmdLineInputError

empty_cib = rc("cib-empty-withnodes.xml")
temp_cib = rc("temp-cib.xml")
cluster_conf_file = rc("cluster.conf")
cluster_conf_tmp = rc("cluster.conf.tmp")
corosync_conf_tmp = rc("corosync.conf.tmp")

try:
    s1 = socket.gethostbyname("rh7-1.localhost")
    s2 = socket.gethostbyname("rh7-2.localhost")
    TEST_NODES_RESOLVED = True
except socket.gaierror:
    TEST_NODES_RESOLVED = False

need_to_resolve_test_nodes = unittest.skipUnless(
    TEST_NODES_RESOLVED,
    "unable to resolve all hostnames: rh7-1.localhost, rh7-2.localhost"
)

class ClusterTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(
            temp_cib, corosync_conf_tmp, cluster_conf_tmp
        )
        if os.path.exists(corosync_conf_tmp):
            os.unlink(corosync_conf_tmp)
        if os.path.exists(cluster_conf_tmp):
            os.unlink(cluster_conf_tmp)

    def testNodeStandby(self):
        # only basic test, standby subcommands were moved to 'pcs node'
        output, returnVal = pcs(temp_cib, "cluster standby rh7-1")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "cluster unstandby rh7-1")
        ac(output, "")
        assert returnVal == 0

    def testRemoteNode(self):
        #pylint: disable=trailing-whitespace
        o,r = pcs(
            temp_cib,
            "resource create D1 ocf:heartbeat:Dummy --no-default-ops"
        )
        assert r==0 and o==""

        o,r = pcs(
            temp_cib,
            "resource create D2 ocf:heartbeat:Dummy --no-default-ops"
        )
        assert r==0 and o==""

        o,r = pcs(temp_cib, "cluster remote-node rh7-2g D1")
        assert r==1 and o.startswith("\nUsage: pcs cluster remote-node")

        o,r = pcs(temp_cib, "cluster remote-node add rh7-2g D1 --force")
        assert r==0
        self.assertEqual(
            o,
            "Warning: this command is deprecated, use 'pcs cluster node"
                " add-guest'\n"
        )

        o,r = pcs(
            temp_cib,
            "cluster remote-node add rh7-1 D2 remote-port=100 remote-addr=400"
            " remote-connect-timeout=50 --force"
        )
        assert r==0
        self.assertEqual(
            o,
            "Warning: this command is deprecated, use 'pcs cluster node"
                " add-guest'\n"
        )

        self.assert_pcs_success("resource --full", outdent(
            """\
             Resource: D1 (class=ocf provider=heartbeat type=Dummy)
              Meta Attrs: remote-node=rh7-2g 
              Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
             Resource: D2 (class=ocf provider=heartbeat type=Dummy)
              Meta Attrs: remote-node=rh7-1 remote-port=100 remote-addr=400 remote-connect-timeout=50 
              Operations: monitor interval=10s timeout=20s (D2-monitor-interval-10s)
            """
        ))

        o,r = pcs(temp_cib, "cluster remote-node remove")
        assert r==1 and o.startswith("\nUsage: pcs cluster remote-node")

        self.assert_pcs_fail(
            "cluster remote-node remove rh7-2g",
            "Error: this command is deprecated, use 'pcs cluster node"
            " remove-guest', use --force to override\n"
        )
        self.assert_pcs_success(
            "cluster remote-node remove rh7-2g --force",
            "Warning: this command is deprecated, use 'pcs cluster node"
            " remove-guest'\n"
        )

        self.assert_pcs_fail(
            "cluster remote-node add rh7-2g NOTARESOURCE --force",
            "Error: unable to find resource 'NOTARESOURCE'\n"
                "Warning: this command is deprecated, use"
                " 'pcs cluster node add-guest'\n"
            ,
        )

        self.assert_pcs_fail(
            "cluster remote-node remove rh7-2g",
            "Error: this command is deprecated, use 'pcs cluster node"
                " remove-guest', use --force to override\n"
        )
        self.assert_pcs_fail(
            "cluster remote-node remove rh7-2g --force",
            "Error: unable to remove: cannot find remote-node 'rh7-2g'\n"
            "Warning: this command is deprecated, use 'pcs cluster node"
                " remove-guest'\n"
        )


        self.assert_pcs_success("resource --full", outdent(
            """\
             Resource: D1 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
             Resource: D2 (class=ocf provider=heartbeat type=Dummy)
              Meta Attrs: remote-node=rh7-1 remote-port=100 remote-addr=400 remote-connect-timeout=50 
              Operations: monitor interval=10s timeout=20s (D2-monitor-interval-10s)
            """
        ))

        self.assert_pcs_fail(
            "cluster remote-node remove rh7-1",
            "Error: this command is deprecated, use 'pcs cluster node"
                " remove-guest', use --force to override\n"
        )
        self.assert_pcs_success(
            "cluster remote-node remove rh7-1 --force",
            "Warning: this command is deprecated, use 'pcs cluster node"
                " remove-guest'\n"
        )

        self.assert_pcs_success("resource --full", outdent(
            """\
             Resource: D1 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
             Resource: D2 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (D2-monitor-interval-10s)
            """
        ))

    def test_cluster_setup_bad_args(self):
        output, returnVal = pcs(temp_cib, "cluster setup")
        self.assertEqual(
            "Error: A cluster name (--name <name>) is required to setup a cluster\n",
            output
        )
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "cluster setup --name cname")
        self.assertTrue(output.startswith("\nUsage: pcs cluster setup..."))
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "cluster setup cname rh7-1.localhost rh7-2.localhost")
        self.assertEqual(
            "Error: A cluster name (--name <name>) is required to setup a cluster\n",
            output
        )
        self.assertEqual(1, returnVal)

    @need_to_resolve_test_nodes
    def test_cluster_setup_hostnames_resolving(self):
        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --cluster_conf={1} --name cname nonexistant-address.invalid"
            .format(corosync_conf_tmp, cluster_conf_tmp)
        )
        ac(output, """\
Error: Unable to resolve all hostnames, use --force to override
Warning: Unable to resolve hostname: nonexistant-address.invalid
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --cluster_conf={1} --name cname nonexistant-address.invalid --force"
            .format(corosync_conf_tmp, cluster_conf_tmp)
        )
        ac(output, """\
Warning: Unable to resolve hostname: nonexistant-address.invalid
""")
        self.assertEqual(0, returnVal)

    def test_cluster_setup_file_exists(self):
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost"
            .format(corosync_conf_tmp)
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        corosync_conf = """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
"""
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, corosync_conf)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-2.localhost rh7-3.localhost"
            .format(corosync_conf_tmp)
        )
        self.assertEqual("""\
Error: {0} already exists, use --force to overwrite
""".format(corosync_conf_tmp),
            output
        )
        self.assertEqual(1, returnVal)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, corosync_conf)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --corosync_conf={0} --name cname rh7-2.localhost rh7-3.localhost"
            .format(corosync_conf_tmp)
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-2.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-3.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    @need_to_resolve_test_nodes
    def test_cluster_setup_file_exists_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost"
            .format(cluster_conf_tmp)
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        cluster_conf = """\
<cluster config_version="9" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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
"""
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, cluster_conf)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name cname rh7-2.localhost rh7-3.localhost"
            .format(cluster_conf_tmp)
        )
        self.assertEqual("""\
Error: {0} already exists, use --force to overwrite
""".format(cluster_conf_tmp),
            output
        )
        self.assertEqual(1, returnVal)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, cluster_conf)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf={0} --name cname rh7-2.localhost rh7-3.localhost"
            .format(cluster_conf_tmp)
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="9" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-2.localhost" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3.localhost" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-3.localhost"/>
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

    def test_cluster_setup_encryption_enabled(self):
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --encryption=1"
            .format(corosync_conf_tmp)
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_encryption_disabled(self):
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --encryption=0"
            .format(corosync_conf_tmp)
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_encryption_bad_value(self):
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --encryption=bad"
            .format(corosync_conf_tmp)
        )
        self.assertEqual(
            "Error: 'bad' is not a valid --encryption value, use 0, 1\n",
            output
        )
        self.assertEqual(1, returnVal)

    @skip_if_service_enabled("sbd")
    def test_cluster_setup_2_nodes_no_atb(self):
        # Setup a 2 node cluster and make sure the two node config is set, then
        # add a node and make sure that it's unset, then remove a node and make
        # sure it's set again.
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost"
            .format(corosync_conf_tmp)
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode add --corosync_conf={0} rh7-3.localhost"
            .format(corosync_conf_tmp)
        )
        self.assertEqual("rh7-3.localhost: successfully added!\n", output)
        self.assertEqual(0, returnVal)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }

    node {
        ring0_addr: rh7-3.localhost
        nodeid: 3
    }
}

quorum {
    provider: corosync_votequorum
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode remove --corosync_conf={0} rh7-3.localhost"
            .format(corosync_conf_tmp)
        )
        self.assertEqual(0, returnVal)
        self.assertEqual("rh7-3.localhost: successfully removed!\n", output)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode add --corosync_conf={0} rh7-3.localhost,192.168.1.3"
            .format(corosync_conf_tmp)
        )
        self.assertEqual("rh7-3.localhost,192.168.1.3: successfully added!\n", output)
        self.assertEqual(0, returnVal)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }

    node {
        ring0_addr: rh7-3.localhost
        ring1_addr: 192.168.1.3
        nodeid: 3
    }
}

quorum {
    provider: corosync_votequorum
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode remove --corosync_conf={0} rh7-2.localhost"
            .format(corosync_conf_tmp)
        )
        self.assertEqual(0, returnVal)
        self.assertEqual("rh7-2.localhost: successfully removed!\n", output)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-3.localhost
        ring1_addr: 192.168.1.3
        nodeid: 3
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode remove --corosync_conf={0} rh7-3.localhost,192.168.1.3"
            .format(corosync_conf_tmp)
        )
        self.assertEqual(0, returnVal)
        self.assertEqual("rh7-3.localhost,192.168.1.3: successfully removed!\n", output)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }
}

quorum {
    provider: corosync_votequorum
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_2_nodes_with_atb(self):
        # Setup a 2 node cluster with auto_tie_breaker and make sure the two
        # node config is NOT set, then add a node, then remove a node and make
        # sure it is still NOT set.
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --auto_tie_breaker=1"
            .format(corosync_conf_tmp)
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    auto_tie_breaker: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode add --corosync_conf={0} rh7-3.localhost"
            .format(corosync_conf_tmp)
        )
        self.assertEqual(output, "rh7-3.localhost: successfully added!\n")
        self.assertEqual(0, returnVal)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }

    node {
        ring0_addr: rh7-3.localhost
        nodeid: 3
    }
}

quorum {
    provider: corosync_votequorum
    auto_tie_breaker: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

        output, returnVal = pcs(
            temp_cib,
            "cluster localnode remove --corosync_conf={0} rh7-3.localhost"
            .format(corosync_conf_tmp)
        )
        self.assertEqual("rh7-3.localhost: successfully removed!\n", output)
        self.assertEqual(0, returnVal)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    auto_tie_breaker: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_3_nodes(self):
        # Setup a 3 node cluster
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost rh7-3.localhost"
            .format(corosync_conf_tmp)
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }

    node {
        ring0_addr: rh7-3.localhost
        nodeid: 3
    }
}

quorum {
    provider: corosync_votequorum
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_transport(self):
        # Test to make transport is set
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --transport udp"
            .format(corosync_conf_tmp)
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udp
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    @need_to_resolve_test_nodes
    def test_cluster_setup_2_nodes_rhel6(self):
        # Setup a 2 node cluster and make sure the two node config is set, then
        # add a node and make sure that it's unset, then remove a node and make
        # sure it's set again.
        # There is no auto-tie-breaker in CMAN so we don't need the non-atb
        # variant as we do for corosync.
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost"
            .format(cluster_conf_tmp)
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="9" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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
            "cluster localnode add --cluster_conf={0} rh7-3.localhost"
            .format(cluster_conf_tmp)
        )
        ac(output, "rh7-3.localhost: successfully added!\n")
        self.assertEqual(returnVal, 0)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="13" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3.localhost" nodeid="3">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-3.localhost"/>
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
            "cluster localnode remove --cluster_conf={0} rh7-3.localhost"
            .format(cluster_conf_tmp)
        )
        ac(output, "rh7-3.localhost: successfully removed!\n")
        self.assertEqual(returnVal, 0)

        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="15" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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
            "cluster localnode add --cluster_conf={0} rh7-3.localhost,192.168.1.3"
            .format(cluster_conf_tmp)
        )
        ac(output, "rh7-3.localhost,192.168.1.3: successfully added!\n")
        self.assertEqual(returnVal, 0)

        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="20" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3.localhost" nodeid="3">
      <altname name="192.168.1.3"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-3.localhost"/>
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
            "cluster localnode remove --cluster_conf={0} rh7-2.localhost"
            .format(cluster_conf_tmp)
        )
        ac(output, "rh7-2.localhost: successfully removed!\n")
        self.assertEqual(returnVal, 0)

        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="22" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3.localhost" nodeid="3">
      <altname name="192.168.1.3"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-3.localhost"/>
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
            "cluster localnode remove --cluster_conf={0} rh7-3.localhost,192.168.1.3"
            .format(cluster_conf_tmp)
        )
        ac(output, "rh7-3.localhost,192.168.1.3: successfully removed!\n")
        self.assertEqual(returnVal, 0)

        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="23" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
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

    @need_to_resolve_test_nodes
    def test_cluster_setup_3_nodes_rhel6(self):
        # Setup a 3 node cluster
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost rh7-3.localhost"
            .format(cluster_conf_tmp)
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="12" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3.localhost" nodeid="3">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-3.localhost"/>
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

    @need_to_resolve_test_nodes
    def test_cluster_setup_transport_rhel6(self):
        # Test to make transport is set
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost --transport udpu"
            .format(cluster_conf_tmp)
        )
        ac(output, """\
Warning: Using udpu transport on a CMAN cluster, cluster restart is required after node add or remove
""")
        self.assertEqual(returnVal, 0)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="9" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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

    def test_cluster_setup_ipv6(self):
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --ipv6"
            .format(corosync_conf_tmp)
        )
        self.assertEqual("", output)
        self.assertEqual(0, returnVal)
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
    ip_version: ipv6
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    @need_to_resolve_test_nodes
    def test_cluster_setup_ipv6_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost --ipv6"
            .format(cluster_conf_tmp)
        )
        ac(output, """\
Warning: --ipv6 ignored as it is not supported on CMAN clusters
""")
        self.assertEqual(returnVal, 0)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="9" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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

    def test_cluster_setup_rrp_passive_udp_addr01(self):
        if utils.is_rhel6():
            return

        o,r = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr0 1.1.2.0"
            .format(corosync_conf_tmp)
        )
        assert r == 1
        ac(o, "Error: --addr0 can only be used once\n")

        o,r = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode blah --broadcast0 --transport udp"
            .format(corosync_conf_tmp)
        )
        assert r == 1
        ac(
            o,
            "Error: 'blah' is not a valid RRP mode value, use active, passive, use --force to override\n"
        )

        o,r = pcs(
            temp_cib,
            "cluster setup --transport udp --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0"
            .format(corosync_conf_tmp)
        )
        ac(o,"")
        assert r == 0
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udp
    rrp_mode: passive

    interface {
        ringnumber: 0
        bindnetaddr: 1.1.1.0
        mcastaddr: 239.255.1.1
        mcastport: 5405
    }

    interface {
        ringnumber: 1
        bindnetaddr: 1.1.2.0
        mcastaddr: 239.255.2.1
        mcastport: 5405
    }
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_rrp_passive_udp_addr01_mcast01(self):
        if utils.is_rhel6():
            return

        o,r = pcs(
            temp_cib,
            "cluster setup --transport udp --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --mcast0 8.8.8.8 --addr1 1.1.2.0 --mcast1 9.9.9.9"
            .format(corosync_conf_tmp)
        )
        ac(o,"")
        assert r == 0
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udp
    rrp_mode: passive

    interface {
        ringnumber: 0
        bindnetaddr: 1.1.1.0
        mcastaddr: 8.8.8.8
        mcastport: 5405
    }

    interface {
        ringnumber: 1
        bindnetaddr: 1.1.2.0
        mcastaddr: 9.9.9.9
        mcastport: 5405
    }
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_rrp_passive_udp_addr01_mcastport01(self):
        if utils.is_rhel6():
            return

        o,r = pcs(
            temp_cib,
            "cluster setup --transport udp --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --mcastport0 9999 --mcastport1 9998 --addr1 1.1.2.0"
            .format(corosync_conf_tmp)
        )
        ac(o,"")
        assert r == 0
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udp
    rrp_mode: passive

    interface {
        ringnumber: 0
        bindnetaddr: 1.1.1.0
        mcastaddr: 239.255.1.1
        mcastport: 9999
    }

    interface {
        ringnumber: 1
        bindnetaddr: 1.1.2.0
        mcastaddr: 239.255.2.1
        mcastport: 9998
    }
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_rrp_passive_udp_addr01_ttl01(self):
        if utils.is_rhel6():
            return

        o,r = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0 --ttl0 4 --ttl1 5 --transport udp"
            .format(corosync_conf_tmp)
        )
        ac(o,"")
        assert r == 0
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udp
    rrp_mode: passive

    interface {
        ringnumber: 0
        bindnetaddr: 1.1.1.0
        mcastaddr: 239.255.1.1
        mcastport: 5405
        ttl: 4
    }

    interface {
        ringnumber: 1
        bindnetaddr: 1.1.2.0
        mcastaddr: 239.255.2.1
        mcastport: 5405
        ttl: 5
    }
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_rrp_active_udp_addr01(self):
        if utils.is_rhel6():
            return

        o,r = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --transport udp"
            .format(corosync_conf_tmp)
        )
        ac(o, "Error: using a RRP mode of 'active' is not supported or tested, use --force to override\n")
        assert r == 1

        o,r = pcs(
            temp_cib,
            "cluster setup --force --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --transport udp"
            .format(corosync_conf_tmp)
        )
        ac(o, "Warning: using a RRP mode of 'active' is not supported or tested\n")
        assert r == 0
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udp
    rrp_mode: active

    interface {
        ringnumber: 0
        bindnetaddr: 1.1.1.0
        mcastaddr: 239.255.1.1
        mcastport: 5405
    }

    interface {
        ringnumber: 1
        bindnetaddr: 1.1.2.0
        mcastaddr: 239.255.2.1
        mcastport: 5405
    }
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_rrp_active_udp_broadcast_addr01(self):
        if utils.is_rhel6():
            return

        o,r = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --broadcast0 --transport udp"
            .format(corosync_conf_tmp)
        )
        ac(o, "Error: using a RRP mode of 'active' is not supported or tested, use --force to override\n")
        assert r == 1

        o,r = pcs(
            temp_cib,
            "cluster setup --force --local --corosync_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --broadcast0 --transport udp"
            .format(corosync_conf_tmp)
        )
        ac(o, "Warning: using a RRP mode of 'active' is not supported or tested\n")
        assert r == 0
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udp
    rrp_mode: active

    interface {
        ringnumber: 0
        bindnetaddr: 1.1.1.0
        broadcast: yes
    }

    interface {
        ringnumber: 1
        bindnetaddr: 1.1.2.0
        mcastaddr: 239.255.2.1
        mcastport: 5405
    }
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_rrp_udpu(self):
        if utils.is_rhel6():
            return

        o,r = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost,192.168.99.1 rh7-2.localhost,192.168.99.2,192.168.99.3"
            .format(corosync_conf_tmp)
        )
        ac(o,"Error: You cannot specify more than two addresses for a node: rh7-2.localhost,192.168.99.2,192.168.99.3\n")
        assert r == 1

        o,r = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost,192.168.99.1 rh7-2.localhost"
            .format(corosync_conf_tmp)
        )
        ac(o,"Error: if one node is configured for RRP, all nodes must be configured for RRP\n")
        assert r == 1

        o,r = pcs(
            temp_cib,
            "cluster setup --force --local --name test99 rh7-1.localhost rh7-2.localhost --addr0 1.1.1.1"
        )
        ac(o,"Error: --addr0 and --addr1 can only be used with --transport=udp\n")
        assert r == 1

        o,r = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name cname rh7-1.localhost,192.168.99.1 rh7-2.localhost,192.168.99.2"
            .format(corosync_conf_tmp)
        )
        ac(o,"")
        assert r == 0
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: udpu
    rrp_mode: passive
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        ring1_addr: 192.168.99.1
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        ring1_addr: 192.168.99.2
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    def test_cluster_setup_quorum_options(self):
        if utils.is_rhel6():
            return

        o,r = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name test99 rh7-1.localhost rh7-2.localhost --wait_for_all=2"
            .format(corosync_conf_tmp)
        )
        ac(o, "Error: '2' is not a valid --wait_for_all value, use 0, 1\n")
        assert r == 1

        o,r = pcs(
            temp_cib,
            "cluster setup --force --local --corosync_conf={0} --name test99 rh7-1.localhost rh7-2.localhost --wait_for_all=2"
            .format(corosync_conf_tmp)
        )
        ac(o, "Error: '2' is not a valid --wait_for_all value, use 0, 1\n")
        assert r == 1

        o,r = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name test99 rh7-1.localhost rh7-2.localhost --auto_tie_breaker=2"
            .format(corosync_conf_tmp)
        )
        ac(o, "Error: '2' is not a valid --auto_tie_breaker value, use 0, 1\n")
        assert r == 1

        o,r = pcs(
            temp_cib,
            "cluster setup --force --local --corosync_conf={0} --name test99 rh7-1.localhost rh7-2.localhost --auto_tie_breaker=2"
            .format(corosync_conf_tmp)
        )
        ac(o, "Error: '2' is not a valid --auto_tie_breaker value, use 0, 1\n")
        assert r == 1

        o,r = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name test99 rh7-1.localhost rh7-2.localhost --last_man_standing=2"
            .format(corosync_conf_tmp)
        )
        ac(o, "Error: '2' is not a valid --last_man_standing value, use 0, 1\n")
        assert r == 1

        o,r = pcs(
            temp_cib,
            "cluster setup --force --local --corosync_conf={0} --name test99 rh7-1.localhost rh7-2.localhost --last_man_standing=2"
            .format(corosync_conf_tmp)
        )
        ac(o, "Error: '2' is not a valid --last_man_standing value, use 0, 1\n")
        assert r == 1

        o,r = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name test99 rh7-1.localhost rh7-2.localhost --wait_for_all=1 --auto_tie_breaker=1 --last_man_standing=1 --last_man_standing_window=12000"
            .format(corosync_conf_tmp)
        )
        ac(o,"")
        assert r == 0
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: test99
    secauth: off
    transport: udpu
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    wait_for_all: 1
    auto_tie_breaker: 1
    last_man_standing: 1
    last_man_standing_window: 12000
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    @need_to_resolve_test_nodes
    def test_cluster_setup_rrp_passive_udp_addr01_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr0 1.1.2.0"
        )
        ac(output, "Error: --addr0 can only be used once\n")
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode blah --broadcast0 --transport udp"
            .format(cluster_conf_tmp)
        )
        ac(output, """\
Error: 'blah' is not a valid RRP mode value, use active, passive, use --force to override
Warning: Enabling broadcast for all rings as CMAN does not support broadcast in only one ring
""")
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --transport udp --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0"
            .format(cluster_conf_tmp)
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)

        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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

    @need_to_resolve_test_nodes
    def test_cluster_setup_rrp_passive_udp_addr01_mcast01_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --transport udp --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --mcast0 8.8.8.8 --addr1 1.1.2.0 --mcast1 9.9.9.9"
            .format(cluster_conf_tmp)
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)

        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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

    @need_to_resolve_test_nodes
    def test_cluster_setup_rrp_passive_udp_addr01_mcastport01_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --transport udp --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --mcastport0 9999 --mcastport1 9998 --addr1 1.1.2.0"
            .format(cluster_conf_tmp)
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)

        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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

    @need_to_resolve_test_nodes
    def test_cluster_setup_rrp_passive_udp_addr01_ttl01_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0 --ttl0 4 --ttl1 5 --transport udp"
            .format(cluster_conf_tmp)
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)

        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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

    @need_to_resolve_test_nodes
    def test_cluster_setup_rrp_active_udp_addr01_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --transport udp"
            .format(cluster_conf_tmp)
        )
        ac(
            output,
            "Error: using a RRP mode of 'active' is not supported or tested, use --force to override\n"
        )
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --transport udp"
            .format(cluster_conf_tmp)
        )
        ac(
            output,
            "Warning: using a RRP mode of 'active' is not supported or tested\n"
        )
        self.assertEqual(returnVal, 0)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="14" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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

    @need_to_resolve_test_nodes
    def test_cluster_setup_rrp_active_udp_broadcast_addr01_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --broadcast0 --transport udp"
            .format(cluster_conf_tmp)
        )
        ac(output, """\
Error: using a RRP mode of 'active' is not supported or tested, use --force to override
Warning: Enabling broadcast for all rings as CMAN does not support broadcast in only one ring
""")
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --force --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode active --broadcast0 --transport udp"
            .format(cluster_conf_tmp)
        )
        ac(output, """\
Warning: Enabling broadcast for all rings as CMAN does not support broadcast in only one ring
Warning: using a RRP mode of 'active' is not supported or tested
""")
        self.assertEqual(returnVal, 0)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="12" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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

    @need_to_resolve_test_nodes
    def test_cluster_setup_rrp_udpu_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name cname rh7-1.localhost,192.168.99.1 rh7-2.localhost,192.168.99.2,192.168.99.3"
            .format(cluster_conf_tmp)
        )
        ac(output, """\
Error: You cannot specify more than two addresses for a node: rh7-2.localhost,192.168.99.2,192.168.99.3
""")
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --name cname rh7-1.localhost,192.168.99.1 rh7-2.localhost"
        )
        ac(output, """\
Error: if one node is configured for RRP, all nodes must be configured for RRP
""")
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --name test99 rh7-1.localhost rh7-2.localhost --addr0 1.1.1.1 --transport=udpu"
        )
        ac(output, """\
Error: --addr0 and --addr1 can only be used with --transport=udp
Warning: Using udpu transport on a CMAN cluster, cluster restart is required after node add or remove
""")
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name cname rh7-1.localhost,192.168.99.1 rh7-2.localhost,192.168.99.2"
            .format(cluster_conf_tmp)
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="12" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <altname name="192.168.99.1"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <altname name="192.168.99.2"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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

    @need_to_resolve_test_nodes
    def test_cluster_setup_broadcast_rhel6(self):
        if not utils.is_rhel6():
            return

        cluster_conf = """\
<cluster config_version="12" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <altname name="1.1.2.0"/>
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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
  <totem rrp_mode="passive"/>
</cluster>
"""

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0 --rrpmode passive --broadcast0 --transport udp"
            .format(cluster_conf_tmp)
        )
        ac(output, """\
Warning: Enabling broadcast for all rings as CMAN does not support broadcast in only one ring
""")
        self.assertEqual(returnVal, 0)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, cluster_conf)

        os.remove(cluster_conf_tmp)

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name cname rh7-1.localhost rh7-2.localhost --addr0 1.1.1.0 --addr1 1.1.2.0 --broadcast0 --transport udp"
            .format(cluster_conf_tmp)
        )
        ac(output, """\
Warning: Enabling broadcast for all rings as CMAN does not support broadcast in only one ring
""")
        self.assertEqual(returnVal, 0)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, cluster_conf)

    @need_to_resolve_test_nodes
    def test_cluster_setup_quorum_options_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name test99 rh7-1.localhost rh7-2.localhost --wait_for_all=2 --auto_tie_breaker=3 --last_man_standing=4 --last_man_standing_window=5"
            .format(cluster_conf_tmp)
        )
        ac(output, """\
Warning: --wait_for_all ignored as it is not supported on CMAN clusters
Warning: --auto_tie_breaker ignored as it is not supported on CMAN clusters
Warning: --last_man_standing ignored as it is not supported on CMAN clusters
Warning: --last_man_standing_window ignored as it is not supported on CMAN clusters
""")
        self.assertEqual(returnVal, 0)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="9" name="test99">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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

    def test_cluster_setup_totem_options(self):
        if utils.is_rhel6():
            return

        o,r = pcs(
            temp_cib,
            "cluster setup --local --corosync_conf={0} --name test99 rh7-1.localhost rh7-2.localhost --token 20000 --join 20001 --consensus 20002 --miss_count_const 20003 --fail_recv_const 20004 --token_coefficient 20005"
            .format(corosync_conf_tmp)
        )
        ac(o,"")
        assert r == 0
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: test99
    secauth: off
    transport: udpu
    token: 20000
    token_coefficient: 20005
    join: 20001
    consensus: 20002
    miss_count_const: 20003
    fail_recv_const: 20004
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    @need_to_resolve_test_nodes
    def test_cluster_setup_totem_options_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "cluster setup --local --cluster_conf={0} --name test99 rh7-1.localhost rh7-2.localhost --token 20000 --join 20001 --consensus 20002 --miss_count_const 20003 --fail_recv_const 20004 --token_coefficient 20005"
            .format(cluster_conf_tmp)
        )
        ac(output, """\
Warning: --token_coefficient ignored as it is not supported on CMAN clusters
""")
        self.assertEqual(returnVal, 0)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="10" name="test99">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
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
            os.system("cp {0} {1}".format(cluster_conf_file, cluster_conf_tmp))

            o,r = pcs(temp_cib, "cluster uidgid --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 0
            ac(o, "No uidgids configured in cluster.conf\n")

            o,r = pcs(temp_cib, "cluster uidgid blah --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs(temp_cib, "cluster uidgid rm --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs(temp_cib, "cluster uidgid add --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs(temp_cib, "cluster uidgid add blah --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 1
            ac(o, "Error: uidgid options must be of the form uid=<uid> gid=<gid>\n")

            o,r = pcs(temp_cib, "cluster uidgid rm blah --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 1
            ac(o, "Error: uidgid options must be of the form uid=<uid> gid=<gid>\n")

            o,r = pcs(temp_cib, "cluster uidgid add uid=zzz --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 0
            ac(o, "")

            o,r = pcs(temp_cib, "cluster uidgid add uid=zzz --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 1
            ac(o, "Error: unable to add uidgid\nError: uidgid entry already exists with uid=zzz, gid=\n")

            o,r = pcs(temp_cib, "cluster uidgid add gid=yyy --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 0
            ac(o, "")

            o,r = pcs(temp_cib, "cluster uidgid add uid=aaa gid=bbb --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 0
            ac(o, "")

            o,r = pcs(temp_cib, "cluster uidgid --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 0
            ac(o, "UID/GID: gid=, uid=zzz\nUID/GID: gid=yyy, uid=\nUID/GID: gid=bbb, uid=aaa\n")

            o,r = pcs(temp_cib, "cluster uidgid rm gid=bbb --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 1
            ac(o, "Error: unable to remove uidgid\nError: unable to find uidgid with uid=, gid=bbb\n")

            o,r = pcs(temp_cib, "cluster uidgid rm uid=aaa gid=bbb --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 0
            ac(o, "")

            o,r = pcs(temp_cib, "cluster uidgid --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 0
            ac(o, "UID/GID: gid=, uid=zzz\nUID/GID: gid=yyy, uid=\n")

            o,r = pcs(temp_cib, "cluster uidgid rm uid=zzz --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 0
            ac(o, "")

            o,r = pcs(temp_cib, "config --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 0
            assert o.find("UID/GID: gid=yyy, uid=") != -1

            o,r = pcs(temp_cib, "cluster uidgid rm gid=yyy --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 0
            ac(o, "")

            o,r = pcs(temp_cib, "config --cluster_conf={0}".format(cluster_conf_tmp))
            assert r == 0
            assert o.find("No uidgids") == -1
        else:
            o,r = pcs(temp_cib, "cluster uidgid")
            assert r == 0
            ac(o, "No uidgids configured in cluster.conf\n")

            o,r = pcs(temp_cib, "cluster uidgid add")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs(temp_cib, "cluster uidgid rm")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs(temp_cib, "cluster uidgid xx")
            assert r == 1
            assert o.startswith("\nUsage:")

            o,r = pcs(temp_cib, "cluster uidgid add uid=testuid gid=testgid")
            assert r == 0
            ac(o, "")

            o,r = pcs(temp_cib, "cluster uidgid add uid=testuid gid=testgid")
            assert r == 1
            ac(o, "Error: uidgid file with uid=testuid and gid=testgid already exists\n")

            o,r = pcs(temp_cib, "cluster uidgid rm uid=testuid2 gid=testgid2")
            assert r == 1
            ac(o, "Error: no uidgid files with uid=testuid2 and gid=testgid2 found\n")

            o,r = pcs(temp_cib, "cluster uidgid rm uid=testuid gid=testgid2")
            assert r == 1
            ac(o, "Error: no uidgid files with uid=testuid and gid=testgid2 found\n")

            o,r = pcs(temp_cib, "cluster uidgid rm uid=testuid2 gid=testgid")
            assert r == 1
            ac(o, "Error: no uidgid files with uid=testuid2 and gid=testgid found\n")

            o,r = pcs(temp_cib, "cluster uidgid")
            assert r == 0
            ac(o, "UID/GID: uid=testuid gid=testgid\n")

            o,r = pcs(temp_cib, "cluster uidgid rm uid=testuid gid=testgid")
            assert r == 0
            ac(o, "")

            o,r = pcs(temp_cib, "cluster uidgid")
            assert r == 0
            ac(o, "No uidgids configured in cluster.conf\n")

    def test_can_not_setup_cluster_for_unknown_transport_type(self):
        if utils.is_rhel6():
            return

        self.assert_pcs_fail(
            "cluster setup --local --name cname rh7-1.localhost rh7-2.localhost --transport=unknown",
            "Error: 'unknown' is not a valid transport value, use udp, udpu, use --force to override\n"
        )

        self.assert_pcs_success(
            "cluster setup --local --name cname rh7-1.localhost rh7-2.localhost --transport=unknown --force",
            "Warning: 'unknown' is not a valid transport value, use udp, udpu\n"
        )
        with open(corosync_conf_tmp) as f:
            data = f.read()
            ac(data, """\
totem {
    version: 2
    cluster_name: cname
    secauth: off
    transport: unknown
}

nodelist {
    node {
        ring0_addr: rh7-1.localhost
        nodeid: 1
    }

    node {
        ring0_addr: rh7-2.localhost
        nodeid: 2
    }
}

quorum {
    provider: corosync_votequorum
    two_node: 1
}

logging {
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
}
""")

    @need_to_resolve_test_nodes
    def test_can_not_setup_cluster_for_unknown_transport_type_rhel6(self):
        if not utils.is_rhel6():
            return

        self.assert_pcs_fail(
            "cluster setup --local --name cname rh7-1.localhost rh7-2.localhost --transport=rdma",
            "Error: 'rdma' is not a valid transport value, use udp, udpu, use --force to override\n"
        )

        self.assert_pcs_success(
            "cluster setup --local --name cname rh7-1.localhost rh7-2.localhost --transport=rdma --force",
            "Warning: 'rdma' is not a valid transport value, use udp, udpu\n"
        )
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="9" name="cname">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1.localhost" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-1.localhost"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2.localhost" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect" port="rh7-2.localhost"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" expected_votes="1" transport="rdma" two_node="1"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

    def test_node_add_rhel6_unexpected_fence_pcmk_name(self):
        if not utils.is_rhel6():
            return

        # chnage the fence device name to a value different that set by pcs
        with open(cluster_conf_file, "r") as f:
            data = f.read()
        data = data.replace('name="pcmk-redirect"', 'name="pcmk_redirect"')
        with open(cluster_conf_tmp, "w") as f:
            f.write(data)

        # test a node is added correctly and uses the fence device
        output, returnVal = pcs(
            temp_cib,
            "cluster localnode add --cluster_conf={0} rh7-3.localhost"
            .format(cluster_conf_tmp)
        )
        ac(output, "rh7-3.localhost: successfully added!\n")
        self.assertEqual(returnVal, 0)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="13" name="test99">
  <fence_daemon/>
  <clusternodes>
    <clusternode name="rh7-1" nodeid="1">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk_redirect" port="rh7-1"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-2" nodeid="2">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk_redirect" port="rh7-2"/>
        </method>
      </fence>
    </clusternode>
    <clusternode name="rh7-3.localhost" nodeid="3">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk_redirect" port="rh7-3.localhost"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" transport="udpu"/>
  <fencedevices>
    <fencedevice agent="fence_pcmk" name="pcmk_redirect"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")

    def test_node_add_rhel6_missing_fence_pcmk(self):
        if not utils.is_rhel6():
            return

        # chnage the fence device name to a value different that set by pcs
        with open(cluster_conf_file, "r") as f:
            data = f.read()
        data = data.replace('agent="fence_pcmk"', 'agent="fence_whatever"')
        with open(cluster_conf_tmp, "w") as f:
            f.write(data)

        # test a node is added correctly and uses the fence device
        output, returnVal = pcs(
            temp_cib,
            "cluster localnode add --cluster_conf={0} rh7-3.localhost"
            .format(cluster_conf_tmp)
        )
        ac(output, "rh7-3.localhost: successfully added!\n")
        self.assertEqual(returnVal, 0)
        with open(cluster_conf_tmp) as f:
            data = f.read()
            ac(data, """\
<cluster config_version="14" name="test99">
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
    <clusternode name="rh7-3.localhost" nodeid="3">
      <fence>
        <method name="pcmk-method">
          <device name="pcmk-redirect-1" port="rh7-3.localhost"/>
        </method>
      </fence>
    </clusternode>
  </clusternodes>
  <cman broadcast="no" transport="udpu"/>
  <fencedevices>
    <fencedevice agent="fence_whatever" name="pcmk-redirect"/>
    <fencedevice agent="fence_pcmk" name="pcmk-redirect-1"/>
  </fencedevices>
  <rm>
    <failoverdomains/>
    <resources/>
  </rm>
</cluster>
""")


class ClusterUpgradeTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(rc("cib-empty-1.2.xml"), temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    @skip_unless_pacemaker_version((1, 1, 11), "CIB schema upgrade")
    def testClusterUpgrade(self):
        with open(temp_cib) as myfile:
            data = myfile.read()
            assert data.find("pacemaker-1.2") != -1
            assert data.find("pacemaker-2.") == -1

        o,r = pcs(temp_cib, "cluster cib-upgrade")
        ac(o,"Cluster CIB has been upgraded to latest version\n")
        assert r == 0

        with open(temp_cib) as myfile:
            data = myfile.read()
            assert data.find("pacemaker-1.2") == -1
            assert data.find("pacemaker-2.") != -1

        o,r = pcs(temp_cib, "cluster cib-upgrade")
        ac(o,"Cluster CIB has been upgraded to latest version\n")
        assert r == 0



class ClusterStartStop(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner()

    def test_all_and_nodelist(self):
        self.assert_pcs_fail(
            "cluster stop rh7-1 rh7-2 --all",
            stdout_full="Error: Cannot specify both --all and a list of nodes.\n"
        )
        self.assert_pcs_fail(
            "cluster start rh7-1 rh7-2 --all",
            stdout_full="Error: Cannot specify both --all and a list of nodes.\n"
        )


class ClusterEnableDisable(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner()

    def test_all_and_nodelist(self):
        self.assert_pcs_fail(
            "cluster enable rh7-1 rh7-2 --all",
            stdout_full="Error: Cannot specify both --all and a list of nodes.\n"
        )
        self.assert_pcs_fail(
            "cluster disable rh7-1 rh7-2 --all",
            stdout_full="Error: Cannot specify both --all and a list of nodes.\n"
        )

class NodeRemove(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner()

    def test_fail_when_node_does_not_exists(self):
        self.assert_pcs_fail(
            "cluster node remove not-existent --force", #
            "Error: node 'not-existent' does not appear to exist in"
                " configuration\n"
        )

def node_dict_fixture(node_name, addrs=None):
    return dict(
        name=node_name,
        addrs=addrs if addrs else None,
    )

DEFAULT_TRANSPORT_TYPE = "knet"
class NewClusterSetup(unittest.TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster"])
        self.cluster = mock.Mock(spec_set=["setup"])
        self.lib.cluster = self.cluster
        self.cluster_name = "cluster_name"

    def assert_setup_called_with(self, node_list, **kwargs):
        default_kwargs = dict(
            transport_type=DEFAULT_TRANSPORT_TYPE,
            transport_options={},
            link_list=[],
            compression_options={},
            crypto_options={},
            totem_options={},
            quorum_options={},
            wait=False,
            start=False,
            enable=False,
            force=False,
            force_unresolvable=False
        )
        default_kwargs.update(kwargs)
        self.cluster.setup.assert_called_once_with(
            self.cluster_name, node_list, **default_kwargs
        )

    def call_cmd_without_cluster_name(self, argv, modifiers=None):
        all_modifiers = {
            "enable": False,
            "force": False,
            "start": False,
            "wait": False,
        }
        all_modifiers.update(modifiers or {})
        cluster.new_cluster_setup(self.lib, argv, all_modifiers)

    def call_cmd(self, argv, modifiers=None):
        self.call_cmd_without_cluster_name(
            [self.cluster_name] + argv,
            modifiers
        )

    def test_no_cluster_name(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd_without_cluster_name([])
        self.assertIsNone(cm.exception.message)

    def test_no_node(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([])
        self.assertIsNone(cm.exception.message)

    def test_invalid_node_name(self):
        node = "node="
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([node])
        self.assertEqual(
            "Invalid character '=' in node name '{}'".format(node),
            cm.exception.message,
        )

    def test_node_defined_multiple_times(self):
        node = "node"
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([node, node])
        self.assertEqual(
            "Node name '{}' defined multiple times".format(node),
            cm.exception.message,
        )

    def test_one_node_no_addrs(self):
        node_name = "node"
        self.call_cmd([node_name])
        self.assert_setup_called_with([node_dict_fixture(node_name)])

    def test_one_node_empty_addrs(self):
        node_name = "node"
        self.call_cmd([node_name, "addrs="])
        self.assert_setup_called_with([node_dict_fixture(node_name, [''])])

    def test_one_node_with_single_address(self):
        node_name = "node"
        addr = "node_addr"
        self.call_cmd([node_name, "addrs={}".format(addr)])
        self.assert_setup_called_with([node_dict_fixture(node_name, [addr])])

    def test_one_node_with_multiple_addresses(self):
        node_name = "node"
        addr_list = ["addr{}".format(i) for i in range(3)]
        self.call_cmd([node_name, "addrs={}".format(",".join(addr_list))])
        self.assert_setup_called_with([node_dict_fixture(node_name, addr_list)])

    def test_node_unknown_options(self):
        node_name = "node"
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                [node_name, "unknown=option", "another=one", "addrs=addr"]
            )
        self.assertEqual(
            "Unknown options {} for node '{}'".format(
                ", ".join(sorted(["unknown", "another"])), node_name
            ),
            cm.exception.message,
        )

    def test_multiple_nodes(self):
        self.call_cmd(
            ["node1", "addrs=addr1,addr2", "node2", "node3", "addrs=addr"]
        )
        self.assert_setup_called_with(
            [
                node_dict_fixture("node1", ["addr1", "addr2"]),
                node_dict_fixture("node2"),
                node_dict_fixture("node3", ["addr"]),
            ]
        )

    def test_multiple_nodes_without_addrs(self):
        node_list = ["node{}".format(i) for i in range(4)]
        self.call_cmd(node_list)
        self.assert_setup_called_with(
            [node_dict_fixture(node) for node in node_list]
        )

    def test_transport_type_missing(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["node", "transport"])
        self.assertEqual("Transport type not defined", cm.exception.message)

    def test_transport_type_unknown(self):
        node = "node"
        self.call_cmd([
            node, "transport", "unknown", "a=1", "link", "b=2", "c=3",
        ])
        self.assert_setup_called_with(
            [node_dict_fixture(node)],
            transport_type="unknown",
            transport_options=dict(a="1"),
            link_list=[
                dict(b="2", c="3"),
            ]
        )

    def test_transport_with_unknown_keywords(self):
        node = "node"
        self.call_cmd(["node", "transport", "udp", "crypto", "a=1"])
        self.assert_setup_called_with(
            [node_dict_fixture(node)],
            transport_type="udp",
            crypto_options=dict(a="1"),
        )

    def test_transport_independent_options(self):
        node = "node"
        self.call_cmd([node, "quorum", "a=1", "b=2", "totem", "c=3", "a=2"])
        self.assert_setup_called_with(
            [node_dict_fixture(node)],
            quorum_options=dict(a="1", b="2"),
            totem_options=dict(c="3", a="2")
        )

    def test_knet_links(self):
        node = "node"
        self.call_cmd([
            node, "transport", "knet", "link", "c=3", "a=2", "link", "a=1",
        ])
        self.assert_setup_called_with(
            [node_dict_fixture(node)],
            transport_type="knet",
            link_list=[
                dict(c="3", a="2"),
                dict(a="1"),
            ]
        )

    def test_knet_links_repetable_correctly(self):
        node = "node"
        self.call_cmd([
            node, "transport", "knet", "link", "c=3", "a=2", "compression",
            "d=1", "e=1", "link", "a=1", "compression", "f=1"
        ])
        self.assert_setup_called_with(
            [node_dict_fixture(node)],
            transport_type="knet",
            link_list=[
                dict(c="3", a="2"),
                dict(a="1"),
            ],
            compression_options=dict(d="1", e="1", f="1"),
        )

    def test_transport_not_repeatable(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["node", "transport", "knet", "a=1", "transport", "knet"]
            )
        self.assertEqual(
            "'transport' cannot be used more than once", cm.exception.message
        )

    def test_totem_not_repeatable(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["node", "totem", "a=1", "b=1", "totem", "c=2"])
        self.assertEqual(
            "'totem' cannot be used more than once", cm.exception.message
        )

    def test_quorum_not_repeatable(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["node", "quorum", "a=1", "b=1", "quorum", "c=2"])
        self.assertEqual(
            "'quorum' cannot be used more than once", cm.exception.message
        )

    def test_full_knet(self):
        self.call_cmd([
            "node0", "node2", "addrs=addr0", "node1", "addrs=addr1,addr2",
            "totem", "a=1", "b=1", "quorum", "c=1", "d=1", "transport", "knet",
            "a=a", "b=b", "compression", "a=1", "b=2", "c=3", "crypto", "d=4",
            "e=5", "link", "aa=1", "link", "ba=1", "bb=2", "link", "ca=1",
            "cb=2", "cc=3"
        ])
        self.assert_setup_called_with(
            [
                node_dict_fixture("node0"),
                node_dict_fixture("node2", ["addr0"]),
                node_dict_fixture("node1", ["addr1", "addr2"]),
            ],
            totem_options=dict(a="1", b="1"),
            quorum_options=dict(c="1", d="1"),
            transport_type="knet",
            transport_options=dict(a="a", b="b"),
            compression_options=dict(a="1", b="2", c="3"),
            crypto_options=dict(d="4", e="5"),
            link_list=[
                dict(aa="1"),
                dict(ba="1", bb="2"),
                dict(ca="1", cb="2", cc="3"),
            ],
        )

    def assert_with_all_options(self, transport_type):
        self.call_cmd([
            "node0", "node2", "addrs=addr0", "node1", "addrs=addr1,addr2",
            "totem", "a=1", "b=1", "quorum", "c=1", "d=1", "transport",
            transport_type, "a=a", "b=b", "link", "aa=1", "link", "ba=1",
            "bb=2",
        ])
        self.assert_setup_called_with(
            [
                node_dict_fixture("node0"),
                node_dict_fixture("node2", ["addr0"]),
                node_dict_fixture("node1", ["addr1", "addr2"]),
            ],
            totem_options=dict(a="1", b="1"),
            quorum_options=dict(c="1", d="1"),
            transport_type=transport_type,
            transport_options=dict(a="a", b="b"),
            link_list=[
                dict(aa="1"),
                dict(ba="1", bb="2"),
            ],
        )

    def test_full_udp(self):
        self.assert_with_all_options("udp")

    def test_full_udpu(self):
        self.assert_with_all_options("udpu")

    def test_enable(self):
        node_name = "node"
        self.call_cmd([node_name], {"enable": True})
        self.assert_setup_called_with(
            [node_dict_fixture(node_name)],
            enable=True
        )

    def test_start(self):
        node_name = "node"
        self.call_cmd([node_name], {"start": True})
        self.assert_setup_called_with(
            [node_dict_fixture(node_name)],
            start=True
        )

    def test_enable_start(self):
        node_name = "node"
        self.call_cmd([node_name], {"enable": True, "start": True})
        self.assert_setup_called_with(
            [node_dict_fixture(node_name)],
            enable=True,
            start=True
        )

    def test_wait(self):
        node_name = "node"
        self.call_cmd([node_name], {"wait": "10"})
        self.assert_setup_called_with(
            [node_dict_fixture(node_name)],
            wait="10"
        )

    def test_start_wait(self):
        node_name = "node"
        self.call_cmd([node_name], {"start": True, "wait": None})
        self.assert_setup_called_with(
            [node_dict_fixture(node_name)],
            start=True,
            wait=None
        )

    def test_start_wait_timeout(self):
        node_name = "node"
        self.call_cmd([node_name], {"start": True, "wait": "10"})
        self.assert_setup_called_with(
            [node_dict_fixture(node_name)],
            start=True,
            wait="10"
        )

    def test_force(self):
        node_name = "node"
        self.call_cmd([node_name], {"force": True})
        self.assert_setup_called_with(
            [node_dict_fixture(node_name)],
            force=True,
            force_unresolvable=True
        )

    def test_all_modifiers(self):
        node_name = "node"
        self.call_cmd(
            [node_name],
            {"force": True, "enable": True, "start": True, "wait": "15"}
        )
        self.assert_setup_called_with(
            [node_dict_fixture(node_name)],
            enable=True,
            start=True,
            wait="15",
            force=True,
            force_unresolvable=True
        )
