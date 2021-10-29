from unittest import TestCase

from pcs.lib.resource_agent import (
    const,
    InvalidResourceAgentName,
    ResourceAgentMetadata,
    ResourceAgentName,
    split_resource_agent_name,
)
from pcs.lib.resource_agent.name import name_to_void_metadata


class SplitResourceAgentName(TestCase):
    def test_returns_resource_agent_name_when_is_valid(self):
        self.assertEqual(
            ResourceAgentName("ocf", "heartbeat", "Dummy"),
            split_resource_agent_name("ocf:heartbeat:Dummy"),
        )

    def test_refuses_string_if_is_not_valid(self):
        self.assertRaises(
            InvalidResourceAgentName,
            lambda: split_resource_agent_name("invalid:resource:agent:string"),
        )

    def test_refuses_with_unknown_standard(self):
        self.assertRaises(
            InvalidResourceAgentName,
            lambda: split_resource_agent_name("unknown:Dummy"),
        )

    def test_refuses_ocf_agent_name_without_provider(self):
        self.assertRaises(
            InvalidResourceAgentName,
            lambda: split_resource_agent_name("ocf:Dummy"),
        )

    def test_refuses_non_ocf_agent_name_with_provider(self):
        self.assertRaises(
            InvalidResourceAgentName,
            lambda: split_resource_agent_name("lsb:provider:Dummy"),
        )

    def test_returns_resource_agent_containing_sytemd(self):
        self.assertEqual(
            ResourceAgentName("systemd", None, "lvm2-pvscan"),
            split_resource_agent_name("systemd:lvm2-pvscan"),
        )

    def test_returns_resource_agent_containing_sytemd_instance(self):
        self.assertEqual(
            ResourceAgentName("systemd", None, "lvm2-pvscan@252:2"),
            split_resource_agent_name("systemd:lvm2-pvscan@252:2"),
        )

    def test_returns_resource_agent_containing_service(self):
        self.assertEqual(
            ResourceAgentName("service", None, "lvm2-pvscan"),
            split_resource_agent_name("service:lvm2-pvscan"),
        )

    def test_returns_resource_agent_containing_service_instance(self):
        self.assertEqual(
            ResourceAgentName("service", None, "lvm2-pvscan@252:2"),
            split_resource_agent_name("service:lvm2-pvscan@252:2"),
        )

    def test_returns_resource_agent_containing_systemd_instance_short(self):
        self.assertEqual(
            ResourceAgentName("service", None, "getty@tty1"),
            split_resource_agent_name("service:getty@tty1"),
        )

    def test_refuses_systemd_agent_name_with_provider(self):
        self.assertRaises(
            InvalidResourceAgentName,
            lambda: split_resource_agent_name("sytemd:provider:lvm2-pvscan252"),
        )

    def test_refuses_systemd_agent_name_with_provider_and_instance(self):
        self.assertRaises(
            InvalidResourceAgentName,
            lambda: split_resource_agent_name(
                "sytemd:provider:lvm2-pvscan252@252:2"
            ),
        )

    def test_refuses_service_agent_name_with_provider(self):
        self.assertRaises(
            InvalidResourceAgentName,
            lambda: split_resource_agent_name(
                "service:provider:lvm2-pvscan252"
            ),
        )

    def test_refuses_service_agent_name_with_provider_and_instance(self):
        self.assertRaises(
            InvalidResourceAgentName,
            lambda: split_resource_agent_name(
                "service:provider:lvm2-pvscan252@252:2"
            ),
        )


class NameToDataclass(TestCase):
    def test_success(self):
        name = ResourceAgentName("ocf", "pacemaker", "Dummy")
        self.assertEqual(
            name_to_void_metadata(name),
            ResourceAgentMetadata(
                name,
                False,
                const.OCF_1_0,
                shortdesc=None,
                longdesc=None,
                parameters=[],
                actions=[],
            ),
        )
