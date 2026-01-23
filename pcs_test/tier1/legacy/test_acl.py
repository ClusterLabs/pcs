from textwrap import dedent
from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner

empty_cib = rc("cib-empty.xml")

AMBIGUOUS_ASSIGN_DEPRECATED = (
    "Deprecation Warning: Assigning / unassigning a role to a user / group "
    "without specifying 'user' or 'group' keyword is deprecated and might be "
    "removed in a future release.\n"
)
AUTODELETE_DEPRECATED = (
    "Deprecation Warning: Flag '--autodelete' is deprecated and might be "
    "removed in a future release.\n"
)
ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)


class ACLTest(TestCase, AssertPcsMixin):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_acl")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def test_enable_disable(self):
        self.assert_pcs_success("acl disable".split())
        self.assert_pcs_success(
            ["acl"],
            "ACLs are disabled, run 'pcs acl enable' to enable\n\n",
        )
        self.assert_pcs_success("acl enable".split())
        self.assert_pcs_success(
            ["acl"],
            "ACLs are enabled\n\n",
        )
        self.assert_pcs_success("acl disable".split())
        self.assert_pcs_success(
            ["acl"],
            "ACLs are disabled, run 'pcs acl enable' to enable\n\n",
        )

    def test_user_group_create_delete_with_roles(self):
        self.assert_pcs_success(
            "acl role create role1 read xpath /xpath1/ write xpath /xpath2/".split()
        )
        self.assert_pcs_success(
            "acl role create role2 deny xpath /xpath3/ deny xpath /xpath4/".split()
        )
        self.assert_pcs_success(
            "acl role create role3 read xpath /xpath5/ read xpath /xpath6/".split()
        )
        self.assert_pcs_fail(
            "acl user create user1 roleX".split(),
            "Error: ACL role 'roleX' does not exist\n",
        )
        self.assert_pcs_fail(
            "acl user create user1 role1 roleX".split(),
            "Error: ACL role 'roleX' does not exist\n",
        )
        self.assert_pcs_fail(
            "acl group create group1 roleX".split(),
            "Error: ACL role 'roleX' does not exist\n",
        )
        self.assert_pcs_fail(
            "acl group create group1 role1 roleX".split(),
            "Error: ACL role 'roleX' does not exist\n",
        )
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
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
                """
            ),
        )
        self.assert_pcs_success("acl user create user1 role1 role2".split())
        self.assert_pcs_success("acl group create group1 role1 role3".split())
        self.assert_pcs_success(
            ["acl"],
            dedent(
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
            ),
        )
        self.assert_pcs_fail(
            "acl role create group1".split(),
            "Error: 'group1' already exists\n" + ERRORS_HAVE_OCCURRED,
        )
        self.assert_pcs_fail(
            "acl role create role1".split(),
            "Error: 'role1' already exists\n" + ERRORS_HAVE_OCCURRED,
        )
        self.assert_pcs_fail(
            "acl user create user1".split(),
            "Error: 'user1' already exists\n",
        )
        self.assert_pcs_fail(
            "acl group create group1".split(),
            "Error: 'group1' already exists\n",
        )
        self.assert_pcs_fail(
            "acl group create role1".split(),
            "Error: 'role1' already exists\n",
        )
        self.assert_pcs_fail(
            "acl role assign role1 to noexist".split(),
            (
                AMBIGUOUS_ASSIGN_DEPRECATED
                + "Error: ACL group / ACL user 'noexist' does not exist\n"
            ),
        )
        self.assert_pcs_fail(
            "acl role assign noexist to user1".split(),
            (
                AMBIGUOUS_ASSIGN_DEPRECATED
                + "Error: ACL role 'noexist' does not exist\n"
            ),
        )
        self.assert_pcs_success(
            "acl role assign role3 to user1".split(),
            stderr_full=AMBIGUOUS_ASSIGN_DEPRECATED,
        )
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                User: user1
                  Roles: role1 role2 role3
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
            ),
        )
        self.assert_pcs_fail(
            "acl role unassign noexist from user1".split(),
            (
                AMBIGUOUS_ASSIGN_DEPRECATED
                + "Error: Role 'noexist' is not assigned to 'user1'\n"
            ),
        )
        self.assert_pcs_fail(
            "acl role unassign role3 from noexist".split(),
            (
                AMBIGUOUS_ASSIGN_DEPRECATED
                + "Error: ACL group / ACL user 'noexist' does not exist\n"
            ),
        )
        self.assert_pcs_success(
            "acl role unassign role3 from user1".split(),
            stderr_full=AMBIGUOUS_ASSIGN_DEPRECATED,
        )
        self.assert_pcs_success(
            ["acl"],
            dedent(
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
            ),
        )
        self.assert_pcs_success(
            "acl role unassign role2 from user1".split(),
            stderr_full=AMBIGUOUS_ASSIGN_DEPRECATED,
        )
        self.assert_pcs_success(
            "acl role unassign role1 from user1".split(),
            stderr_full=AMBIGUOUS_ASSIGN_DEPRECATED,
        )
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
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
                """
            ),
        )
        self.assert_pcs_success("acl role delete role3".split())
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
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
                """
            ),
        )
        self.assert_pcs_success(
            "acl role assign role2 to user1".split(),
            stderr_full=AMBIGUOUS_ASSIGN_DEPRECATED,
        )
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                User: user1
                  Roles: role2
                Group: group1
                  Roles: role1
                Role: role1
                  Permission: read xpath /xpath1/ (role1-read)
                  Permission: write xpath /xpath2/ (role1-write)
                Role: role2
                  Permission: deny xpath /xpath3/ (role2-deny)
                  Permission: deny xpath /xpath4/ (role2-deny-1)
                """
            ),
        )
        self.assert_pcs_success(
            "acl role assign role1 user1".split(),
            stderr_full=AMBIGUOUS_ASSIGN_DEPRECATED,
        )
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
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
                """
            ),
        )
        self.assert_pcs_success(
            "acl role unassign role2 from user1 --autodelete".split(),
            stderr_full=AUTODELETE_DEPRECATED + AMBIGUOUS_ASSIGN_DEPRECATED,
        )
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
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
                """
            ),
        )
        self.assert_pcs_success(
            "acl role unassign role1 from user1 --autodelete".split(),
            stderr_full=AUTODELETE_DEPRECATED + AMBIGUOUS_ASSIGN_DEPRECATED,
        )
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                Group: group1
                  Roles: role1
                Role: role1
                  Permission: read xpath /xpath1/ (role1-read)
                  Permission: write xpath /xpath2/ (role1-write)
                Role: role2
                  Permission: deny xpath /xpath3/ (role2-deny)
                  Permission: deny xpath /xpath4/ (role2-deny-1)
                """
            ),
        )
        self.assert_pcs_success("acl user create user1 role1 role2".split())
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
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
                """
            ),
        )
        self.assert_pcs_success(
            "acl role delete role1 --autodelete".split(),
            stderr_full=AUTODELETE_DEPRECATED,
        )
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                User: user1
                  Roles: role2
                Role: role2
                  Permission: deny xpath /xpath3/ (role2-deny)
                  Permission: deny xpath /xpath4/ (role2-deny-1)
                """
            ),
        )
        self.assert_pcs_success("acl role delete role2".split())
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                User: user1
                  Roles:
                """
            ),
        )

    def test_user_group_create_delete(self):
        self.assert_pcs_success(
            ["acl"],
            "ACLs are disabled, run 'pcs acl enable' to enable\n\n",
        )
        self.assert_pcs_success("acl user create user1".split())
        self.assert_pcs_success("acl user create user2".split())
        self.assert_pcs_fail(
            "acl user create user1".split(),
            "Error: 'user1' already exists\n",
        )
        self.assert_pcs_success("acl group create group1".split())
        self.assert_pcs_success("acl group create group2".split())
        self.assert_pcs_fail(
            "acl group create group1".split(),
            "Error: 'group1' already exists\n",
        )
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                User: user1
                  Roles:
                User: user2
                  Roles:
                Group: group1
                  Roles:
                Group: group2
                  Roles:
                """
            ),
        )
        self.assert_pcs_fail(
            "acl group delete user1".split(),
            "Error: ACL group 'user1' does not exist\n",
        )
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                User: user1
                  Roles:
                User: user2
                  Roles:
                Group: group1
                  Roles:
                Group: group2
                  Roles:
                """
            ),
        )
        self.assert_pcs_success("acl group delete group2".split())
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                User: user1
                  Roles:
                User: user2
                  Roles:
                Group: group1
                  Roles:
                """
            ),
        )
        self.assert_pcs_success("acl group remove group1".split())
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                User: user1
                  Roles:
                User: user2
                  Roles:
                """
            ),
        )
        self.assert_pcs_success("acl user delete user1".split())
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                User: user2
                  Roles:
                """
            ),
        )
        self.assert_pcs_success("acl user remove user2".split())
        self.assert_pcs_success(
            ["acl"],
            "ACLs are disabled, run 'pcs acl enable' to enable\n\n",
        )

    def test_role_create_delete(self):
        self.assert_pcs_fail(
            "acl role create role0 read".split(),
            stderr_start="\nUsage: pcs acl role create...",
        )
        self.assert_pcs_fail(
            "acl role create role0 read //resources".split(),
            stderr_start="\nUsage: pcs acl role create...",
        )
        self.assert_pcs_fail(
            "acl role create role0 read xpath".split(),
            stderr_start="\nUsage: pcs acl role create...",
        )
        self.assert_pcs_fail(
            "acl role create role0 read id".split(),
            stderr_start="\nUsage: pcs acl role create...",
        )
        self.assert_pcs_fail(
            "acl role create role0 readX xpath //resources".split(),
            (
                "Error: 'readx' is not a valid permission value, use 'deny', 'read', 'write'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_fail(
            "acl role create role0 read xpathX //resources".split(),
            (
                "Error: 'xpathx' is not a valid scope type value, use 'id', 'xpath'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_fail(
            "acl role create role0 description=test read".split(),
            stderr_start="\nUsage: pcs acl role create...",
        )
        self.assert_pcs_fail(
            "acl role create role0 description=test read //resources".split(),
            stderr_start="\nUsage: pcs acl role create...",
        )
        self.assert_pcs_fail(
            "acl role create role0 description=test read xpath".split(),
            stderr_start="\nUsage: pcs acl role create...",
        )
        self.assert_pcs_fail(
            "acl role create role0 description=test read id".split(),
            stderr_start="\nUsage: pcs acl role create...",
        )
        self.assert_pcs_fail(
            "acl role create role0 description=test readX xpath //resources".split(),
            (
                "Error: 'readx' is not a valid permission value, use 'deny', 'read', 'write'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_fail(
            "acl role create role0 description=test read xpathX //resources".split(),
            (
                "Error: 'xpathx' is not a valid scope type value, use 'id', 'xpath'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_fail(
            "acl role create role0 desc=test read".split(),
            stderr_start="\nUsage: pcs acl role create...",
        )
        self.assert_pcs_fail(
            "acl role create role0 desc=test read //resources".split(),
            (
                "Error: 'desc=test' is not a valid permission value, use 'deny', 'read', 'write'\n"
                "Error: 'read' is not a valid scope type value, use 'id', 'xpath'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_fail(
            "acl role create role0 desc=test read xpath".split(),
            (
                "Error: 'desc=test' is not a valid permission value, use 'deny', 'read', 'write'\n"
                "Error: 'read' is not a valid scope type value, use 'id', 'xpath'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_fail(
            "acl role create role0 desc=test read id".split(),
            (
                "Error: 'desc=test' is not a valid permission value, use 'deny', 'read', 'write'\n"
                "Error: 'read' is not a valid scope type value, use 'id', 'xpath'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_fail(
            "acl role create role0 desc=test readX xpath //resources".split(),
            stderr_start="\nUsage: pcs acl role create...",
        )
        self.assert_pcs_fail(
            "acl role create role0 desc=test read xpathX //resources".split(),
            stderr_start="\nUsage: pcs acl role create...",
        )
        self.assert_pcs_success(
            ["acl"],
            "ACLs are disabled, run 'pcs acl enable' to enable\n\n",
        )
        self.assert_pcs_success("acl role create role0".split())
        self.assert_pcs_fail(
            "acl role create role0".split(),
            "Error: 'role0' already exists\n" + ERRORS_HAVE_OCCURRED,
        )
        self.assert_pcs_success(
            ["acl", "role", "create", "role0d", "description=empty role"]
        )
        self.assert_pcs_success(
            "acl role create role1 read xpath /xpath/".split()
        )
        self.assert_pcs_success(
            [
                "acl",
                "role",
                "create",
                "role2",
                "description=with description",
                "READ",
                "XPATH",
                "/xpath/",
            ]
        )
        self.assert_pcs_success(
            (
                "acl role create role3 Read XPath /xpath_query/ wRiTe xpATH "
                "/xpath_query2/ deny xpath /xpath_query3/"
            ).split()
        )
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                Role: role0
                Role: role0d
                  Description: empty role
                Role: role1
                  Permission: read xpath /xpath/ (role1-read)
                Role: role2
                  Description: with description
                  Permission: read xpath /xpath/ (role2-read)
                Role: role3
                  Permission: read xpath /xpath_query/ (role3-read)
                  Permission: write xpath /xpath_query2/ (role3-write)
                  Permission: deny xpath /xpath_query3/ (role3-deny)
                """
            ),
        )
        self.assert_pcs_success("acl role delete role2".split())
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                Role: role0
                Role: role0d
                  Description: empty role
                Role: role1
                  Permission: read xpath /xpath/ (role1-read)
                Role: role3
                  Permission: read xpath /xpath_query/ (role3-read)
                  Permission: write xpath /xpath_query2/ (role3-write)
                  Permission: deny xpath /xpath_query3/ (role3-deny)
                """
            ),
        )
        self.assert_pcs_fail(
            "acl role delete role2".split(),
            "Error: ACL role 'role2' does not exist\n",
        )
        self.assert_pcs_success("acl role delete role1".split())
        self.assert_pcs_success("acl role remove role3".split())
        self.assert_pcs_success("acl role remove role0".split())
        self.assert_pcs_success("acl role remove role0d".split())
        self.assert_pcs_success(
            ["acl"],
            "ACLs are disabled, run 'pcs acl enable' to enable\n\n",
        )

    def test_permission_add_delete(self):
        self.assert_pcs_success(
            "acl role create role1 read xpath /xpath1/ write xpath /xpath2/".split()
        )
        self.assert_pcs_success(
            "acl role create role2 read xpath /xpath3/ write xpath /xpath4/".split()
        )
        self.assert_pcs_success(
            "acl role create role3 read xpath /xpath5/ write xpath /xpath6/".split()
        )
        self.assert_pcs_success(
            "acl config".split(),
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                Role: role1
                  Permission: read xpath /xpath1/ (role1-read)
                  Permission: write xpath /xpath2/ (role1-write)
                Role: role2
                  Permission: read xpath /xpath3/ (role2-read)
                  Permission: write xpath /xpath4/ (role2-write)
                Role: role3
                  Permission: read xpath /xpath5/ (role3-read)
                  Permission: write xpath /xpath6/ (role3-write)
                """
            ),
        )
        self.assert_pcs_success(
            "acl permission add role1 deny xpath /myxpath1/".split()
        )
        self.assert_pcs_success(
            "acl permission add role4 deny xpath /myxpath2/".split()
        )
        self.assert_pcs_success(
            "acl config".split(),
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                Role: role1
                  Permission: read xpath /xpath1/ (role1-read)
                  Permission: write xpath /xpath2/ (role1-write)
                  Permission: deny xpath /myxpath1/ (role1-deny)
                Role: role2
                  Permission: read xpath /xpath3/ (role2-read)
                  Permission: write xpath /xpath4/ (role2-write)
                Role: role3
                  Permission: read xpath /xpath5/ (role3-read)
                  Permission: write xpath /xpath6/ (role3-write)
                Role: role4
                  Permission: deny xpath /myxpath2/ (role4-deny)
                """
            ),
        )
        self.assert_pcs_success("acl permission delete role4-deny".split())
        self.assert_pcs_fail(
            "acl permission delete role4-deny".split(),
            "Error: ACL permission 'role4-deny' does not exist\n",
        )
        self.assert_pcs_fail(
            "acl permission remove role4-deny".split(),
            "Error: ACL permission 'role4-deny' does not exist\n",
        )
        self.assert_pcs_success(
            "acl config".split(),
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                Role: role1
                  Permission: read xpath /xpath1/ (role1-read)
                  Permission: write xpath /xpath2/ (role1-write)
                  Permission: deny xpath /myxpath1/ (role1-deny)
                Role: role2
                  Permission: read xpath /xpath3/ (role2-read)
                  Permission: write xpath /xpath4/ (role2-write)
                Role: role3
                  Permission: read xpath /xpath5/ (role3-read)
                  Permission: write xpath /xpath6/ (role3-write)
                Role: role4
                """
            ),
        )
        self.assert_pcs_success("acl permission delete role3-read".split())
        self.assert_pcs_success("acl permission delete role3-write".split())
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                Role: role1
                  Permission: read xpath /xpath1/ (role1-read)
                  Permission: write xpath /xpath2/ (role1-write)
                  Permission: deny xpath /myxpath1/ (role1-deny)
                Role: role2
                  Permission: read xpath /xpath3/ (role2-read)
                  Permission: write xpath /xpath4/ (role2-write)
                Role: role3
                Role: role4
                """
            ),
        )
        self.assert_pcs_success("acl permission remove role1-read".split())
        self.assert_pcs_success("acl permission remove role1-write".split())
        self.assert_pcs_success("acl permission remove role1-deny".split())
        self.assert_pcs_success("acl permission remove role2-read".split())
        self.assert_pcs_success("acl permission remove role2-write".split())
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                Role: role1
                Role: role2
                Role: role3
                Role: role4
                """
            ),
        )
        self.assert_pcs_fail(
            "acl permission add role1 read".split(),
            stderr_start="\nUsage: pcs acl permission add...",
        )
        self.assert_pcs_fail(
            "acl permission add role1 read //resources".split(),
            stderr_start="\nUsage: pcs acl permission add...",
        )
        self.assert_pcs_fail(
            "acl permission add role1 read xpath".split(),
            stderr_start="\nUsage: pcs acl permission add...",
        )
        self.assert_pcs_fail(
            "acl permission add role1 read id".split(),
            stderr_start="\nUsage: pcs acl permission add...",
        )
        self.assert_pcs_fail(
            "acl permission add role1 readX xpath //resources".split(),
            (
                "Error: 'readx' is not a valid permission value, use 'deny', 'read', 'write'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_fail(
            "acl permission add role1 read xpathX //resources".split(),
            (
                "Error: 'xpathx' is not a valid scope type value, use 'id', 'xpath'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_fail(
            "acl permission add role1 read id dummy read".split(),
            stderr_start="\nUsage: pcs acl permission add...",
        )
        self.assert_pcs_fail(
            "acl permission add role1 read id dummy read //resources".split(),
            stderr_start="\nUsage: pcs acl permission add...",
        )
        self.assert_pcs_fail(
            "acl permission add role1 read id dummy read xpath".split(),
            stderr_start="\nUsage: pcs acl permission add...",
        )
        self.assert_pcs_fail(
            "acl permission add role1 read id dummy read id".split(),
            stderr_start="\nUsage: pcs acl permission add...",
        )
        self.assert_pcs_fail(
            "acl permission add role1 read id dummy readX xpath //resources".split(),
            (
                "Error: id 'dummy' does not exist\n"
                "Error: 'readx' is not a valid permission value, use 'deny', 'read', 'write'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_fail(
            "acl permission add role1 read id dummy read xpathX //resources".split(),
            (
                "Error: id 'dummy' does not exist\n"
                "Error: 'xpathx' is not a valid scope type value, use 'id', 'xpath'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success(
            ["acl"],
            dedent(
                """\
                ACLs are disabled, run 'pcs acl enable' to enable

                Role: role1
                Role: role2
                Role: role3
                Role: role4
                """
            ),
        )

    def test_can_add_permission_for_existing_id(self):
        self.assert_pcs_success("acl role create role1".split())
        self.assert_pcs_success("acl role create role2".split())
        self.assert_pcs_success(
            "acl permission add role1 read id role2".split()
        )

    def test_can_add_permission_for_existing_xpath(self):
        self.assert_pcs_success("acl role create role1".split())
        self.assert_pcs_success(
            "acl permission add role1 read xpath //nodes".split()
        )

    def test_can_not_add_permission_for_nonexisting_id(self):
        self.assert_pcs_success("acl role create role1".split())
        self.assert_pcs_fail(
            "acl permission add role1 read id non-existent-id".split(),
            "Error: id 'non-existent-id' does not exist\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_can_not_add_permission_for_nonexisting_id_in_later_part(self):
        self.assert_pcs_success("acl role create role1".split())
        self.assert_pcs_success("acl role create role2".split())
        self.assert_pcs_fail(
            "acl permission add role1 read id role2 read id non-existent-id".split(),
            "Error: id 'non-existent-id' does not exist\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_can_not_add_permission_for_nonexisting_role_with_bad_id(self):
        self.assert_pcs_success("acl role create role1".split())
        self.assert_pcs_fail(
            "acl permission add #bad-name read id role1".split(),
            "Error: invalid ACL role '#bad-name'"
            ", '#' is not a valid first character for a ACL role\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_can_create_role_with_permission_for_existing_id(self):
        self.assert_pcs_success("acl role create role2".split())
        self.assert_pcs_success("acl role create role1 read id role2".split())

    def test_can_not_crate_role_with_permission_for_nonexisting_id(self):
        self.assert_pcs_fail(
            "acl role create role1 read id non-existent-id".split(),
            "Error: id 'non-existent-id' does not exist\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_can_not_create_role_with_bad_name(self):
        self.assert_pcs_fail(
            "acl role create #bad-name".split(),
            "Error: invalid ACL role '#bad-name'"
            ", '#' is not a valid first character for a ACL role\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_on_unknown_role_method(self):
        self.assert_pcs_fail(
            "acl role unknown whatever".split(),
            stderr_start="\nUsage: pcs acl role ...",
        )

    def test_assign_unassign_role_to_user(self):
        self.assert_pcs_success("acl role create role1".split())
        self.assert_pcs_success("acl user create user1".split())
        self.assert_pcs_success("acl role assign role1 user user1".split())
        self.assert_pcs_fail(
            "acl role assign role1 user user1".split(),
            "Error: Role 'role1' is already assigned to 'user1'\n",
        )
        self.assert_pcs_success("acl role unassign role1 user user1".split())
        self.assert_pcs_fail(
            "acl role unassign role1 user user1".split(),
            "Error: Role 'role1' is not assigned to 'user1'\n",
        )

    def test_assign_unassign_role_to_user_not_existing_user(self):
        self.assert_pcs_success("acl role create role1".split())
        self.assert_pcs_success("acl group create group1".split())
        self.assert_pcs_fail(
            "acl role assign role1 to user group1".split(),
            "Error: 'group1' is not an ACL user\n",
        )

    def test_assign_unassign_role_to_user_with_to(self):
        self.assert_pcs_success("acl role create role1".split())
        self.assert_pcs_success("acl user create user1".split())
        self.assert_pcs_success("acl role assign role1 to user user1".split())
        self.assert_pcs_fail(
            "acl role assign role1 to user user1".split(),
            "Error: Role 'role1' is already assigned to 'user1'\n",
        )
        self.assert_pcs_success(
            "acl role unassign role1 from user user1".split()
        )
        self.assert_pcs_fail(
            "acl role unassign role1 from user user1".split(),
            "Error: Role 'role1' is not assigned to 'user1'\n",
        )

    def test_assign_unassign_role_to_group(self):
        self.assert_pcs_success("acl role create role1".split())
        self.assert_pcs_success("acl group create group1".split())
        self.assert_pcs_success("acl role assign role1 group group1".split())
        self.assert_pcs_fail(
            "acl role assign role1 group group1".split(),
            "Error: Role 'role1' is already assigned to 'group1'\n",
        )
        self.assert_pcs_success("acl role unassign role1 group group1".split())
        self.assert_pcs_fail(
            "acl role unassign role1 group group1".split(),
            "Error: Role 'role1' is not assigned to 'group1'\n",
        )

    def test_assign_unassign_role_to_group_not_existing_group(self):
        self.assert_pcs_success("acl role create role1".split())
        self.assert_pcs_success("acl user create user1".split())
        self.assert_pcs_fail(
            "acl role assign role1 to group user1".split(),
            "Error: ACL group 'user1' does not exist\n",
        )

    def test_assign_unassign_role_to_group_with_to(self):
        self.assert_pcs_success("acl role create role1".split())
        self.assert_pcs_success("acl group create group1".split())
        self.assert_pcs_success("acl role assign role1 to group group1".split())
        self.assert_pcs_fail(
            "acl role assign role1 to group group1".split(),
            "Error: Role 'role1' is already assigned to 'group1'\n",
        )
        self.assert_pcs_success(
            "acl role unassign role1 from group group1".split()
        )
        self.assert_pcs_fail(
            "acl role unassign role1 from group group1".split(),
            "Error: Role 'role1' is not assigned to 'group1'\n",
        )
