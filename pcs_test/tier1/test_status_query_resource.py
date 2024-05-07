from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


class QueryTestBase(TestCase, AssertPcsMixin):
    cib = get_test_resource("cib-resources.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_status_query_resource")
        write_file_to_tmpfile(self.cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()


class QueryExists(QueryTestBase):
    def test_true(self):
        self.assert_pcs_success(
            ["status", "query", "resource", "S2", "exists"], "True\n"
        )

    def test_false(self):
        self.assert_pcs_result(
            ["status", "query", "resource", "nonexistent", "exists"],
            stdout_full="False\n",
            stderr_full="",
            returncode=2,
        )


class QueryIsStonith(QueryTestBase):
    def test_true(self):
        self.assert_pcs_success(
            ["status", "query", "resource", "S2", "is-stonith"], "True\n"
        )

    def test_false(self):
        self.assert_pcs_result(
            ["status", "query", "resource", "R7", "is-stonith"],
            stdout_full="False\n",
            stderr_full="",
            returncode=2,
        )

    def test_fail(self):
        self.assert_pcs_fail(
            ["status", "query", "resource", "nonexistent", "is-stonith"],
            "Error: Resource 'nonexistent' does not exist\n",
        )


class QueryIsType(QueryTestBase):
    def test_true(self):
        self.assert_pcs_success(
            [
                "status",
                "query",
                "resource",
                "B1",
                "is-type",
                "bundle",
                "unique",
            ],
            "True\n",
        )

    def test_false(self):
        self.assert_pcs_result(
            ["status", "query", "resource", "G2", "is-type", "clone"],
            stdout_full="False\n",
            stderr_full="",
            returncode=2,
        )


class QueryGetType(QueryTestBase):
    def test_ok(self):
        self.assert_pcs_success(
            ["status", "query", "resource", "G1-clone", "get-type"],
            "clone promotable\n",
        )


class QueryIsInGroup(QueryTestBase):
    def test_group(self):
        self.assert_pcs_success(
            ["status", "query", "resource", "R2", "is-in-group"], "True\nG1\n"
        )

    def test_bad_group(self):
        self.assert_pcs_result(
            ["status", "query", "resource", "R5", "is-in-group", "G1"],
            stdout_full="False\nG2\n",
            stderr_full="",
            returncode=2,
        )

    def test_fail(self):
        self.assert_pcs_fail(
            ["status", "query", "resource", "G1", "is-in-group"],
            (
                "Error: Resource 'G1' has unexpected type 'group'. This "
                "command works only for resources of type 'primitive'\n"
            ),
        )


class QueryIsInClone(QueryTestBase):
    def test_clone(self):
        self.assert_pcs_success(
            ["status", "query", "resource", "R2", "is-in-clone"],
            "True\nG1-clone\n",
        )

    def test_bad_clone(self):
        self.assert_pcs_result(
            ["status", "query", "resource", "R2", "is-in-clone", "R6-clone"],
            stdout_full="False\nG1-clone\n",
            stderr_full="",
            returncode=2,
        )

    def test_fail(self):
        self.assert_pcs_fail(
            ["status", "query", "resource", "R6-clone", "is-in-clone"],
            (
                "Error: Resource 'R6-clone' has unexpected type 'clone'. This "
                "command works only for resources of type 'group', "
                "'primitive'\n"
            ),
        )


class QueryIsInBundle(QueryTestBase):
    def test_in_bundle(self):
        self.assert_pcs_success(
            ["status", "query", "resource", "R1", "is-in-bundle"], "True\nB2\n"
        )

    def test_bad_bundle(self):
        self.assert_pcs_result(
            ["status", "query", "resource", "R1", "is-in-bundle", "B1"],
            stdout_full="False\nB2\n",
            stderr_full="",
            returncode=2,
        )

    def test_fail(self):
        self.assert_pcs_fail(
            ["status", "query", "resource", "G1", "is-in-group"],
            (
                "Error: Resource 'G1' has unexpected type 'group'. This "
                "command works only for resources of type 'primitive'\n"
            ),
        )


class QueryGetMembers(QueryTestBase):
    def test_ok(self):
        self.assert_pcs_success(
            ["status", "query", "resource", "G2", "get-members"],
            "R5\n",
        )

    def test_primitive(self):
        self.assert_pcs_fail(
            ["status", "query", "resource", "S1", "get-members"],
            (
                "Error: Resource 'S1' has unexpected type 'primitive'. This "
                "command works only for resources of type 'bundle', 'clone', "
                "'group'\n"
            ),
        )


class QueryGetIndexInGroup(QueryTestBase):
    def test_ok(self):
        self.assert_pcs_success(
            ["status", "query", "resource", "R5", "get-index-in-group"], "0\n"
        )

    def test_not_in_group(self):
        self.assert_pcs_fail(
            ["status", "query", "resource", "S2", "get-index-in-group"],
            "Error: Resource 'S2' is not in a group\n",
        )


class QueryCibWithStatusTestBase(TestCase, AssertPcsMixin):
    cib = get_test_resource("cib-status.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_status_query_resource_status")
        write_file_to_tmpfile(self.cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()


class QueryGetNodes(QueryCibWithStatusTestBase):
    def test_one(self):
        self.assert_pcs_success(
            ["status", "query", "resource", "s1", "get-nodes"], "rh93-1\n"
        )

    def test_multiple(self):
        self.assert_pcs_success(
            ["status", "query", "resource", "g1", "get-nodes"],
            "rh93-1\nrh93-2\n",
        )

    def test_fail(self):
        self.assert_pcs_fail(
            ["status", "query", "resource", "g2", "get-nodes"],
            "Error: Resource 'g2' does not exist\n",
        )


class QueryIsState(QueryCibWithStatusTestBase):
    def test_true(self):
        self.assert_pcs_success(
            [
                "status",
                "query",
                "resource",
                "g1",
                "is-state",
                "started",
                "on-node",
                "rh93-1",
            ],
            "True\n",
        )

    def test_false(self):
        self.assert_pcs_result(
            [
                "status",
                "query",
                "resource",
                "g1",
                "is-state",
                "started",
                "members",
                "all",
                "instances",
                "all",
            ],
            stdout_full="False\n",
            stderr_full="",
            returncode=2,
        )

    def test_fail(self):
        self.assert_pcs_fail(
            [
                "status",
                "query",
                "resource",
                "r1",
                "is-state",
                "started",
                "members",
                "all",
            ],
            (
                "Error: 'members' quantifier can be used only on group "
                "resources or group instances of cloned groups\n"
            ),
        )


class QueryResourceRemoteNode(TestCase, AssertPcsMixin):
    cib = get_test_resource("cib-remote.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_status_query_resource_remote")
        write_file_to_tmpfile(self.cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def test_exists(self):
        self.assert_pcs_success(
            ["status", "query", "resource", "dummy", "exists"], "True\n"
        )

    def test_get_nodes(self):
        self.assert_pcs_success(
            ["status", "query", "resource", "dummy", "get-nodes"],
            "rh93-remote\n",
        )

    def test_started(self):
        self.assert_pcs_success(
            ["status", "query", "resource", "dummy", "is-state", "started"],
            "True\n",
        )
