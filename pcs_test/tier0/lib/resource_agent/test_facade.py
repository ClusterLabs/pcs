from unittest import (
    TestCase,
    mock,
)

from pcs.common import reports
from pcs.lib import resource_agent as ra

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


@mock.patch("pcs.lib.resource_agent.facade.ocf_unified_to_pcs")
class ResourceAgentFacade(TestCase):
    # Methods returning validators are not tested here. They are tested
    # indirectly in tests for methods calling them.

    @staticmethod
    def _fixture_metadata(shortdesc, parameters):
        return ra.ResourceAgentMetadata(
            ra.ResourceAgentName("standard", "provider", "type"),
            agent_exists=True,
            ocf_version=ra.const.OCF_1_0,
            shortdesc=shortdesc,
            longdesc=None,
            parameters=parameters,
            actions=[],
        )

    @staticmethod
    def _fixture_parameter(name):
        return ra.ResourceAgentParameter(
            name,
            shortdesc=None,
            longdesc=None,
            type="string",
            default=None,
            enum_values=None,
            required=False,
            advanced=False,
            deprecated=False,
            deprecated_by=[],
            deprecated_desc=None,
            unique_group=None,
            reloadable=False,
        )

    def test_metadata_transformation(self, mock_ocf_transform):
        metadata_in = self._fixture_metadata("raw metadata", [])
        metadata_out = self._fixture_metadata("transformed metadata", [])
        mock_ocf_transform.return_value = metadata_out

        facade = ra.ResourceAgentFacade(metadata_in, [])
        self.assertEqual(facade.metadata, metadata_out)
        mock_ocf_transform.assert_called_once_with(metadata_in)

        # transformation is cached
        mock_ocf_transform.reset_mock()
        self.assertEqual(facade.metadata, metadata_out)
        mock_ocf_transform.assert_not_called()

    def test_add_additional_params(self, mock_ocf_transform):
        metadata_in = self._fixture_metadata(
            "raw metadata", [self._fixture_parameter("param1")]
        )
        metadata_transformed = self._fixture_metadata(
            "transformed metadata", [self._fixture_parameter("param1")]
        )
        metadata_out = self._fixture_metadata(
            "transformed metadata",
            [
                self._fixture_parameter("param1"),
                self._fixture_parameter("param2"),
            ],
        )
        mock_ocf_transform.return_value = metadata_transformed

        facade = ra.ResourceAgentFacade(
            metadata_in, [self._fixture_parameter("param2")]
        )
        self.assertEqual(facade.metadata, metadata_out)
        mock_ocf_transform.assert_called_once_with(metadata_in)

        # transformation is cached
        mock_ocf_transform.reset_mock()
        self.assertEqual(facade.metadata, metadata_out)
        mock_ocf_transform.assert_not_called()


