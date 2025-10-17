from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs import settings
from pcs.lib import resource_agent as ra
from pcs.lib.external import CommandRunner
from pcs.lib.resource_agent.types import (
    ResourceAgentActionOcf1_0,
    ResourceAgentActionOcf1_1,
    ResourceAgentMetadataOcf1_0,
    ResourceAgentMetadataOcf1_1,
    ResourceAgentParameterOcf1_0,
    ResourceAgentParameterOcf1_1,
)

from pcs_test.tools.assertions import assert_xml_equal
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.xml import etree_to_str


class LoadMetadataXml(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success(self):
        agent_name = ra.ResourceAgentName("ocf", "pacemaker", "Dummy")
        metadata = """
            <resource-agent name="Dummy">
            </resource-agent>
        """
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:Dummy",
            stdout=metadata,
        )

        env = self.env_assist.get_env()
        self.assertEqual(
            # pylint: disable=protected-access
            ra.xml._load_metadata_xml(env.cmd_runner(), agent_name),
            metadata.strip(),
        )

    def test_failure(self):
        agent_name = ra.ResourceAgentName("ocf", "pacemaker", "Dummy")
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:Dummy",
            agent_is_missing=True,
            stderr="error message",
        )

        env = self.env_assist.get_env()
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            # pylint: disable=protected-access
            ra.xml._load_metadata_xml(env.cmd_runner(), agent_name)
        self.assertEqual(cm.exception.agent_name, "ocf:pacemaker:Dummy")
        self.assertEqual(cm.exception.message, "error message")


