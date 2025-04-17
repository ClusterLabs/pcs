from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs import (
    node,
    utils,
)

from pcs_test.tier1.legacy.common import FIXTURE_UTILIZATION_WARNING
from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    outdent,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import (
    PcsRunner,
    pcs,
)

empty_cib = rc("cib-empty-withnodes.xml")


class NodeUtilizationSet(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).findall(".//nodes")[0])
    ),
):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_node_utilization_set")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    @staticmethod
    def fixture_xml_no_utilization():
        # must match empty_cib
        return """
            <nodes>
                <node id="1" uname="rh7-1" />
                <node id="2" uname="rh7-2" />
            </nodes>
        """

    @staticmethod
    def fixture_xml_empty_utilization():
        # must match empty_cib
        return """
            <nodes>
                <node id="1" uname="rh7-1">
                    <utilization id="nodes-1-utilization" />
                </node>
                <node id="2" uname="rh7-2" />
            </nodes>
        """

    @staticmethod
    def fixture_xml_with_utilization():
        # must match empty_cib
        return """
            <nodes>
                <node id="1" uname="rh7-1">
                    <utilization id="nodes-1-utilization">
                        <nvpair id="nodes-1-utilization-test" name="test"
                            value="100"
                        />
                    </utilization>
                </node>
                <node id="2" uname="rh7-2" />
            </nodes>
        """

    def test_node_utilization_set(self):
        stdout, stderr, retval = pcs(
            self.temp_cib.name, "node utilization rh7-1 test1=10".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, FIXTURE_UTILIZATION_WARNING)
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "node utilization rh7-2".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, FIXTURE_UTILIZATION_WARNING)
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "node utilization rh7-1".split()
        )
        self.assertEqual(
            stdout,
            outdent(
                """\
                Node: rh7-1
                  Utilization: nodes-1-utilization
                    test1=10
                """
            ),
        )
        self.assertEqual(stderr, FIXTURE_UTILIZATION_WARNING)
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "node utilization rh7-1 test1=-10 test4=1234".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, FIXTURE_UTILIZATION_WARNING)
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "node utilization rh7-1".split()
        )
        self.assertEqual(
            stdout,
            outdent(
                """\
                Node: rh7-1
                  Utilization: nodes-1-utilization
                    test1=-10
                    test4=1234
                """
            ),
        )
        self.assertEqual(stderr, FIXTURE_UTILIZATION_WARNING)
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "node utilization rh7-2 test2=321 empty=".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, FIXTURE_UTILIZATION_WARNING)
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "node utilization rh7-2".split()
        )
        self.assertEqual(
            stdout,
            outdent(
                """\
                Node: rh7-2
                  Utilization: nodes-2-utilization
                    test2=321
                """
            ),
        )
        self.assertEqual(stderr, FIXTURE_UTILIZATION_WARNING)
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "node utilization".split()
        )
        self.assertEqual(
            stdout,
            outdent(
                """\
                Node: rh7-1
                  Utilization: nodes-1-utilization
                    test1=-10
                    test4=1234
                Node: rh7-2
                  Utilization: nodes-2-utilization
                    test2=321
                """
            ),
        )
        self.assertEqual(stderr, FIXTURE_UTILIZATION_WARNING)
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "node utilization rh7-2 test1=-20".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, FIXTURE_UTILIZATION_WARNING)
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "node utilization --name test1".split()
        )
        self.assertEqual(
            stdout,
            outdent(
                """\
                Node: rh7-1
                  Utilization: nodes-1-utilization
                    test1=-10
                Node: rh7-2
                  Utilization: nodes-2-utilization
                    test1=-20
                """
            ),
        )
        self.assertEqual(stderr, FIXTURE_UTILIZATION_WARNING)
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "node utilization --name test1 rh7-2".split(),
        )
        self.assertEqual(
            stdout,
            outdent(
                """\
                Node: rh7-2
                  Utilization: nodes-2-utilization
                    test1=-20
                """
            ),
        )
        self.assertEqual(stderr, FIXTURE_UTILIZATION_WARNING)
        self.assertEqual(retval, 0)

    def test_refuse_non_option_attribute_parameter_among_options(self):
        self.assert_pcs_fail(
            "node utilization rh7-1 net".split(),
            (
                f"{FIXTURE_UTILIZATION_WARNING}"
                "Error: missing value of 'net' option\n"
            ),
        )

    def test_refuse_option_without_key(self):
        self.assert_pcs_fail(
            "node utilization rh7-1 =1".split(),
            f"{FIXTURE_UTILIZATION_WARNING}Error: missing key in '=1' option\n",
        )

    def test_refuse_unknown_node(self):
        self.assert_pcs_fail(
            "node utilization rh7-0 test=10".split(),
            (
                f"{FIXTURE_UTILIZATION_WARNING}"
                "Error: Unable to find a node: rh7-0\n"
            ),
        )

    def test_refuse_value_not_int(self):
        self.assert_pcs_fail(
            "node utilization rh7-1 test1=10 test=int".split(),
            (
                f"{FIXTURE_UTILIZATION_WARNING}"
                "Error: Value of utilization attribute must be integer: "
                "'test=int'\n"
            ),
        )

    def test_keep_empty_nvset(self):
        self.assert_effect(
            "node utilization rh7-1 test=100".split(),
            self.fixture_xml_with_utilization(),
            stderr_full=FIXTURE_UTILIZATION_WARNING,
        )
        self.assert_effect(
            "node utilization rh7-1 test=".split(),
            self.fixture_xml_empty_utilization(),
            stderr_full=FIXTURE_UTILIZATION_WARNING,
        )

    def test_dont_create_nvset_on_removal(self):
        self.assert_effect(
            "node utilization rh7-1 test=".split(),
            self.fixture_xml_no_utilization(),
            stderr_full=FIXTURE_UTILIZATION_WARNING,
        )

    def test_no_warning_printed_placement_strategy_is_set(self):
        self.assert_effect(
            "property set placement-strategy=minimal".split(),
            self.fixture_xml_no_utilization(),
        )
        self.assert_resources_xml_in_cib(
            """
            <crm_config>
                <cluster_property_set id="cib-bootstrap-options">
                    <nvpair id="cib-bootstrap-options-placement-strategy"
                        name="placement-strategy" value="minimal"
                    />
                </cluster_property_set>
            </crm_config>
            """,
            get_cib_part_func=lambda cib: etree.tostring(
                etree.parse(cib).findall(".//crm_config")[0],
            ),
        )
        self.assert_effect(
            "node utilization rh7-1 test=".split(),
            self.fixture_xml_no_utilization(),
        )
        self.assert_effect(
            "node utilization".split(), self.fixture_xml_no_utilization()
        )


