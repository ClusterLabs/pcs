import os
import re
from functools import partial
from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import compare_version
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
from pcs_test.tools.xml import str_to_etree


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
        def extract_version(string_value):
            match = re.match(
                r"^pacemaker-(?P<major>\d+)\.(?P<minor>\d+)(\.(?P<rev>\d+))?$",
                string_value,
            )
            return (
                int(match.group("major")),
                int(match.group("minor")),
                int(match.group("rev")) if match.group("rev") else 0,
            )

        self.temp_cib.seek(0)
        cib = str_to_etree(self.temp_cib.read())
        validate_with = cib.getroottree().getroot().get("validate-with")
        self.assertEqual(validate_with, "pacemaker-1.2")
        version_before = extract_version(validate_with)
        self.assertEqual(version_before, (1, 2, 0))

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "cluster cib-upgrade".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr, "Cluster CIB has been upgraded to latest version\n"
        )
        self.assertEqual(retval, 0)

        self.temp_cib.seek(0)
        cib = str_to_etree(self.temp_cib.read())
        validate_with = cib.getroottree().getroot().get("validate-with")
        version_after = extract_version(validate_with)
        self.assertEqual(compare_version(version_before, version_after), -1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "cluster cib-upgrade".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr, "Cluster CIB has been upgraded to latest version\n"
        )
        self.assertEqual(retval, 0)

        self.temp_cib.seek(0)
        cib = str_to_etree(self.temp_cib.read())
        validate_with = cib.getroottree().getroot().get("validate-with")
        version_after2 = extract_version(validate_with)
        self.assertEqual(compare_version(version_after, version_after2), 0)


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