class LoadFakeAgentMetadataXml(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success(self):
        agent_name = ra.const.PACEMAKER_FENCED
        metadata = """
            <resource-agent name="pacemaker-fenced">
            </resource-agent>
        """
        self.config.runner.pcmk.load_fake_agent_metadata(
            agent_name="pacemaker-fenced", stdout=metadata
        )

        env = self.env_assist.get_env()
        self.assertEqual(
            # pylint: disable=protected-access
            ra.xml._load_fake_agent_metadata_xml(env.cmd_runner(), agent_name),
            metadata.strip(),
        )

    def test_failure(self):
        agent_name = ra.const.PACEMAKER_FENCED
        self.config.runner.pcmk.load_fake_agent_metadata(
            stdout="", stderr="error message"
        )

        env = self.env_assist.get_env()
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            # pylint: disable=protected-access
            ra.xml._load_fake_agent_metadata_xml(env.cmd_runner(), agent_name)
        self.assertEqual(cm.exception.agent_name, "pacemaker-fenced")
        self.assertEqual(cm.exception.message, "error message")

    def test_unknown_agent(self):
        agent_name = "unknown"

        env = self.env_assist.get_env()
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            # pylint: disable=protected-access
            ra.xml._load_fake_agent_metadata_xml(env.cmd_runner(), agent_name)
        self.assertEqual(cm.exception.agent_name, "unknown")
        self.assertEqual(cm.exception.message, "Unknown agent")


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class LoadCrmMetadataXmlBaseMixin:
    agent_name = None
    request_cmd = None

    def load_metadata(self, agent_name, stdout="", stderr="", returncode=0):
        raise NotImplementedError

    def call_function(self, agent_name):
        raise NotImplementedError()

    def setUp(self):
        self.maxDiff = None
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success(self):
        metadata = f"""
            <resource-agent name="{self.agent_name}">
              <version>1.1</version>
              <parameters>
                <parameter name="parameter-name" advanced="0" generated="0">
                  <longdesc lang="en">longdesc</longdesc>
                  <shortdesc lang="en">shortdesc</shortdesc>
                  <content type="string"/>
                </parameter>
              </parameters>
            </resource-agent>
        """
        api_result = f"""
            <pacemaker-result api-version="2.38" request="{self.request_cmd}">
                {metadata}
                <status code="0" message="OK" />
            </pacemaker-result>
        """

        self.load_metadata(self.agent_name, api_result.strip())
        assert_xml_equal(metadata, self.call_function(self.agent_name))

    def test_unknown_agent(self):
        agent_name = "unknown"
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            self.call_function(agent_name)
        self.assertEqual(cm.exception.agent_name, agent_name)
        self.assertEqual(cm.exception.message, "Unknown agent")

    def test_unable_to_get_api_result_dom(self):
        api_result = """
            <pacemaker-result api-version="2.38" request="crm_attribute">
                <resource-agent> bad metadata </resource-agent>
                <status code="0" message="OK" />
            </pacemaker-result>
        """
        self.load_metadata(self.agent_name, api_result, stderr="stderr")
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            self.call_function(self.agent_name)
        self.assertEqual(cm.exception.agent_name, self.agent_name)
        self.assertEqual(
            cm.exception.message, "\n".join(["stderr", api_result.strip()])
        )

    def test_api_result_errors(self):
        api_result = """
            <pacemaker-result api-version="2.38" request="crm_attribute">
                <status code="1" message="ERROR">
                    <errors>
                        <error>error 1</error>
                        <error>error 2</error>
                    </errors>
                </status>
            </pacemaker-result>
        """
        self.load_metadata(
            self.agent_name,
            stdout=api_result,
            stderr="stderr output",
            returncode=1,
        )
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            self.call_function(self.agent_name)
        self.assertEqual(cm.exception.agent_name, self.agent_name)
        self.assertEqual(cm.exception.message, "ERROR\nerror 1\nerror 2")

    def test_missing_resource_agent_element(self):
        api_result = """
            <pacemaker-result api-version="2.38" request="crm_attribute">
                <status code="0" message="OK" />
            </pacemaker-result>
        """
        self.load_metadata(self.agent_name, stdout=api_result)
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            self.call_function(self.agent_name)
        self.assertEqual(cm.exception.agent_name, self.agent_name)
        self.assertEqual(cm.exception.message, api_result.strip())


class LoadCrmResourceMetadataXml(LoadCrmMetadataXmlBaseMixin, TestCase):
    agent_name = ra.const.PRIMITIVE_META
    request_cmd = "crm_resource"

    def load_metadata(self, agent_name, stdout="", stderr="", returncode=0):
        self.config.runner.pcmk.load_crm_resource_metadata(
            agent_name=agent_name,
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
        )

    def call_function(self, agent_name):
        return ra.xml._load_crm_resource_metadata_xml(
            self.env_assist.get_env().cmd_runner(), agent_name
        )


class LoadCrmAttributeMetadataXml(LoadCrmMetadataXmlBaseMixin, TestCase):
    agent_name = ra.const.CLUSTER_OPTIONS
    request_cmd = "crm_attribute"

    def load_metadata(self, agent_name, stdout="", stderr="", returncode=0):
        self.config.runner.pcmk.load_crm_attribute_metadata(
            agent_name=agent_name,
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
        )

    def call_function(self, agent_name):
        return ra.xml._load_crm_attribute_metadata_xml(
            self.env_assist.get_env().cmd_runner(), agent_name
        )


class GetOcfVersion(TestCase):
    # pylint: disable=protected-access
    def test_no_version_element(self):
        self.assertEqual(
            ra.xml._get_ocf_version(
                etree.fromstring(
                    """
                        <resource-agent>
                        </resource-agent>
                    """
                )
            ),
            ra.const.OCF_1_0,
        )

    def test_version_element_empty(self):
        self.assertEqual(
            ra.xml._get_ocf_version(
                etree.fromstring(
                    """
                        <resource-agent>
                            <version/>
                        </resource-agent>
                    """
                )
            ),
            "",
        )

    def test_version_set(self):
        self.assertEqual(
            ra.xml._get_ocf_version(
                etree.fromstring(
                    """
                        <resource-agent>
                            <version> my version </version>
                        </resource-agent>
                    """
                )
            ),
            "my version",
        )

    def test_ignore_agent_version(self):
        self.assertEqual(
            ra.xml._get_ocf_version(
                etree.fromstring(
                    """
                        <resource-agent version="1.0">
                            <version>2.0</version>
                        </resource-agent>
                    """
                )
            ),
            "2.0",
        )


class MetadataXmlToDom(TestCase):
    # pylint: disable=protected-access
    def test_not_xml(self):
        with self.assertRaises(etree.XMLSyntaxError):
            ra.xml._metadata_xml_to_dom("not an xml")

    def test_no_version_not_valid(self):
        with self.assertRaises(etree.DocumentInvalid):
            ra.xml._metadata_xml_to_dom("<resource-agent/>")

    def test_no_version_valid(self):
        # pylint: disable=no-self-use
        metadata = """
            <resource-agent name="agent">
            </resource-agent>
        """
        assert_xml_equal(
            metadata, etree_to_str(ra.xml._metadata_xml_to_dom(metadata))
        )

    def test_ocf_1_0_not_valid(self):
        with self.assertRaises(etree.DocumentInvalid):
            ra.xml._metadata_xml_to_dom(
                """
                    <resource-agent>
                        <version>1.0</version>
                    </resource-agent>
                """
            )

    def test_ocf_1_0_valid(self):
        # pylint: disable=no-self-use
        metadata = """
            <resource-agent name="agent">
                <version>1.0</version>
            </resource-agent>
        """
        assert_xml_equal(
            metadata, etree_to_str(ra.xml._metadata_xml_to_dom(metadata))
        )

    def test_ocf_1_1_not_valid(self):
        with self.assertRaises(etree.DocumentInvalid):
            ra.xml._metadata_xml_to_dom(
                """
                    <resource-agent>
                        <version>1.1</version>
                    </resource-agent>
                """
            )

    def test_ocf_1_1_valid(self):
        # pylint: disable=no-self-use
        metadata = """
            <resource-agent name="agent">
                <version>1.1</version>
                <parameters>
                    <parameter name="test" unique-group="ug1"/>
                </parameters>
            </resource-agent>
        """
        assert_xml_equal(
            metadata, etree_to_str(ra.xml._metadata_xml_to_dom(metadata))
        )


class LoadMetadata(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success(self):
        agent_name = ra.ResourceAgentName("ocf", "pacemaker", "Dummy")
        metadata = """
            <resource-agent name="Dummy">
            </resource-agent>
        """
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:Dummy",
            stdout=metadata,
        )

        env = self.env_assist.get_env()
        assert_xml_equal(
            metadata,
            etree_to_str(ra.xml.load_metadata(env.cmd_runner(), agent_name)),
        )

    def test_cannot_load(self):
        agent_name = ra.ResourceAgentName("ocf", "pacemaker", "Dummy")
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:Dummy",
            agent_is_missing=True,
            stderr="error message",
        )

        env = self.env_assist.get_env()
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            ra.xml.load_metadata(env.cmd_runner(), agent_name)
        self.assertEqual(cm.exception.agent_name, "ocf:pacemaker:Dummy")
        self.assertEqual(cm.exception.message, "error message")

    def test_not_xml(self):
        agent_name = ra.ResourceAgentName("ocf", "pacemaker", "Dummy")
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:Dummy",
            stdout="this is not an xml",
        )

        env = self.env_assist.get_env()
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            ra.xml.load_metadata(env.cmd_runner(), agent_name)
        self.assertEqual(cm.exception.agent_name, "ocf:pacemaker:Dummy")
        self.assertTrue(cm.exception.message.startswith("Start tag expected"))

    def test_not_valid_xml(self):
        agent_name = ra.ResourceAgentName("ocf", "pacemaker", "Dummy")
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:Dummy",
            stdout="<resource-agent/>",
        )

        env = self.env_assist.get_env()
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            ra.xml.load_metadata(env.cmd_runner(), agent_name)
        self.assertEqual(cm.exception.agent_name, "ocf:pacemaker:Dummy")
        self.assertTrue(
            cm.exception.message.startswith(
                "Element resource-agent failed to validate"
            )
        )