class NodeUtilizationPrint(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_node_utilization_print")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    @mock.patch("pcs.node.utils")
    def test_refuse_when_node_not_in_cib_and_is_not_remote(self, mock_utils):
        mock_cib = mock.MagicMock()
        mock_cib.getElementsByTagName = mock.Mock(return_value=[])

        mock_utils.get_cib_dom = mock.Mock(return_value=mock_cib)
        mock_utils.usefile = False
        mock_utils.getNodeAttributesFromPacemaker = mock.Mock(return_value=[])
        mock_utils.err = mock.Mock(side_effect=SystemExit)

        self.assertRaises(
            SystemExit, lambda: node.print_node_utilization("some")
        )

    def test_refuse_when_node_not_in_mocked_cib(self):
        self.assert_pcs_fail(
            "node utilization some_nonexistent_node".split(),
            (
                f"{FIXTURE_UTILIZATION_WARNING}"
                "Error: Unable to find a node: some_nonexistent_node\n"
            ),
        )


class NodeStandby(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_node_standby")
        write_file_to_tmpfile(rc("cib-empty-with3nodes.xml"), self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        pass
        # self.temp_cib.close()

    def fixture_standby_all(self):
        self.assert_pcs_success("node standby --all".split())
        self.assert_standby_all()

    def assert_standby_none(self):
        self.assert_pcs_success("node attribute".split())

    def assert_standby_all(self):
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    standby=on
                Node: rh7-2
                  Attributes: nodes-2
                    standby=on
                Node: rh7-3
                  Attributes: nodes-3
                    standby=on
                """
            ),
        )

    def test_local_node(self):
        self.assert_standby_none()
        self.assert_pcs_fail(
            "node standby".split(),
            "Error: Node(s) must be specified if -f is used\n",
        )
        self.assert_standby_none()

        self.fixture_standby_all()
        self.assert_pcs_fail(
            "node unstandby".split(),
            "Error: Node(s) must be specified if -f is used\n",
        )
        self.assert_standby_all()

    def test_one_bad_node(self):
        self.assert_standby_none()
        self.assert_pcs_fail(
            "node standby nonexistent-node".split(),
            "Error: Node 'nonexistent-node' does not appear to exist in configuration\n",
        )
        self.assert_standby_none()

        self.fixture_standby_all()
        self.assert_pcs_fail(
            "node unstandby nonexistent-node".split(),
            "Error: Node 'nonexistent-node' does not appear to exist in configuration\n",
        )
        self.assert_standby_all()

    def test_bad_node_cancels_all_changes(self):
        self.assert_standby_none()
        self.assert_pcs_fail(
            "node standby rh7-1 nonexistent-node and-another rh7-2".split(),
            "Error: Node 'nonexistent-node' does not appear to exist in configuration\n"
            "Error: Node 'and-another' does not appear to exist in configuration\n",
        )
        self.assert_standby_none()

        self.fixture_standby_all()
        self.assert_pcs_fail(
            "node standby rh7-1 nonexistent-node and-another rh7-2".split(),
            "Error: Node 'nonexistent-node' does not appear to exist in configuration\n"
            "Error: Node 'and-another' does not appear to exist in configuration\n",
        )
        self.assert_standby_all()

    def test_all_nodes(self):
        self.assert_standby_none()
        self.assert_pcs_success("node standby --all".split())
        self.fixture_standby_all()

        self.assert_pcs_success("node unstandby --all".split())
        self.assert_standby_none()

    def test_one_node_with_repeat(self):
        self.assert_standby_none()
        self.assert_pcs_success("node standby rh7-1".split())
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    standby=on
                """
            ),
        )
        self.assert_pcs_success("node standby rh7-1".split())

        self.fixture_standby_all()
        self.assert_pcs_success("node unstandby rh7-1".split())
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-2
                  Attributes: nodes-2
                    standby=on
                Node: rh7-3
                  Attributes: nodes-3
                    standby=on
                """
            ),
        )
        self.assert_pcs_success("node unstandby rh7-1".split())

    def test_more_nodes(self):
        self.assert_standby_none()
        self.assert_pcs_success("node standby rh7-1 rh7-2".split())
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    standby=on
                Node: rh7-2
                  Attributes: nodes-2
                    standby=on
                """
            ),
        )

        self.fixture_standby_all()
        self.assert_pcs_success("node unstandby rh7-1 rh7-2".split())
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-3
                  Attributes: nodes-3
                    standby=on
                """
            ),
        )

    def test_all_and_nodelist(self):
        self.assert_pcs_fail(
            "node standby rh7-1 rh7-2 --all".split(),
            "Error: Cannot specify both --all and a list of nodes.\n",
        )
        self.assert_pcs_fail(
            "node unstandby rh7-1 rh7-2 --all".split(),
            "Error: Cannot specify both --all and a list of nodes.\n",
        )


class NodeMaintenance(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_node_maintenance")
        write_file_to_tmpfile(rc("cib-empty-with3nodes.xml"), self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def fixture_maintenance_all(self):
        self.assert_pcs_success("node maintenance --all".split())
        self.assert_maintenance_all()

    def assert_maintenance_none(self):
        self.assert_pcs_success("node attribute".split())

    def assert_maintenance_all(self):
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    maintenance=on
                Node: rh7-2
                  Attributes: nodes-2
                    maintenance=on
                Node: rh7-3
                  Attributes: nodes-3
                    maintenance=on
                """
            ),
        )

    def test_local_node(self):
        self.assert_maintenance_none()
        self.assert_pcs_fail(
            "node maintenance".split(),
            "Error: Node(s) must be specified if -f is used\n",
        )
        self.assert_maintenance_none()

        self.fixture_maintenance_all()
        self.assert_pcs_fail(
            "node unmaintenance".split(),
            "Error: Node(s) must be specified if -f is used\n",
        )
        self.assert_maintenance_all()

    def test_one_bad_node(self):
        self.assert_maintenance_none()
        self.assert_pcs_fail(
            "node maintenance nonexistent-node".split(),
            "Error: Node 'nonexistent-node' does not appear to exist in configuration\n",
        )
        self.assert_maintenance_none()

        self.fixture_maintenance_all()
        self.assert_pcs_fail(
            "node unmaintenance nonexistent-node".split(),
            "Error: Node 'nonexistent-node' does not appear to exist in configuration\n",
        )
        self.assert_maintenance_all()

    def test_bad_node_cancels_all_changes(self):
        self.assert_maintenance_none()
        self.assert_pcs_fail(
            "node maintenance rh7-1 nonexistent-node and-another rh7-2".split(),
            "Error: Node 'nonexistent-node' does not appear to exist in configuration\n"
            "Error: Node 'and-another' does not appear to exist in configuration\n",
        )
        self.assert_maintenance_none()

        self.fixture_maintenance_all()
        self.assert_pcs_fail(
            "node maintenance rh7-1 nonexistent-node and-another rh7-2".split(),
            "Error: Node 'nonexistent-node' does not appear to exist in configuration\n"
            "Error: Node 'and-another' does not appear to exist in configuration\n",
        )
        self.assert_maintenance_all()

    def test_all_nodes(self):
        self.assert_maintenance_none()
        self.assert_pcs_success("node maintenance --all".split())
        self.fixture_maintenance_all()

        self.assert_pcs_success("node unmaintenance --all".split())
        self.assert_maintenance_none()

    def test_one_node_with_repeat(self):
        self.assert_maintenance_none()
        self.assert_pcs_success("node maintenance rh7-1".split())
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    maintenance=on
                """
            ),
        )
        self.assert_pcs_success("node maintenance rh7-1".split())

        self.fixture_maintenance_all()
        self.assert_pcs_success("node unmaintenance rh7-1".split())
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-2
                  Attributes: nodes-2
                    maintenance=on
                Node: rh7-3
                  Attributes: nodes-3
                    maintenance=on
                """
            ),
        )
        self.assert_pcs_success("node unmaintenance rh7-1".split())

    def test_more_nodes(self):
        self.assert_maintenance_none()
        self.assert_pcs_success("node maintenance rh7-1 rh7-2".split())
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    maintenance=on
                Node: rh7-2
                  Attributes: nodes-2
                    maintenance=on
                """
            ),
        )

        self.fixture_maintenance_all()
        self.assert_pcs_success("node unmaintenance rh7-1 rh7-2".split())
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-3
                  Attributes: nodes-3
                    maintenance=on
                """
            ),
        )

    def test_all_and_nodelist(self):
        self.assert_pcs_fail(
            "node maintenance rh7-1 rh7-2 --all".split(),
            "Error: Cannot specify both --all and a list of nodes.\n",
        )
        self.assert_pcs_fail(
            "node unmaintenance rh7-1 rh7-2 --all".split(),
            "Error: Cannot specify both --all and a list of nodes.\n",
        )


