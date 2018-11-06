import shutil
import unittest

from pcs.test.tools.assertions import (
    ac,
    AssertPcsMixin,
)
from pcs.test.tools.misc import (
    get_test_resource as rc,
    skip_unless_pacemaker_version,
)
from pcs.test.tools.pcs_runner import (
    pcs,
    PcsRunner,
)

# pylint: disable=too-many-public-methods, invalid-name, no-self-use, bad-whitespace, line-too-long, too-many-statements

old_cib = rc("cib-empty-1.2.xml")
empty_cib = rc("cib-empty.xml")
temp_cib = rc("temp-cib.xml")

class ACLTest(unittest.TestCase, AssertPcsMixin):
    pcs_runner = None
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    @skip_unless_pacemaker_version((2, 0, 0), "CIB schema upgrade")
    def testAutoUpgradeofCIB(self):
        shutil.copy(old_cib, temp_cib)

        self.assert_pcs_success(
            'acl show',
            "ACLs are disabled, run 'pcs acl enable' to enable"
            "\n\nCIB has been upgraded to the latest schema version.\n"
        )

        with open(temp_cib) as myfile:
            data = myfile.read()
            assert data.find("pacemaker-1.2") == -1
            assert data.find("pacemaker-2.") == -1
            assert data.find("pacemaker-3.") != -1

    def testEnableDisable(self):
        o,r = pcs(temp_cib, "acl disable")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl")
        assert r == 0
        ac(o,"ACLs are disabled, run 'pcs acl enable' to enable\n\n")

        o,r = pcs(temp_cib, "acl enable")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl")
        assert r == 0
        ac(o,"ACLs are enabled\n\n")

        o,r = pcs(temp_cib, "acl disable")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl")
        assert r == 0
        ac(o,"ACLs are disabled, run 'pcs acl enable' to enable\n\n")

    def testUserGroupCreateDeleteWithRoles(self):
        o,r = pcs(temp_cib, "acl role create role1 read xpath /xpath1/ write xpath /xpath2/")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl role create role2 deny xpath /xpath3/ deny xpath /xpath4/")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl role create role3 read xpath /xpath5/ read xpath /xpath6/")
        assert r == 0
        ac(o,"")

        o, r = pcs(temp_cib, "acl user create user1 roleX")
        ac(o, "Error: ACL role 'roleX' does not exist\n")
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl user create user1 role1 roleX")
        ac(o, "Error: ACL role 'roleX' does not exist\n")
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl group create group1 roleX")
        ac(o, "Error: ACL role 'roleX' does not exist\n")
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl group create group1 role1 roleX")
        ac(o, "Error: ACL role 'roleX' does not exist\n")
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl")
        ac(o, """\
ACLs are disabled, run 'pcs acl enable' to enable

Role: role1
  Permission: read xpath /xpath1/ (role1-read)
  Permission: write xpath /xpath2/ (role1-write)
Role: role2
  Permission: deny xpath /xpath3/ (role2-deny)
  Permission: deny xpath /xpath4/ (role2-deny-1)
Role: role3
  Permission: read xpath /xpath5/ (role3-read)
  Permission: read xpath /xpath6/ (role3-read-1)
""")
        self.assertEqual(0, r)

        o,r = pcs(temp_cib, "acl user create user1 role1 role2")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl group create group1 role1 role3")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl")
        assert r == 0
        ac(
            o,
            """\
ACLs are disabled, run 'pcs acl enable' to enable

User: user1
  Roles: role1 role2
Group: group1
  Roles: role1 role3
Role: role1
  Permission: read xpath /xpath1/ (role1-read)
  Permission: write xpath /xpath2/ (role1-write)
Role: role2
  Permission: deny xpath /xpath3/ (role2-deny)
  Permission: deny xpath /xpath4/ (role2-deny-1)
Role: role3
  Permission: read xpath /xpath5/ (role3-read)
  Permission: read xpath /xpath6/ (role3-read-1)
"""
        )

        o,r = pcs(temp_cib, "acl role create group1")
        assert r == 1
        ac(o,"Error: 'group1' already exists\n")

        o,r = pcs(temp_cib, "acl role create role1")
        assert r == 1
        ac(o,"Error: 'role1' already exists\n")

        o,r = pcs(temp_cib, "acl user create user1")
        assert r == 1
        ac(o,"Error: 'user1' already exists\n")

        o,r = pcs(temp_cib, "acl group create group1")
        assert r == 1
        ac(o,"Error: 'group1' already exists\n")

        o,r = pcs(temp_cib, "acl group create role1")
        assert r == 1
        ac(o,"Error: 'role1' already exists\n")

        o,r = pcs(temp_cib, "acl role assign role1 to noexist")
        assert r == 1
        ac(o,"Error: ACL group/ACL user 'noexist' does not exist\n")

        o,r = pcs(temp_cib, "acl role assign noexist to user1")
        assert r == 1
        ac(o,"Error: ACL role 'noexist' does not exist\n")

        o,r = pcs(temp_cib, "acl role assign role3 to user1")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl")
        assert r == 0
        ac(o,"ACLs are disabled, run 'pcs acl enable' to enable\n\nUser: user1\n  Roles: role1 role2 role3\nGroup: group1\n  Roles: role1 role3\nRole: role1\n  Permission: read xpath /xpath1/ (role1-read)\n  Permission: write xpath /xpath2/ (role1-write)\nRole: role2\n  Permission: deny xpath /xpath3/ (role2-deny)\n  Permission: deny xpath /xpath4/ (role2-deny-1)\nRole: role3\n  Permission: read xpath /xpath5/ (role3-read)\n  Permission: read xpath /xpath6/ (role3-read-1)\n")

        o,r = pcs(temp_cib, "acl role unassign noexist from user1")
        assert r == 1
        ac(o,"Error: Role 'noexist' is not assigned to 'user1'\n")

        o,r = pcs(temp_cib, "acl role unassign role3 from noexist")
        assert r == 1
        ac(o,"Error: ACL group/ACL user 'noexist' does not exist\n")

        o,r = pcs(temp_cib, "acl role unassign role3 from user1")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl")
        assert r == 0
        ac(o,"ACLs are disabled, run 'pcs acl enable' to enable\n\nUser: user1\n  Roles: role1 role2\nGroup: group1\n  Roles: role1 role3\nRole: role1\n  Permission: read xpath /xpath1/ (role1-read)\n  Permission: write xpath /xpath2/ (role1-write)\nRole: role2\n  Permission: deny xpath /xpath3/ (role2-deny)\n  Permission: deny xpath /xpath4/ (role2-deny-1)\nRole: role3\n  Permission: read xpath /xpath5/ (role3-read)\n  Permission: read xpath /xpath6/ (role3-read-1)\n")

        o,r = pcs(temp_cib, "acl role unassign role2 from user1")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl role unassign role1 from user1")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl")
        ac(o, """\
ACLs are disabled, run 'pcs acl enable' to enable

User: user1
  Roles:
Group: group1
  Roles: role1 role3
Role: role1
  Permission: read xpath /xpath1/ (role1-read)
  Permission: write xpath /xpath2/ (role1-write)
Role: role2
  Permission: deny xpath /xpath3/ (role2-deny)
  Permission: deny xpath /xpath4/ (role2-deny-1)
Role: role3
  Permission: read xpath /xpath5/ (role3-read)
  Permission: read xpath /xpath6/ (role3-read-1)
""")
        assert r == 0

        o,r = pcs(temp_cib, "acl role delete role3")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl")
        ac(o, """\
ACLs are disabled, run 'pcs acl enable' to enable

User: user1
  Roles:
Group: group1
  Roles: role1
Role: role1
  Permission: read xpath /xpath1/ (role1-read)
  Permission: write xpath /xpath2/ (role1-write)
Role: role2
  Permission: deny xpath /xpath3/ (role2-deny)
  Permission: deny xpath /xpath4/ (role2-deny-1)
""")
        assert r == 0

        o,r = pcs(temp_cib, "acl role assign role2 to user1")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl")
        assert r == 0
        ac(o,"ACLs are disabled, run 'pcs acl enable' to enable\n\nUser: user1\n  Roles: role2\nGroup: group1\n  Roles: role1\nRole: role1\n  Permission: read xpath /xpath1/ (role1-read)\n  Permission: write xpath /xpath2/ (role1-write)\nRole: role2\n  Permission: deny xpath /xpath3/ (role2-deny)\n  Permission: deny xpath /xpath4/ (role2-deny-1)\n")

        o,r = pcs(temp_cib, "acl role assign role1 user1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl")
        ac(o, """\
ACLs are disabled, run 'pcs acl enable' to enable

User: user1
  Roles: role2 role1
Group: group1
  Roles: role1
Role: role1
  Permission: read xpath /xpath1/ (role1-read)
  Permission: write xpath /xpath2/ (role1-write)
Role: role2
  Permission: deny xpath /xpath3/ (role2-deny)
  Permission: deny xpath /xpath4/ (role2-deny-1)
""")
        assert r == 0

        o,r = pcs(temp_cib, "acl role unassign role2 from user1 --autodelete")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl")
        ac(o, """\
ACLs are disabled, run 'pcs acl enable' to enable

User: user1
  Roles: role1
Group: group1
  Roles: role1
Role: role1
  Permission: read xpath /xpath1/ (role1-read)
  Permission: write xpath /xpath2/ (role1-write)
Role: role2
  Permission: deny xpath /xpath3/ (role2-deny)
  Permission: deny xpath /xpath4/ (role2-deny-1)
""")
        assert r == 0

        o,r = pcs(temp_cib, "acl role unassign role1 from user1 --autodelete")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl")
        ac(o, """\
ACLs are disabled, run 'pcs acl enable' to enable

Group: group1
  Roles: role1
Role: role1
  Permission: read xpath /xpath1/ (role1-read)
  Permission: write xpath /xpath2/ (role1-write)
Role: role2
  Permission: deny xpath /xpath3/ (role2-deny)
  Permission: deny xpath /xpath4/ (role2-deny-1)
""")
        assert r == 0

        o,r = pcs(temp_cib, "acl user create user1 role1 role2")
        ac(o, "")
        assert r == 0

        o,r = pcs(temp_cib, "acl")
        ac(o, """\
ACLs are disabled, run 'pcs acl enable' to enable

User: user1
  Roles: role1 role2
Group: group1
  Roles: role1
Role: role1
  Permission: read xpath /xpath1/ (role1-read)
  Permission: write xpath /xpath2/ (role1-write)
Role: role2
  Permission: deny xpath /xpath3/ (role2-deny)
  Permission: deny xpath /xpath4/ (role2-deny-1)
""")
        assert r == 0

        o,r = pcs(temp_cib, "acl role delete role1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl")
        ac(o, """\
ACLs are disabled, run 'pcs acl enable' to enable

User: user1
  Roles: role2
Role: role2
  Permission: deny xpath /xpath3/ (role2-deny)
  Permission: deny xpath /xpath4/ (role2-deny-1)
""")
        assert r == 0

    def testUserGroupCreateDelete(self):
        o,r = pcs(temp_cib, "acl")
        assert r == 0
        ac(o,"ACLs are disabled, run 'pcs acl enable' to enable\n\n")

        o,r = pcs(temp_cib, "acl user create user1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl user create user2")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl user create user1")
        assert r == 1
        ac(o,"Error: 'user1' already exists\n")

        o,r = pcs(temp_cib, "acl group create group1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl group create group2")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl group create group1")
        assert r == 1
        ac(o,"Error: 'group1' already exists\n")

        o,r = pcs(temp_cib, "acl")
        ac(o,"""\
ACLs are disabled, run 'pcs acl enable' to enable

User: user1
  Roles:
User: user2
  Roles:
Group: group1
  Roles:
Group: group2
  Roles:
""")
        assert r == 0

        o,r = pcs(temp_cib, "acl group delete user1")
        assert r == 1
        ac(o,"Error: 'user1' is not an ACL group\n")

        o,r = pcs(temp_cib, "acl")
        ac(o, """\
ACLs are disabled, run 'pcs acl enable' to enable

User: user1
  Roles:
User: user2
  Roles:
Group: group1
  Roles:
Group: group2
  Roles:
""")
        assert r == 0

        o,r = pcs(temp_cib, "acl group delete group2")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl")
        ac(o, """\
ACLs are disabled, run 'pcs acl enable' to enable

User: user1
  Roles:
User: user2
  Roles:
Group: group1
  Roles:
""")
        assert r == 0

        o,r = pcs(temp_cib, "acl group remove group1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl")
        ac(o, """\
ACLs are disabled, run 'pcs acl enable' to enable

User: user1
  Roles:
User: user2
  Roles:
""")
        assert r == 0

        o,r = pcs(temp_cib, "acl user delete user1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl")
        ac(o, """\
ACLs are disabled, run 'pcs acl enable' to enable

User: user2
  Roles:
""")
        assert r == 0

        o,r = pcs(temp_cib, "acl user remove user2")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl")
        assert r == 0
        ac(o,"ACLs are disabled, run 'pcs acl enable' to enable\n\n")

    def testRoleCreateDelete(self):
        o, r = pcs(temp_cib, "acl role create role0 read")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 read //resources")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 read xpath")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 read id")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 readX xpath //resources")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 read xpathX //resources")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 description=test read")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 description=test read //resources")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 description=test read xpath")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 description=test read id")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib,
            "acl role create role0 description=test readX xpath //resources"
        )
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib,
            "acl role create role0 description=test read xpathX //resources"
        )
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 desc=test read")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 desc=test read //resources")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 desc=test read xpath")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 desc=test read id")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 desc=test readX xpath //resources")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl role create role0 desc=test read xpathX //resources")
        self.assertTrue(o.startswith("\nUsage: pcs acl role create..."))
        self.assertEqual(1, r)

        o,r = pcs(temp_cib, "acl")
        ac(o, "ACLs are disabled, run 'pcs acl enable' to enable\n\n")
        self.assertEqual(0, r)

        o,r = pcs(temp_cib, "acl role create role0")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl role create role0")
        ac(o,"Error: 'role0' already exists\n")
        assert r == 1

        o,r = pcs(temp_cib, "acl role create role0d description='empty role'")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl role create role1 read xpath /xpath/")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl role create role2 description='with description' READ XPATH /xpath/")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl role create role3 Read XPath /xpath_query/ wRiTe xpATH /xpath_query2/ deny xpath /xpath_query3/")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl")
        ac(o,"ACLs are disabled, run 'pcs acl enable' to enable\n\nRole: role0\nRole: role0d\n  Description: empty role\nRole: role1\n  Permission: read xpath /xpath/ (role1-read)\nRole: role2\n  Description: with description\n  Permission: read xpath /xpath/ (role2-read)\nRole: role3\n  Permission: read xpath /xpath_query/ (role3-read)\n  Permission: write xpath /xpath_query2/ (role3-write)\n  Permission: deny xpath /xpath_query3/ (role3-deny)\n")
        assert r == 0

        o,r = pcs(temp_cib, "acl role delete role2")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl")
        ac(o,"ACLs are disabled, run 'pcs acl enable' to enable\n\nRole: role0\nRole: role0d\n  Description: empty role\nRole: role1\n  Permission: read xpath /xpath/ (role1-read)\nRole: role3\n  Permission: read xpath /xpath_query/ (role3-read)\n  Permission: write xpath /xpath_query2/ (role3-write)\n  Permission: deny xpath /xpath_query3/ (role3-deny)\n")
        assert r == 0

        o,r = pcs(temp_cib, "acl role delete role2")
        assert r == 1
        ac(o,"Error: ACL role 'role2' does not exist\n")

        o,r = pcs(temp_cib, "acl role delete role1")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl role remove role3")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl role remove role0")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl role remove role0d")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "acl")
        ac(o,"ACLs are disabled, run 'pcs acl enable' to enable\n\n")
        assert r == 0

    def testPermissionAddDelete(self):
        o,r = pcs(temp_cib, "acl role create role1 read xpath /xpath1/ write xpath /xpath2/")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl role create role2 read xpath /xpath3/ write xpath /xpath4/")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl role create role3 read xpath /xpath5/ write xpath /xpath6/")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl show")
        assert r == 0
        ac(o,"ACLs are disabled, run 'pcs acl enable' to enable\n\nRole: role1\n  Permission: read xpath /xpath1/ (role1-read)\n  Permission: write xpath /xpath2/ (role1-write)\nRole: role2\n  Permission: read xpath /xpath3/ (role2-read)\n  Permission: write xpath /xpath4/ (role2-write)\nRole: role3\n  Permission: read xpath /xpath5/ (role3-read)\n  Permission: write xpath /xpath6/ (role3-write)\n")

        o,r = pcs(temp_cib, "acl permission add role1 deny xpath /myxpath1/")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl permission add role4 deny xpath /myxpath2/")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl show")
        assert r == 0
        ac(o,"ACLs are disabled, run 'pcs acl enable' to enable\n\nRole: role1\n  Permission: read xpath /xpath1/ (role1-read)\n  Permission: write xpath /xpath2/ (role1-write)\n  Permission: deny xpath /myxpath1/ (role1-deny)\nRole: role2\n  Permission: read xpath /xpath3/ (role2-read)\n  Permission: write xpath /xpath4/ (role2-write)\nRole: role3\n  Permission: read xpath /xpath5/ (role3-read)\n  Permission: write xpath /xpath6/ (role3-write)\nRole: role4\n  Permission: deny xpath /myxpath2/ (role4-deny)\n")

        o,r = pcs(temp_cib, "acl permission delete role4-deny")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl permission delete role4-deny")
        ac(o,"Error: ACL permission 'role4-deny' does not exist\n")
        assert r == 1

        o,r = pcs(temp_cib, "acl permission remove role4-deny")
        ac(o,"Error: ACL permission 'role4-deny' does not exist\n")
        assert r == 1

        o,r = pcs(temp_cib, "acl show")
        assert r == 0
        ac(o,"ACLs are disabled, run 'pcs acl enable' to enable\n\nRole: role1\n  Permission: read xpath /xpath1/ (role1-read)\n  Permission: write xpath /xpath2/ (role1-write)\n  Permission: deny xpath /myxpath1/ (role1-deny)\nRole: role2\n  Permission: read xpath /xpath3/ (role2-read)\n  Permission: write xpath /xpath4/ (role2-write)\nRole: role3\n  Permission: read xpath /xpath5/ (role3-read)\n  Permission: write xpath /xpath6/ (role3-write)\nRole: role4\n")

        o,r = pcs(temp_cib, "acl permission delete role3-read")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl permission delete role3-write")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "acl")
        ac(o,"ACLs are disabled, run 'pcs acl enable' to enable\n\nRole: role1\n  Permission: read xpath /xpath1/ (role1-read)\n  Permission: write xpath /xpath2/ (role1-write)\n  Permission: deny xpath /myxpath1/ (role1-deny)\nRole: role2\n  Permission: read xpath /xpath3/ (role2-read)\n  Permission: write xpath /xpath4/ (role2-write)\nRole: role3\nRole: role4\n")
        assert r == 0

        o, r = pcs(temp_cib, "acl permission remove role1-read")
        ac(o, "")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "acl permission remove role1-write")
        ac(o, "")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "acl permission remove role1-deny")
        ac(o, "")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "acl permission remove role2-read")
        ac(o, "")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "acl permission remove role2-write")
        ac(o, "")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "acl")
        ac(o, """\
ACLs are disabled, run 'pcs acl enable' to enable

Role: role1
Role: role2
Role: role3
Role: role4
""")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "acl permission add role1 read")
        self.assertTrue(o.startswith("\nUsage: pcs acl permission add..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl permission add role1 read //resources")
        self.assertTrue(o.startswith("\nUsage: pcs acl permission add..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl permission add role1 read xpath")
        self.assertTrue(o.startswith("\nUsage: pcs acl permission add..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl permission add role1 read id")
        self.assertTrue(o.startswith("\nUsage: pcs acl permission add..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl permission add role1 readX xpath //resources")
        self.assertTrue(o.startswith("\nUsage: pcs acl permission add..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl permission add role1 read xpathX //resources")
        self.assertTrue(o.startswith("\nUsage: pcs acl permission add..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl permission add role1 read id dummy read")
        self.assertTrue(o.startswith("\nUsage: pcs acl permission add..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl permission add role1 read id dummy read //resources")
        self.assertTrue(o.startswith("\nUsage: pcs acl permission add..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl permission add role1 read id dummy read xpath")
        self.assertTrue(o.startswith("\nUsage: pcs acl permission add..."))
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "acl permission add role1 read id dummy read id")
        self.assertTrue(o.startswith("\nUsage: pcs acl permission add..."))
        self.assertEqual(1, r)

        self.assert_pcs_fail(
          "acl permission add role1 read id dummy readX xpath //resources",
          stdout_start='\nUsage: pcs acl permission add...'
        )

        self.assert_pcs_fail(
          "acl permission add role1 read id dummy read xpathX //resources",
          stdout_start='\nUsage: pcs acl permission add...'
        )

        o, r = pcs(temp_cib, "acl")
        ac(o, """\
ACLs are disabled, run 'pcs acl enable' to enable

Role: role1
Role: role2
Role: role3
Role: role4
""")
        self.assertEqual(0, r)

    def test_can_add_permission_for_existing_id(self):
        self.assert_pcs_success('acl role create role1')
        self.assert_pcs_success('acl role create role2')
        self.assert_pcs_success("acl permission add role1 read id role2")

    def test_can_add_permission_for_existing_xpath(self):
        self.assert_pcs_success('acl role create role1')
        self.assert_pcs_success("acl permission add role1 read xpath //nodes")

    def test_can_not_add_permission_for_nonexisting_id(self):
        self.assert_pcs_success('acl role create role1')
        self.assert_pcs_fail(
            "acl permission add role1 read id non-existent-id",
            "Error: id 'non-existent-id' does not exist\n"
        )

    def test_can_not_add_permission_for_nonexisting_id_in_later_part(self):
        self.assert_pcs_success('acl role create role1')
        self.assert_pcs_success('acl role create role2')
        self.assert_pcs_fail(
            "acl permission add role1 read id role2 read id non-existent-id",
            "Error: id 'non-existent-id' does not exist\n"
        )

    def test_can_not_add_permission_for_nonexisting_role_with_bad_id(self):
        self.assert_pcs_success('acl role create role1')
        self.assert_pcs_fail(
            'acl permission add #bad-name read id role1',
            "Error: invalid ACL role '#bad-name'"
            +", '#' is not a valid first character for a ACL role\n"
        )

    def test_can_create_role_with_permission_for_existing_id(self):
        self.assert_pcs_success('acl role create role2')
        self.assert_pcs_success('acl role create role1 read id role2')

    def test_can_not_crate_role_with_permission_for_nonexisting_id(self):
        self.assert_pcs_fail(
            "acl role create role1 read id non-existent-id",
            "Error: id 'non-existent-id' does not exist\n"
        )

    def test_can_not_create_role_with_bad_name(self):
        self.assert_pcs_fail(
            'acl role create #bad-name',
            "Error: invalid ACL role '#bad-name'"
            +", '#' is not a valid first character for a ACL role\n"
        )

    def test_fail_on_unknown_role_method(self):
        self.assert_pcs_fail(
            'acl role unknown whatever',
            stdout_start="\nUsage: pcs acl role..."
        )

    def test_assign_unassign_role_to_user(self):
        self.assert_pcs_success("acl role create role1")
        self.assert_pcs_success("acl user create user1")
        self.assert_pcs_success("acl role assign role1 user user1")
        self.assert_pcs_fail(
            "acl role assign role1 user user1",
            "Error: Role 'role1' is already asigned to 'user1'\n"
        )
        self.assert_pcs_success("acl role unassign role1 user user1")
        self.assert_pcs_fail(
            "acl role unassign role1 user user1",
            "Error: Role 'role1' is not assigned to 'user1'\n"
        )

    def test_assign_unassign_role_to_user_not_existing_user(self):
        self.assert_pcs_success("acl role create role1")
        self.assert_pcs_success("acl group create group1")
        self.assert_pcs_fail(
            "acl role assign role1 to user group1",
            "Error: 'group1' is not an ACL user\n"
        )

    def test_assign_unassign_role_to_user_with_to(self):
        self.assert_pcs_success("acl role create role1")
        self.assert_pcs_success("acl user create user1")
        self.assert_pcs_success("acl role assign role1 to user user1")
        self.assert_pcs_fail(
            "acl role assign role1 to user user1",
            "Error: Role 'role1' is already asigned to 'user1'\n"
        )
        self.assert_pcs_success("acl role unassign role1 from user user1")
        self.assert_pcs_fail(
            "acl role unassign role1 from user user1",
            "Error: Role 'role1' is not assigned to 'user1'\n"
        )

    def test_assign_unassign_role_to_group(self):
        self.assert_pcs_success("acl role create role1")
        self.assert_pcs_success("acl group create group1")
        self.assert_pcs_success("acl role assign role1 group group1")
        self.assert_pcs_fail(
            "acl role assign role1 group group1",
            "Error: Role 'role1' is already asigned to 'group1'\n"
        )
        self.assert_pcs_success("acl role unassign role1 group group1")
        self.assert_pcs_fail(
            "acl role unassign role1 group group1",
            "Error: Role 'role1' is not assigned to 'group1'\n"
        )

    def test_assign_unassign_role_to_group_not_existing_group(self):
        self.assert_pcs_success("acl role create role1")
        self.assert_pcs_success("acl user create user1")
        self.assert_pcs_fail(
            "acl role assign role1 to group user1",
            "Error: 'user1' is not an ACL group\n"
        )

    def test_assign_unassign_role_to_group_with_to(self):
        self.assert_pcs_success("acl role create role1")
        self.assert_pcs_success("acl group create group1")
        self.assert_pcs_success("acl role assign role1 to group group1")
        self.assert_pcs_fail(
            "acl role assign role1 to group group1",
            "Error: Role 'role1' is already asigned to 'group1'\n"
        )
        self.assert_pcs_success("acl role unassign role1 from group group1")
        self.assert_pcs_fail(
            "acl role unassign role1 from group group1",
            "Error: Role 'role1' is not assigned to 'group1'\n"
        )