class LoadFakeAgentMetadata(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success(self):
        agent_name = ra.const.PACEMAKER_FENCED
        metadata = """
            <resource-agent name="pacemaker-fenced">
            </resource-agent>
        """
        self.config.runner.pcmk.load_fake_agent_metadata(stdout=metadata)

        env = self.env_assist.get_env()
        assert_xml_equal(
            metadata,
            etree_to_str(
                ra.xml.load_fake_agent_metadata(env.cmd_runner(), agent_name)
            ),
        )

    def test_cannot_load(self):
        agent_name = ra.const.PACEMAKER_FENCED
        self.config.runner.pcmk.load_fake_agent_metadata(
            stdout="", stderr="error message"
        )

        env = self.env_assist.get_env()
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            ra.xml.load_fake_agent_metadata(env.cmd_runner(), agent_name)
        self.assertEqual(cm.exception.agent_name, "pacemaker-fenced")
        self.assertEqual(cm.exception.message, "error message")

    def test_not_xml(self):
        agent_name = ra.const.PACEMAKER_FENCED
        self.config.runner.pcmk.load_fake_agent_metadata(
            stdout="this is not an xml"
        )

        env = self.env_assist.get_env()
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            ra.xml.load_fake_agent_metadata(env.cmd_runner(), agent_name)
        self.assertEqual(cm.exception.agent_name, "pacemaker-fenced")
        self.assertTrue(cm.exception.message.startswith("Start tag expected"))

    def test_not_valid_xml(self):
        agent_name = ra.const.PACEMAKER_FENCED
        self.config.runner.pcmk.load_fake_agent_metadata(
            stdout="<resource-agent/>"
        )

        env = self.env_assist.get_env()
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            ra.xml.load_fake_agent_metadata(env.cmd_runner(), agent_name)
        self.assertEqual(cm.exception.agent_name, "pacemaker-fenced")
        self.assertTrue(
            cm.exception.message.startswith(
                "Element resource-agent failed to validate"
            )
        )


class ParseOcfToolsMixin:
    agent_name = ra.ResourceAgentName("ocf", "pacemaker", "Dummy")
    ocf_version = None

    def parse(self, xml, agent_name=None):
        agent_name = agent_name or self.agent_name
        if not agent_name:
            raise AssertionError(
                "Invalid test usage, agent_name must be specified"
            )
        with mock.patch(
            "pcs.lib.resource_agent.xml._load_metadata_xml"
        ) as mock_load:
            mock_load.return_value = xml
            return ra.xml.parse_metadata(
                agent_name,
                ra.xml.load_metadata(
                    mock.MagicMock(spec=CommandRunner), agent_name
                ),
            )

    def xml(self, xml, agent_name=None, ocf_version=None):
        agent_name = agent_name or self.agent_name
        ocf_version = ocf_version or self.ocf_version
        dom = etree.fromstring(xml)
        if agent_name:
            dom.set("name", agent_name.full_name)
        if ocf_version:
            version_el = dom.find("./version")
            if version_el is None:
                version_el = etree.Element("version")
                dom.insert(0, version_el)
            version_el.text = ocf_version
        return etree_to_str(dom)


class ParseOcfGeneric(ParseOcfToolsMixin, TestCase):
    def test_unsupported_ocf_version(self):
        with self.assertRaises(ra.UnsupportedOcfVersion) as cm:
            self.parse(self.xml("""<resource-agent/>""", ocf_version="1.2"))
        self.assertEqual(cm.exception.agent_name, self.agent_name.full_name)
        self.assertEqual(cm.exception.ocf_version, "1.2")


class ParseOcf10BaseMixin(ParseOcfToolsMixin):
    def test_empty_agent(self):
        self.assertEqual(
            self.parse(self.xml("""<resource-agent/>""")),
            ResourceAgentMetadataOcf1_0(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[],
                actions=[],
            ),
        )

    def test_desc_element(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <shortdesc>This is a shortdesc</shortdesc>
                            <longdesc>This is a longdesc</longdesc>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_0(
                self.agent_name,
                shortdesc="This is a shortdesc",
                longdesc="This is a longdesc",
                parameters=[],
                actions=[],
            ),
        )

    def test_desc_element_empty(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <longdesc/>
                            <shortdesc/>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_0(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[],
                actions=[],
            ),
        )

    def test_desc_attribute(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent shortdesc="This is a shortdesc">
                            <longdesc></longdesc>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_0(
                self.agent_name,
                shortdesc="This is a shortdesc",
                longdesc=None,
                parameters=[],
                actions=[],
            ),
        )

    def test_desc_attribute_empty(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent shortdesc=""/>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_0(
                self.agent_name,
                shortdesc="",
                longdesc=None,
                parameters=[],
                actions=[],
            ),
        )

    def test_desc_element_and_attribute(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent shortdesc="shortdesc attribute">
                            <shortdesc>shortdesc element</shortdesc>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_0(
                self.agent_name,
                shortdesc="shortdesc element",
                longdesc=None,
                parameters=[],
                actions=[],
            ),
        )

    def test_desc_element_empty_and_attribute(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent shortdesc="shortdesc attribute">
                            <shortdesc></shortdesc>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_0(
                self.agent_name,
                shortdesc="shortdesc attribute",
                longdesc=None,
                parameters=[],
                actions=[],
            ),
        )

    def test_desc_element_empty_and_attribute_empty(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent shortdesc="">
                            <shortdesc></shortdesc>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_0(
                self.agent_name,
                shortdesc="",
                longdesc=None,
                parameters=[],
                actions=[],
            ),
        )

    def test_parameters_empty_list(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <parameters/>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_0(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[],
                actions=[],
            ),
        )

    def test_parameters_empty_parameter(self):
        # parameters must have at least 'name' attribute
        with self.assertRaises(ra.UnableToGetAgentMetadata):
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <parameters>
                                <parameter/>
                            </parameters>
                        </resource-agent>
                    """
                )
            )

    def test_parameters_minimal(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <parameters>
                                <parameter name="a_parameter"/>
                            </parameters>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_0(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[
                    ResourceAgentParameterOcf1_0(
                        name="a_parameter",
                        shortdesc=None,
                        longdesc=None,
                        type="string",
                        default=None,
                        enum_values=None,
                        required=None,
                        deprecated=None,
                        obsoletes=None,
                        unique=None,
                    )
                ],
                actions=[],
            ),
        )

    def test_parameters_all_settings(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <parameters>
                                <parameter name="a_parameter" required="1"
                                    unique="0" deprecated="1" obsoletes="old"
                                >
                                    <longdesc>Long description</longdesc>
                                    <shortdesc>short description</shortdesc>
                                    <content type="integer" default="123"/>
                                </parameter>
                            </parameters>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_0(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[
                    ResourceAgentParameterOcf1_0(
                        name="a_parameter",
                        shortdesc="short description",
                        longdesc="Long description",
                        type="integer",
                        default="123",
                        enum_values=None,
                        required="1",
                        deprecated="1",
                        obsoletes="old",
                        unique="0",
                    )
                ],
                actions=[],
            ),
        )

    def test_parameters_content(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <parameters>
                                <parameter name="with_type">
                                    <content type="integer"/>
                                </parameter>
                                <parameter name="with_select">
                                    <content type="select" default="b">
                                        <option value="a"/>
                                        <option value="b"/>
                                        <option value="c"/>
                                    </content>
                                </parameter>
                            </parameters>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_0(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[
                    ResourceAgentParameterOcf1_0(
                        name="with_type",
                        shortdesc=None,
                        longdesc=None,
                        type="integer",
                        default=None,
                        enum_values=None,
                        required=None,
                        deprecated=None,
                        obsoletes=None,
                        unique=None,
                    ),
                    ResourceAgentParameterOcf1_0(
                        name="with_select",
                        shortdesc=None,
                        longdesc=None,
                        type="select",
                        default="b",
                        enum_values=["a", "b", "c"],
                        required=None,
                        deprecated=None,
                        obsoletes=None,
                        unique=None,
                    ),
                ],
                actions=[],
            ),
        )

    def test_actions_empty_list(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <actions/>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_0(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[],
                actions=[],
            ),
        )

    def test_actions_empty_action(self):
        # actions must have at least 'name' attribute
        with self.assertRaises(ra.UnableToGetAgentMetadata):
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <actions>
                                <action/>
                            </actions>
                        </resource-agent>
                    """
                )
            )

    def test_actions_multiple(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <actions>
                                <action name="minimal"/>
                                <action name="maximal" timeout="1" interval="2"
                                    start-delay="3" depth="4" role="Master"
                                />
                                <action name="stonith_special"
                                    automatic="0" on_target="1"
                                />
                            </actions>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_0(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[],
                actions=[
                    ResourceAgentActionOcf1_0(
                        name="minimal",
                        timeout=None,
                        interval=None,
                        role=None,
                        start_delay=None,
                        depth=None,
                        automatic=None,
                        on_target=None,
                    ),
                    ResourceAgentActionOcf1_0(
                        name="maximal",
                        timeout="1",
                        interval="2",
                        role="Master",
                        start_delay="3",
                        depth="4",
                        automatic=None,
                        on_target=None,
                    ),
                    ResourceAgentActionOcf1_0(
                        name="stonith_special",
                        timeout=None,
                        interval=None,
                        role=None,
                        start_delay=None,
                        depth=None,
                        automatic="0",
                        on_target="1",
                    ),
                ],
            ),
        )


