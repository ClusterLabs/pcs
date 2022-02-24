from functools import partial
from unittest import TestCase

from pcs_test.tools.assertions import (
    AssertPcsMixin,
    ac,
)
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_dir,
    get_tmp_file,
    skip_unless_root,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import (
    PcsRunner,
    pcs,
)


class UidGidTest(TestCase):
    # pylint: disable=invalid-name
    def setUp(self):
        self.uid_gid_dir = get_tmp_dir("tier1_cluster_uidgid")

    def tearDown(self):
        self.uid_gid_dir.cleanup()

    def testUIDGID(self):
        # pylint: disable=too-many-statements
        _pcs = partial(
            pcs,
            None,
            mock_settings={"corosync_uidgid_dir": self.uid_gid_dir.name},
        )
        o, r = _pcs("cluster uidgid".split())
        ac(o, "No uidgids configured\n")
        assert r == 0

        o, r = _pcs("cluster uidgid add".split())
        assert r == 1
        assert o.startswith("\nUsage:")

        o, r = _pcs("cluster uidgid rm".split())
        assert r == 1
        assert o.startswith(
            "Hint: This command has been replaced with 'pcs cluster uidgid "
            "delete', 'pcs cluster uidgid remove'."
        )

        o, r = _pcs("cluster uidgid xx".split())
        assert r == 1
        assert o.startswith("\nUsage:")

        o, r = _pcs("cluster uidgid add uid=testuid gid=testgid".split())
        assert r == 0
        ac(o, "")

        o, r = _pcs("cluster uidgid add uid=testuid gid=testgid".split())
        ac(
            o,
            "Error: uidgid file with uid=testuid and gid=testgid already "
            "exists\n",
        )
        assert r == 1

        o, r = _pcs("cluster uidgid delete uid=testuid2 gid=testgid2".split())
        assert r == 1
        ac(
            o,
            "Error: no uidgid files with uid=testuid2 and gid=testgid2 found\n",
        )

        o, r = _pcs("cluster uidgid remove uid=testuid gid=testgid2".split())
        assert r == 1
        ac(
            o,
            "Error: no uidgid files with uid=testuid and gid=testgid2 found\n",
        )

        o, r = _pcs("cluster uidgid rm uid=testuid2 gid=testgid".split())
        assert r == 1
        ac(
            o,
            "'pcs cluster uidgid rm' has been deprecated, use 'pcs cluster "
            "uidgid delete' or 'pcs cluster uidgid remove' instead\n"
            "Error: no uidgid files with uid=testuid2 and gid=testgid found\n",
        )

        o, r = _pcs("cluster uidgid".split())
        assert r == 0
        ac(o, "UID/GID: uid=testuid gid=testgid\n")

        o, r = _pcs("cluster uidgid delete uid=testuid gid=testgid".split())
        ac(o, "")
        assert r == 0

        o, r = _pcs("cluster uidgid add uid=testuid gid=testgid".split())
        assert r == 0
        ac(o, "")

        o, r = _pcs("cluster uidgid".split())
        assert r == 0
        ac(o, "UID/GID: uid=testuid gid=testgid\n")

        o, r = _pcs("cluster uidgid remove uid=testuid gid=testgid".split())
        ac(o, "")
        assert r == 0

        o, r = _pcs("cluster uidgid add uid=testuid gid=testgid".split())
        assert r == 0
        ac(o, "")

        o, r = _pcs("cluster uidgid".split())
        assert r == 0
        ac(o, "UID/GID: uid=testuid gid=testgid\n")

        o, r = _pcs("cluster uidgid rm uid=testuid gid=testgid".split())
        ac(
            o,
            "'pcs cluster uidgid rm' has been deprecated, use 'pcs cluster "
            "uidgid delete' or 'pcs cluster uidgid remove' instead\n",
        )
        assert r == 0

        o, r = _pcs("cluster uidgid".split())
        assert r == 0
        ac(o, "No uidgids configured\n")


class ClusterUpgradeTest(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_cluster_upgrade")
        write_file_to_tmpfile(rc("cib-empty-1.2.xml"), self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def test_cluster_upgrade(self):
        # pylint: disable=invalid-name
        self.temp_cib.seek(0)
        data = self.temp_cib.read()
        assert data.find("pacemaker-1.2") != -1
        assert data.find("pacemaker-2.") == -1

        o, r = pcs(self.temp_cib.name, "cluster cib-upgrade".split())
        ac(o, "Cluster CIB has been upgraded to latest version\n")
        assert r == 0

        self.temp_cib.seek(0)
        data = self.temp_cib.read()
        assert data.find("pacemaker-1.2") == -1
        assert data.find("pacemaker-2.") == -1
        assert data.find("pacemaker-3.") != -1

        o, r = pcs(self.temp_cib.name, "cluster cib-upgrade".split())
        ac(o, "Cluster CIB has been upgraded to latest version\n")
        assert r == 0


@skip_unless_root()
class ClusterStartStop(TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(cib_file=None)

    def test_all_and_nodelist(self):
        self.assert_pcs_fail(
            "cluster stop rh7-1 rh7-2 --all".split(),
            "Error: Cannot specify both --all and a list of nodes.\n",
        )
        self.assert_pcs_fail(
            "cluster start rh7-1 rh7-2 --all".split(),
            "Error: Cannot specify both --all and a list of nodes.\n",
        )


@skip_unless_root()
class ClusterEnableDisable(TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(cib_file=None)

    def test_all_and_nodelist(self):
        self.assert_pcs_fail(
            "cluster enable rh7-1 rh7-2 --all".split(),
            "Error: Cannot specify both --all and a list of nodes.\n",
        )
        self.assert_pcs_fail(
            "cluster disable rh7-1 rh7-2 --all".split(),
            "Error: Cannot specify both --all and a list of nodes.\n",
        )
