import os
import shutil
import unittest
from unittest import mock

from pcs.test.tools.assertions import (
    ac,
    AssertPcsMixin,
)
from pcs.test.tools.misc import (
    get_test_resource as rc,
    skip_unless_pacemaker_version,
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

class ClusterTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner( temp_cib, cluster_conf_file=cluster_conf_tmp
        )
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
            assert data.find("pacemaker-2.") == -1
            assert data.find("pacemaker-3.") != -1

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
class ClusterSetup(unittest.TestCase):
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
        cluster.cluster_setup(self.lib, argv, all_modifiers)

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
        self.call_cmd([node_name, "addr="])
        self.assert_setup_called_with([node_dict_fixture(node_name, [''])])

    def test_one_node_with_single_address(self):
        node_name = "node"
        addr = "node_addr"
        self.call_cmd([node_name, "addr={}".format(addr)])
        self.assert_setup_called_with([node_dict_fixture(node_name, [addr])])

    def test_one_node_with_multiple_addresses(self):
        node_name = "node"
        addr_list = ["addr{}".format(i) for i in range(3)]
        self.call_cmd([node_name] + [f"addr={addr}" for addr in addr_list])
        self.assert_setup_called_with([node_dict_fixture(node_name, addr_list)])

    def test_node_unknown_options(self):
        node_name = "node"
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                [node_name, "unknown=option", "another=one", "addr=addr"]
            )
        self.assertEqual(
            "Unknown options {} for node '{}'".format(
                ", ".join(sorted(["unknown", "another"])), node_name
            ),
            cm.exception.message,
        )

    def test_multiple_nodes(self):
        self.call_cmd(
            ["node1", "addr=addr1", "addr=addr2", "node2", "node3", "addr=addr"]
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
            "node0", "node2", "addr=addr0", "node1", "addr=addr1", "addr=addr2",
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
            "node0", "node2", "addr=addr0", "node1", "addr=addr1", "addr=addr2",
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