class ParseOcf10NoVersion(ParseOcf10BaseMixin, TestCase):
    pass


class ParseOcf10ExplicitVersion(ParseOcf10BaseMixin, TestCase):
    ocf_version = "1.0"


class ParseOcf11(ParseOcfToolsMixin, TestCase):
    ocf_version = "1.1"

    def test_empty_agent(self):
        self.assertEqual(
            self.parse(self.xml("""<resource-agent/>""")),
            ResourceAgentMetadataOcf1_1(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[],
                actions=[],
            ),
        )

    def test_desc_element(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <shortdesc>This is a shortdesc</shortdesc>
                            <longdesc>This is a longdesc</longdesc>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_1(
                self.agent_name,
                shortdesc="This is a shortdesc",
                longdesc="This is a longdesc",
                parameters=[],
                actions=[],
            ),
        )

    def test_desc_element_empty(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <longdesc/>
                            <shortdesc/>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_1(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[],
                actions=[],
            ),
        )

    def test_parameters_empty_list(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <parameters/>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_1(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[],
                actions=[],
            ),
        )

    def test_parameters_empty_parameter(self):
        # parameters must have at least 'name' attribute
        with self.assertRaises(ra.UnableToGetAgentMetadata):
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <parameters>
                                <parameter/>
                            </parameters>
                        </resource-agent>
                    """
                )
            )

    def test_parameters_minimal(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <parameters>
                                <parameter name="a_parameter"/>
                            </parameters>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_1(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[
                    ResourceAgentParameterOcf1_1(
                        name="a_parameter",
                        shortdesc=None,
                        longdesc=None,
                        type="string",
                        default=None,
                        enum_values=None,
                        required=None,
                        advanced=None,
                        deprecated=False,
                        deprecated_by=[],
                        deprecated_desc=None,
                        unique_group=None,
                        reloadable=None,
                    )
                ],
                actions=[],
            ),
        )

    def test_parameters_deprecated_minimal(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <parameters>
                                <parameter name="a_parameter">
                                    <deprecated/>
                                </parameter>
                            </parameters>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_1(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[
                    ResourceAgentParameterOcf1_1(
                        name="a_parameter",
                        shortdesc=None,
                        longdesc=None,
                        type="string",
                        default=None,
                        enum_values=None,
                        required=None,
                        advanced=None,
                        deprecated=True,
                        deprecated_by=[],
                        deprecated_desc=None,
                        unique_group=None,
                        reloadable=None,
                    )
                ],
                actions=[],
            ),
        )

    def test_parameters_deprecated_replaced_with(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <parameters>
                                <parameter name="a_parameter">
                                    <deprecated>
                                        <replaced-with name="new1"/>
                                        <replaced-with name="new2"/>
                                    </deprecated>
                                </parameter>
                            </parameters>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_1(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[
                    ResourceAgentParameterOcf1_1(
                        name="a_parameter",
                        shortdesc=None,
                        longdesc=None,
                        type="string",
                        default=None,
                        enum_values=None,
                        required=None,
                        advanced=None,
                        deprecated=True,
                        deprecated_by=["new1", "new2"],
                        deprecated_desc=None,
                        unique_group=None,
                        reloadable=None,
                    )
                ],
                actions=[],
            ),
        )

    def test_parameters_all_settings(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <parameters>
                                <parameter name="a_parameter"
                                    unique-group="ug1" unique="0" required="1"
                                    reloadable="0" advanced="1" generated="1"
                                >
                                    <longdesc>Long description</longdesc>
                                    <shortdesc>short description</shortdesc>
                                    <deprecated>
                                        <replaced-with name="new1"/>
                                        <replaced-with name="new2"/>
                                        <desc>deprecation explanation</desc>
                                    </deprecated>
                                    <content type="integer" default="123"/>
                                </parameter>
                            </parameters>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_1(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[
                    ResourceAgentParameterOcf1_1(
                        name="a_parameter",
                        shortdesc="short description",
                        longdesc="Long description",
                        type="integer",
                        default="123",
                        enum_values=None,
                        required="1",
                        advanced="1",
                        deprecated=True,
                        deprecated_by=["new1", "new2"],
                        deprecated_desc="deprecation explanation",
                        unique_group="ug1",
                        reloadable="0",
                    )
                ],
                actions=[],
            ),
        )

    def test_parameters_content(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <parameters>
                                <parameter name="with_type">
                                    <content type="integer"/>
                                </parameter>
                                <parameter name="with_select">
                                    <content type="select" default="b">
                                        <option value="a"/>
                                        <option value="b"/>
                                        <option value="c"/>
                                    </content>
                                </parameter>
                            </parameters>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_1(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[
                    ResourceAgentParameterOcf1_1(
                        name="with_type",
                        shortdesc=None,
                        longdesc=None,
                        type="integer",
                        default=None,
                        enum_values=None,
                        required=None,
                        advanced=None,
                        deprecated=False,
                        deprecated_by=[],
                        deprecated_desc=None,
                        unique_group=None,
                        reloadable=None,
                    ),
                    ResourceAgentParameterOcf1_1(
                        name="with_select",
                        shortdesc=None,
                        longdesc=None,
                        type="select",
                        default="b",
                        enum_values=["a", "b", "c"],
                        required=None,
                        advanced=None,
                        deprecated=False,
                        deprecated_by=[],
                        deprecated_desc=None,
                        unique_group=None,
                        reloadable=None,
                    ),
                ],
                actions=[],
            ),
        )

    def test_actions_empty_list(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <actions/>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_1(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[],
                actions=[],
            ),
        )

    def test_actions_empty_action(self):
        # actions must have at least 'name' attribute
        with self.assertRaises(ra.UnableToGetAgentMetadata):
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <actions>
                                <action/>
                            </actions>
                        </resource-agent>
                    """
                )
            )

    def test_actions_multiple(self):
        self.assertEqual(
            self.parse(
                self.xml(
                    """
                        <resource-agent>
                            <actions>
                                <action name="minimal"/>
                                <action name="maximal" timeout="1" interval="2"
                                    start-delay="3" depth="4" role="whatever"
                                />
                                <action name="stonith_special"
                                    automatic="0" on_target="1"
                                />
                            </actions>
                        </resource-agent>
                    """
                )
            ),
            ResourceAgentMetadataOcf1_1(
                self.agent_name,
                shortdesc=None,
                longdesc=None,
                parameters=[],
                actions=[
                    ResourceAgentActionOcf1_1(
                        name="minimal",
                        timeout=None,
                        interval=None,
                        role=None,
                        start_delay=None,
                        depth=None,
                        automatic=None,
                        on_target=None,
                    ),
                    ResourceAgentActionOcf1_1(
                        name="maximal",
                        timeout="1",
                        interval="2",
                        role="whatever",
                        start_delay="3",
                        depth="4",
                        automatic=None,
                        on_target=None,
                    ),
                    ResourceAgentActionOcf1_1(
                        name="stonith_special",
                        timeout=None,
                        interval=None,
                        role=None,
                        start_delay=None,
                        depth=None,
                        automatic="0",
                        on_target="1",
                    ),
                ],
            ),
        )
