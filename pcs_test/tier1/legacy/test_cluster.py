import os
from functools import partial
from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_dir,
    get_tmp_file,
    outdent,
    read_test_resource,
    skip_unless_root,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import (
    PcsRunner,
    pcs,
)


class UidGidTest(TestCase):
    def setUp(self):
        self.uid_gid_dir = get_tmp_dir("tier1_cluster_uidgid")
        self._pcs = partial(
            pcs,
            None,
            mock_settings={"corosync_uidgid_dir": self.uid_gid_dir.name},
        )

    def tearDown(self):
        self.uid_gid_dir.cleanup()

    def assert_uidgid_file_content(self, filename, content):
        self.assertEqual(
            read_test_resource(os.path.join(self.uid_gid_dir.name, filename)),
            content,
        )

    def assert_uidgid_file_removed(self, filename):
        self.assertEqual(
            os.path.isfile(os.path.join(self.uid_gid_dir.name, filename)),
            False,
        )

    def test_uidgid(self):
        # pylint: disable=too-many-statements
        stdout, stderr, retval = self._pcs("cluster uidgid".split())
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "No uidgids configured\n")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = self._pcs("cluster uidgid add".split())
        self.assertEqual(stdout, "")
        self.assertTrue(stderr.startswith("\nUsage:"))
        self.assertEqual(retval, 1)

        stdout, stderr, retval = self._pcs("cluster uidgid rm".split())
        self.assertEqual(stdout, "")
        self.assertTrue(
            stderr.startswith(
                "Error: This command has been replaced with 'pcs cluster uidgid "
                "delete', 'pcs cluster uidgid remove'."
            )
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = self._pcs("cluster uidgid xx".split())
        self.assertEqual(stdout, "")
        self.assertTrue(stderr.startswith("\nUsage:"))
        self.assertEqual(retval, 1)

        stdout, stderr, retval = self._pcs(
            "cluster uidgid add uid=testuid gid=testgid".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        self.assert_uidgid_file_content(
            "pcs-uidgid-testuid-testgid",
            outdent(
                """\
                uidgid {
                  uid: testuid
                  gid: testgid
                }
                """
            ),
        )

        stdout, stderr, retval = self._pcs(
            "cluster uidgid add uid=testuid gid=testgid".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            "Error: uidgid file with uid=testuid and gid=testgid already "
            "exists\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = self._pcs(
            "cluster uidgid delete uid=testuid2 gid=testgid2".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            "Error: no uidgid files with uid=testuid2 and gid=testgid2 found\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = self._pcs(
            "cluster uidgid remove uid=testuid gid=testgid2".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            "Error: no uidgid files with uid=testuid and gid=testgid2 found\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = self._pcs(
            "cluster uidgid rm uid=testuid2 gid=testgid".split()
        )
        self.assertEqual(stdout, "")
        self.assertTrue(
            stderr.startswith(
                "Error: This command has been replaced with 'pcs cluster uidgid "
                "delete', 'pcs cluster uidgid remove'."
            )
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = self._pcs("cluster uidgid".split())
        self.assertEqual(stdout, "UID/GID: uid=testuid gid=testgid\n")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = self._pcs(
            "cluster uidgid delete uid=testuid gid=testgid".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        self.assert_uidgid_file_removed("pcs-uidgid-testuid-testgid")

        stdout, stderr, retval = self._pcs(
            "cluster uidgid add uid=testuid gid=testgid".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = self._pcs("cluster uidgid".split())
        self.assertEqual(stdout, "UID/GID: uid=testuid gid=testgid\n")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = self._pcs(
            "cluster uidgid remove uid=testuid gid=testgid".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = self._pcs(
            "cluster uidgid add uid=testuid gid=testgid".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        self.assert_uidgid_file_content(
            "pcs-uidgid-testuid-testgid",
            outdent(
                """\
                uidgid {
                  uid: testuid
                  gid: testgid
                }
                """
            ),
        )

        stdout, stderr, retval = self._pcs("cluster uidgid".split())
        self.assertEqual(stdout, "UID/GID: uid=testuid gid=testgid\n")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = self._pcs(
            "cluster uidgid delete uid=testuid gid=testgid".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        self.assert_uidgid_file_removed("pcs-uidgid-testuid-testgid")

        stdout, stderr, retval = self._pcs("cluster uidgid".split())
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "No uidgids configured\n")
        self.assertEqual(retval, 0)

    def test_missing_uid_gid(self):
        stdout, stderr, retval = self._pcs(
            "cluster uidgid add uid=1000".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        self.assert_uidgid_file_content(
            "pcs-uidgid-1000-",
            outdent(
                """\
                uidgid {
                  uid: 1000
                }
                """
            ),
        )

        stdout, stderr, retval = self._pcs(
            "cluster uidgid add gid=1001".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        self.assert_uidgid_file_content(
            "pcs-uidgid--1001",
            outdent(
                """\
                uidgid {
                  gid: 1001
                }
                """
            ),
        )

        stdout, stderr, retval = self._pcs("cluster uidgid".split())
        self.assertEqual(
            stdout,
            outdent(
                """\
                UID/GID: uid= gid=1001
                UID/GID: uid=1000 gid=
                """
            ),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = self._pcs(
            "cluster uidgid delete uid=1000".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        self.assert_uidgid_file_removed("pcs-uidgid-1000-")

        stdout, stderr, retval = self._pcs(
            "cluster uidgid delete gid=1001".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        self.assert_uidgid_file_removed("pcs-uidgid--1001")

        stdout, stderr, retval = self._pcs("cluster uidgid".split())
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "No uidgids configured\n")
        self.assertEqual(retval, 0)


class ClusterUpgradeTest(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_cluster_upgrade")
        write_file_to_tmpfile(rc("cib-empty-1.2.xml"), self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def test_cluster_upgrade(self):
        self.temp_cib.seek(0)
        data = self.temp_cib.read()
        assert data.find("pacemaker-1.2") != -1
        assert data.find("pacemaker-2.") == -1

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "cluster cib-upgrade".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr, "Cluster CIB has been upgraded to latest version\n"
        )
        self.assertEqual(retval, 0)

        self.temp_cib.seek(0)
        data = self.temp_cib.read()
        assert data.find("pacemaker-1.2") == -1
        assert data.find("pacemaker-2.") == -1
        assert data.find("pacemaker-3.") != -1

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "cluster cib-upgrade".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr, "Cluster CIB has been upgraded to latest version\n"
        )
        self.assertEqual(retval, 0)


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