class ResourceAgentFacadeFactory(TestCase):
    _fixture_agent_xml = """
        <resource-agent name="agent">
            <parameters>
                <parameter name="agent-param"/>
            </parameters>
        </resource-agent>
    """
    _fixture_fenced_xml = """
        <resource-agent name="pacemaker-fenced">
            <parameters>
                <parameter name="fenced-param"/>
            </parameters>
        </resource-agent>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_void(self):
        name = ra.ResourceAgentName("service", None, "daemon")
        env = self.env_assist.get_env()
        facade = ra.ResourceAgentFacadeFactory(
            env.cmd_runner(), env.report_processor
        ).void_facade_from_parsed_name(name)
        self.assertEqual(facade.metadata.name, name)
        self.assertFalse(facade.metadata.agent_exists)

    def test_facade(self):
        name = ra.ResourceAgentName("service", None, "daemon")
        self.config.runner.pcmk.load_agent(
            agent_name="service:daemon", stdout=self._fixture_agent_xml
        )

        env = self.env_assist.get_env()
        facade = ra.ResourceAgentFacadeFactory(
            env.cmd_runner(), env.report_processor
        ).facade_from_parsed_name(name)
        self.assertEqual(facade.metadata.name, name)
        self.assertTrue(facade.metadata.agent_exists)

    def test_facade_crm_attribute(self):
        agent_name = "cluster-options"
        fake_agent_name = ra.ResourceAgentName(
            ra.const.FAKE_AGENT_STANDARD, None, agent_name
        )
        self.config.runner.pcmk.load_crm_attribute_metadata(
            agent_name=agent_name
        )
        env = self.env_assist.get_env()
        facade = ra.ResourceAgentFacadeFactory(
            env.cmd_runner(), env.report_processor
        ).facade_from_crm_attribute(agent_name)
        self.assertEqual(facade.metadata.name, fake_agent_name)
        self.assertTrue(facade.metadata.agent_exists)
        self.assertTrue(
            {
                "enable-acl",
                "stonith-watchdog-timeout",
                "maintenance-mode",
            }.issubset({param.name for param in facade.metadata.parameters})
        )

    def test_facade_crm_attribute_unknown_agent(self):
        agent_name = "unknown"
        env = self.env_assist.get_env()
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            ra.ResourceAgentFacadeFactory(
                env.cmd_runner(), env.report_processor
            ).facade_from_crm_attribute(agent_name)
        self.assertEqual(cm.exception.agent_name, agent_name)

    def test_facade_missing_agent(self):
        name = ra.ResourceAgentName("service", None, "daemon")
        self.config.runner.pcmk.load_agent(
            agent_name="service:daemon", agent_is_missing=True
        )

        env = self.env_assist.get_env()
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            ra.ResourceAgentFacadeFactory(
                env.cmd_runner(), env.report_processor
            ).facade_from_parsed_name(name)
        self.assertEqual(cm.exception.agent_name, name.full_name)

    def test_void_load_and_cache_fenced_for_stonith(self):
        name1 = ra.ResourceAgentName("stonith", None, "fence_xvm")
        name2 = ra.ResourceAgentName("stonith", None, "fence_virt")
        self.config.runner.pcmk.load_fake_agent_metadata(
            stdout=self._fixture_fenced_xml
        )

        env = self.env_assist.get_env()
        factory = ra.ResourceAgentFacadeFactory(
            env.cmd_runner(), env.report_processor
        )
        facade1 = factory.void_facade_from_parsed_name(name1)
        facade2 = factory.void_facade_from_parsed_name(name2)

        self.assertEqual(facade1.metadata.name, name1)
        self.assertEqual(facade2.metadata.name, name2)
        self.assertFalse(facade1.metadata.agent_exists)
        self.assertFalse(facade2.metadata.agent_exists)
        self.assertEqual(
            [param.name for param in facade1.metadata.parameters],
            ["fenced-param"],
        )
        self.assertEqual(
            [param.name for param in facade2.metadata.parameters],
            ["fenced-param"],
        )

    def test_facade_load_and_cache_fenced_for_stonith(self):
        name1 = ra.ResourceAgentName("stonith", None, "fence_xvm")
        name2 = ra.ResourceAgentName("stonith", None, "fence_virt")
        self.config.runner.pcmk.load_agent(
            agent_name="stonith:fence_xvm",
            stdout=self._fixture_agent_xml,
            name="runner.pcmk.load_agent.xvm",
        )
        self.config.runner.pcmk.load_fake_agent_metadata(
            stdout=self._fixture_fenced_xml
        )
        self.config.runner.pcmk.load_agent(
            agent_name="stonith:fence_virt",
            stdout=self._fixture_agent_xml,
            name="runner.pcmk.load_agent.virt",
        )

        env = self.env_assist.get_env()
        factory = ra.ResourceAgentFacadeFactory(
            env.cmd_runner(), env.report_processor
        )
        facade1 = factory.facade_from_parsed_name(name1)
        facade2 = factory.facade_from_parsed_name(name2)

        self.assertEqual(facade1.metadata.name, name1)
        self.assertEqual(facade2.metadata.name, name2)
        self.assertTrue(facade1.metadata.agent_exists)
        self.assertTrue(facade2.metadata.agent_exists)
        self.assertEqual(
            [param.name for param in facade1.metadata.parameters],
            ["agent-param", "fenced-param"],
        )
        self.assertEqual(
            [param.name for param in facade2.metadata.parameters],
            ["agent-param", "fenced-param"],
        )

    def test_void_load_and_cache_fenced_for_stonith_failure(self):
        name1 = ra.ResourceAgentName("stonith", None, "fence_xvm")
        name2 = ra.ResourceAgentName("stonith", None, "fence_virt")
        self.config.runner.pcmk.load_fake_agent_metadata(
            stdout="", stderr="fenced failure", returncode=1
        )

        env = self.env_assist.get_env()
        factory = ra.ResourceAgentFacadeFactory(
            env.cmd_runner(), env.report_processor
        )
        facade1 = factory.void_facade_from_parsed_name(name1)
        facade2 = factory.void_facade_from_parsed_name(name2)

        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.UNABLE_TO_GET_AGENT_METADATA,
                    agent="pacemaker-fenced",
                    reason="fenced failure",
                )
            ]
        )
        self.assertEqual(facade1.metadata.name, name1)
        self.assertEqual(facade2.metadata.name, name2)
        self.assertFalse(facade1.metadata.agent_exists)
        self.assertFalse(facade2.metadata.agent_exists)
        self.assertEqual(
            [param.name for param in facade1.metadata.parameters],
            [],
        )
        self.assertEqual(
            [param.name for param in facade2.metadata.parameters],
            [],
        )

    def test_facade_load_and_cache_fenced_for_stonith_failure(self):
        name1 = ra.ResourceAgentName("stonith", None, "fence_xvm")
        name2 = ra.ResourceAgentName("stonith", None, "fence_virt")
        self.config.runner.pcmk.load_agent(
            agent_name="stonith:fence_xvm",
            stdout=self._fixture_agent_xml,
            name="runner.pcmk.load_agent.xvm",
        )
        self.config.runner.pcmk.load_fake_agent_metadata(
            stdout="", stderr="fenced failure", returncode=1
        )
        self.config.runner.pcmk.load_agent(
            agent_name="stonith:fence_virt",
            stdout=self._fixture_agent_xml,
            name="runner.pcmk.load_agent.virt",
        )

        env = self.env_assist.get_env()
        factory = ra.ResourceAgentFacadeFactory(
            env.cmd_runner(), env.report_processor
        )
        facade1 = factory.facade_from_parsed_name(name1)
        facade2 = factory.facade_from_parsed_name(name2)

        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.UNABLE_TO_GET_AGENT_METADATA,
                    agent="pacemaker-fenced",
                    reason="fenced failure",
                )
            ]
        )
        self.assertEqual(facade1.metadata.name, name1)
        self.assertEqual(facade2.metadata.name, name2)
        self.assertTrue(facade1.metadata.agent_exists)
        self.assertTrue(facade2.metadata.agent_exists)
        self.assertEqual(
            [param.name for param in facade1.metadata.parameters],
            ["agent-param"],
        )
        self.assertEqual(
            [param.name for param in facade2.metadata.parameters],
            ["agent-param"],
        )

    def test_void_add_trace_for_ocf(self):
        env = self.env_assist.get_env()
        for provider in ["heartbeat", "pacemaker"]:
            with self.subTest(provider=provider):
                name = ra.ResourceAgentName("ocf", provider, "Dummy")
                facade = ra.ResourceAgentFacadeFactory(
                    env.cmd_runner(), env.report_processor
                ).void_facade_from_parsed_name(name)
                self.assertEqual(facade.metadata.name, name)
                self.assertFalse(facade.metadata.agent_exists)
                self.assertEqual(
                    [param.name for param in facade.metadata.parameters],
                    ["trace_ra", "trace_file"],
                )

    def test_facade_add_trace_for_ocf(self):
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:heartbeat:Dummy",
            stdout=self._fixture_agent_xml,
            name="runner.pcmk.load_agent.heartbeat",
        )
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:Dummy",
            stdout=self._fixture_agent_xml,
            name="runner.pcmk.load_agent.pacemaker",
        )
        env = self.env_assist.get_env()

        for provider in ["heartbeat", "pacemaker"]:
            with self.subTest(provider=provider):
                name = ra.ResourceAgentName("ocf", provider, "Dummy")
                facade = ra.ResourceAgentFacadeFactory(
                    env.cmd_runner(), env.report_processor
                ).facade_from_parsed_name(name)
                self.assertEqual(facade.metadata.name, name)
                self.assertTrue(facade.metadata.agent_exists)
                self.assertEqual(
                    [param.name for param in facade.metadata.parameters],
                    ["agent-param", "trace_ra", "trace_file"],
                )

    def test_void_not_add_trace_for_ocf(self):
        name = ra.ResourceAgentName("ocf", "openstack", "Dummy")
        env = self.env_assist.get_env()
        facade = ra.ResourceAgentFacadeFactory(
            env.cmd_runner(), env.report_processor
        ).void_facade_from_parsed_name(name)
        self.assertEqual(facade.metadata.name, name)
        self.assertFalse(facade.metadata.agent_exists)
        self.assertEqual(
            [param.name for param in facade.metadata.parameters],
            [],
        )

    def test_facade_not_add_trace_for_ocf(self):
        name = ra.ResourceAgentName("ocf", "openstack", "Dummy")
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:openstack:Dummy", stdout=self._fixture_agent_xml
        )
        env = self.env_assist.get_env()

        facade = ra.ResourceAgentFacadeFactory(
            env.cmd_runner(), env.report_processor
        ).facade_from_parsed_name(name)
        self.assertEqual(facade.metadata.name, name)
        self.assertTrue(facade.metadata.agent_exists)
        self.assertEqual(
            [param.name for param in facade.metadata.parameters],
            ["agent-param"],
        )


class GetCrmResourceMetadata(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def _test_get_crm_resource_metadata(self, is_fencing):
        agent_name = "primitive-meta"
        fake_agent_name = ra.ResourceAgentName(
            ra.const.FAKE_AGENT_STANDARD, None, agent_name
        )
        self.config.runner.pcmk.load_crm_resource_metadata(
            agent_name=agent_name
        )
        env = self.env_assist.get_env()
        metadata = ra.get_crm_resource_metadata(
            env.cmd_runner(), agent_name, is_fencing
        )
        self.assertEqual(metadata.name, fake_agent_name)
        self.assertTrue(metadata.agent_exists)
        parameters_name_set = {param.name for param in metadata.parameters}
        self.assertTrue(
            {"priority", "critical", "target-role"}.issubset(
                parameters_name_set
            )
        )
        self.assertEqual("provides" in parameters_name_set, is_fencing)

    def test_get_crm_resource_metadata_is_not_fencing(self):
        self._test_get_crm_resource_metadata(False)

    def test_get_crm_resource_metadata_is_fencing(self):
        self._test_get_crm_resource_metadata(True)

    def test_get_crm_resource_metadata_unknown_agent(self):
        agent_name = "unknown"
        env = self.env_assist.get_env()
        with self.assertRaises(ra.UnableToGetAgentMetadata) as cm:
            ra.get_crm_resource_metadata(env.cmd_runner(), agent_name, False)
        self.assertEqual(cm.exception.agent_name, agent_name)