class NodeAttributeTest(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).findall(".//nodes")[0])
    ),
):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_node_attribute")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def fixture_attrs(self, nodes, attrs=None):
        attrs = {} if attrs is None else attrs
        xml_lines = ["<nodes>"]
        for node_id, node_name in enumerate(nodes, 1):
            xml_lines.extend(
                [
                    '<node id="{0}" uname="{1}">'.format(node_id, node_name),
                    '<instance_attributes id="nodes-{0}">'.format(node_id),
                ]
            )
            # pylint: disable=invalid-name
            nv = '<nvpair id="nodes-{id}-{name}" name="{name}" value="{val}"/>'
            for name, value in attrs.get(node_name, {}).items():
                xml_lines.append(nv.format(id=node_id, name=name, val=value))
            xml_lines.extend(["</instance_attributes>", "</node>"])
        xml_lines.append("</nodes>")

        utils_usefile_original = utils.usefile
        utils_filename_original = utils.filename
        utils.usefile = True
        utils.filename = self.temp_cib.name
        output, retval = utils.run(
            ["cibadmin", "--modify", "--xml-text", "\n".join(xml_lines)]
        )
        utils.usefile = utils_usefile_original
        utils.filename = utils_filename_original
        assert output == ""
        assert retval == 0

    @staticmethod
    def fixture_xml_no_attrs():
        # must match empty_cib
        return """
            <nodes>
                <node id="1" uname="rh7-1" />
                <node id="2" uname="rh7-2" />
            </nodes>
        """

    @staticmethod
    def fixture_xml_empty_attrs():
        # must match empty_cib
        return """
            <nodes>
                <node id="1" uname="rh7-1">
                    <instance_attributes id="nodes-1" />
                </node>
                <node id="2" uname="rh7-2" />
            </nodes>
        """

    @staticmethod
    def fixture_xml_with_attrs():
        # must match empty_cib
        return """
            <nodes>
                <node id="1" uname="rh7-1">
                    <instance_attributes id="nodes-1">
                        <nvpair id="nodes-1-test" name="test" value="100" />
                    </instance_attributes>
                </node>
                <node id="2" uname="rh7-2" />
            </nodes>
        """

    def test_show_empty(self):
        self.fixture_attrs(["rh7-1", "rh7-2"])
        self.assert_pcs_success("node attribute".split())

    def test_show_nonempty(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {
                    "IP": "192.168.1.1",
                },
                "rh7-2": {
                    "IP": "192.168.1.2",
                },
            },
        )
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    IP=192.168.1.1
                Node: rh7-2
                  Attributes: nodes-2
                    IP=192.168.1.2
                """
            ),
        )

    def test_show_multiple_per_node(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {
                    "IP": "192.168.1.1",
                    "alias": "node1",
                },
                "rh7-2": {
                    "IP": "192.168.1.2",
                    "alias": "node2",
                },
            },
        )
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    IP=192.168.1.1
                    alias=node1
                Node: rh7-2
                  Attributes: nodes-2
                    IP=192.168.1.2
                    alias=node2
                """
            ),
        )

    def test_show_one_node(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {
                    "IP": "192.168.1.1",
                    "alias": "node1",
                },
                "rh7-2": {
                    "IP": "192.168.1.2",
                    "alias": "node2",
                },
            },
        )
        self.assert_pcs_success(
            "node attribute rh7-1".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    IP=192.168.1.1
                    alias=node1
                """
            ),
        )

    def test_show_missing_node(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {
                    "IP": "192.168.1.1",
                    "alias": "node1",
                },
                "rh7-2": {
                    "IP": "192.168.1.2",
                    "alias": "node2",
                },
            },
        )
        self.assert_pcs_fail(
            "node attribute rh7-3".split(),
            "Error: Unable to find a node: rh7-3\n",
        )

    def test_show_name(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {
                    "IP": "192.168.1.1",
                    "alias": "node1",
                },
                "rh7-2": {
                    "IP": "192.168.1.2",
                    "alias": "node2",
                },
            },
        )
        self.assert_pcs_success(
            "node attribute --name alias".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    alias=node1
                Node: rh7-2
                  Attributes: nodes-2
                    alias=node2
                """
            ),
        )

    def test_show_missing_name(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {
                    "IP": "192.168.1.1",
                    "alias": "node1",
                },
                "rh7-2": {
                    "IP": "192.168.1.2",
                    "alias": "node2",
                },
            },
        )
        self.assert_pcs_success("node attribute --name missing".split())

    def test_show_node_and_name(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {
                    "IP": "192.168.1.1",
                    "alias": "node1",
                },
                "rh7-2": {
                    "IP": "192.168.1.2",
                    "alias": "node2",
                },
            },
        )
        self.assert_pcs_success(
            "node attribute --name alias rh7-1".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    alias=node1
                """
            ),
        )

    def test_set_new(self):
        self.fixture_attrs(["rh7-1", "rh7-2"])
        self.assert_pcs_success("node attribute rh7-1 IP=192.168.1.1".split())
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    IP=192.168.1.1
                """
            ),
        )
        self.assert_pcs_success("node attribute rh7-2 IP=192.168.1.2".split())
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    IP=192.168.1.1
                Node: rh7-2
                  Attributes: nodes-2
                    IP=192.168.1.2
                """
            ),
        )

    def test_set_existing(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {
                    "IP": "192.168.1.1",
                },
                "rh7-2": {
                    "IP": "192.168.1.2",
                },
            },
        )
        self.assert_pcs_success("node attribute rh7-2 IP=192.168.2.2".split())
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    IP=192.168.1.1
                Node: rh7-2
                  Attributes: nodes-2
                    IP=192.168.2.2
                """
            ),
        )

    def test_unset(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {
                    "IP": "192.168.1.1",
                },
                "rh7-2": {
                    "IP": "192.168.1.2",
                },
            },
        )
        self.assert_pcs_success("node attribute rh7-2 IP=".split())
        self.assert_pcs_success(
            "node attribute".split(),
            outdent(
                """\
                Node: rh7-1
                  Attributes: nodes-1
                    IP=192.168.1.1
                """
            ),
        )

    def test_unset_nonexisting(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {
                    "IP": "192.168.1.1",
                },
                "rh7-2": {
                    "IP": "192.168.1.2",
                },
            },
        )
        self.assert_pcs_result(
            "node attribute rh7-1 missing=".split(),
            stdout_full="",
            stderr_full="Error: attribute: 'missing' doesn't exist for node: 'rh7-1'\n",
            returncode=2,
        )

    def test_unset_nonexisting_forced(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {
                    "IP": "192.168.1.1",
                },
                "rh7-2": {
                    "IP": "192.168.1.2",
                },
            },
        )
        self.assert_pcs_success(
            "node attribute rh7-1 missing= --force".split(), ""
        )

    def test_keep_empty_nvset(self):
        self.assert_effect(
            "node attribute rh7-1 test=100".split(),
            self.fixture_xml_with_attrs(),
        )
        self.assert_effect(
            "node attribute rh7-1 test=".split(),
            self.fixture_xml_empty_attrs(),
        )

    def test_dont_create_nvset_on_removal(self):
        # pcs does not actually do cib editing, it passes it to crm_node. So
        # this behaves differently than the rest of pcs - instead of doing
        # nothing it returns an error.
        # Should be changed to be consistent with the rest of pcs.
        stdout, stderr, retval = pcs(
            self.temp_cib.name, "node attribute rh7-1 test=".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr, "Error: attribute: 'test' doesn't exist for node: 'rh7-1'\n"
        )
        self.assertEqual(retval, 2)
