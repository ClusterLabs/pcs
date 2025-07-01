from unittest import TestCase

from pcs.lib.commands.remote_node import get_resource_ids

from pcs_test.tools.command_env import get_env_tools


class GetResourceIdsFromRemoteNodeIdentfier(TestCase):
    NODE_NAME = "A"
    NODE_NAME_MULTIPLE = "B"

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(
            resources=f"""
                <resources>
                    <primitive class="ocf" id="{self.NODE_NAME}" provider="pacemaker" type="remote" />
                    <primitive class="ocf" id="{self.NODE_NAME_MULTIPLE}" provider="pacemaker" type="remote">
                        <instance_attributes id="node-name-instance_attributes">
                            <nvpair
                                id="node-name-instance_attributes-server"
                                name="server" value="foo"
                            />
                        </instance_attributes>
                    </primitive>
                    <primitive class="ocf" id="X" provider="pacemaker" type="remote">
                        <instance_attributes id="node-name-instance_attributes">
                            <nvpair
                                id="node-name-instance_attributes-server"
                                name="server" value="{self.NODE_NAME_MULTIPLE}"
                            />
                        </instance_attributes>
                    </primitive>
                </resources>
            """
        )

    def test_node_not_found(self):
        resource_ids = get_resource_ids(
            self.env_assist.get_env(), "nonexistent"
        )
        self.assertEqual(resource_ids, [])

    def test_node_found(self):
        resource_ids = get_resource_ids(
            self.env_assist.get_env(), self.NODE_NAME
        )
        self.assertEqual(resource_ids, [self.NODE_NAME])

    def test_multiple_nodes_found(self):
        resource_ids = get_resource_ids(
            self.env_assist.get_env(), self.NODE_NAME_MULTIPLE
        )
        self.assertEqual(resource_ids, [self.NODE_NAME_MULTIPLE, "X"])
