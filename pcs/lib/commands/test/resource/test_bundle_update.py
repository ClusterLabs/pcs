from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from textwrap import dedent

from pcs.common import report_codes
from pcs.lib.commands import resource
from pcs.lib.commands.test.resource.common import ResourceWithoutStateTest
import pcs.lib.commands.test.resource.fixture as fixture
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.misc import skip_unless_pacemaker_supports_bundle

class CommonTest(ResourceWithoutStateTest):
    fixture_cib_minimal = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" />
            </bundle>
        </resources>
    """

    def setUp(self):
        super(CommonTest, self).setUp()
        self.cib_base_file = "cib-empty-2.8.xml"

    def fixture_cib_resources(self, cib):
        return fixture.cib_resources(cib, cib_base_file=self.cib_base_file)


class Basics(CommonTest):
    def test_nonexisting_id(self):
        fixture_cib_pre = "<resources />"
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(fixture_cib_pre)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_update(self.env, "B1"),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "B1",
                    "id_description": "bundle",
                    "context_type": "resources",
                    "context_id": "",
                },
                None
            ),
        )
        self.runner.assert_everything_launched()

    def test_not_bundle_id(self):
        fixture_cib_pre = """
            <resources>
                <primitive id="B1" />
            </resources>
        """
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(fixture_cib_pre)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_update(self.env, "B1"),
            (
                severities.ERROR,
                report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                {
                    "id": "B1",
                    "expected_types": ["bundle"],
                    "current_type": "primitive",
                },
                None
            ),
        )
        self.runner.assert_everything_launched()

    def test_no_updates(self):
        fixture_cib_pre = """
            <resources>
                <bundle id="B1">
                    <docker image="pcs:test" />
                </bundle>
            </resources>
        """
        self.assert_command_effect(
            fixture_cib_pre,
            lambda: resource.bundle_update(self.env, "B1"),
            fixture_cib_pre
        )

    def test_cib_upgrade(self):
        fixture_cib_pre = """
            <resources>
                <bundle id="B1">
                    <docker image="pcs:test" />
                </bundle>
            </resources>
        """
        self.runner.set_runs(
            fixture.calls_cib_load_and_upgrade(fixture_cib_pre)
            +
            fixture.calls_cib(
                fixture_cib_pre,
                fixture_cib_pre,
                cib_base_file=self.cib_base_file
            )
        )

        resource.bundle_update(self.env, "B1")

        self.env.report_processor.assert_reports([
            (
                severities.INFO,
                report_codes.CIB_UPGRADE_SUCCESSFUL,
                {
                },
                None
            ),
        ])
        self.runner.assert_everything_launched()


class ContainerDocker(CommonTest):
    allowed_options = [
        "image",
        "masters",
        "network",
        "options",
        "replicas",
        "replicas-per-host",
        "run-command",
    ]

    fixture_cib_extra_option = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" extra="option" />
            </bundle>
        </resources>
    """

    def test_success(self):
        fixture_cib_pre = """
            <resources>
                <bundle id="B1">
                    <docker image="pcs:test" masters="3" replicas="6"/>
                </bundle>
            </resources>
        """
        fixture_cib_post = """
            <resources>
                <bundle id="B1">
                    <docker image="pcs:test" options="test" replicas="3" />
                </bundle>
            </resources>
        """
        self.assert_command_effect(
            fixture_cib_pre,
            lambda: resource.bundle_update(
                self.env, "B1",
                container_options={
                    "options": "test",
                    "replicas": "3",
                    "masters": "",
                }
            ),
            fixture_cib_post
        )

    def test_cannot_remove_required_options(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(self.fixture_cib_minimal)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env, "B1",
                container_options={
                    "image": "",
                    "options": "test",
                },
                force_options=True
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "image",
                    "option_value": "",
                    "allowed_values": "image name",
                },
                None
            ),
        )
        self.runner.assert_everything_launched()

    def test_unknow_option(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(self.fixture_cib_minimal)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env, "B1",
                container_options={
                    "extra": "option",
                }
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option_names": ["extra", ],
                    "option_type": "container",
                    "allowed": self.allowed_options,
                },
                report_codes.FORCE_OPTIONS
            ),
        )
        self.runner.assert_everything_launched()

    def test_unknow_option_forced(self):
        self.assert_command_effect(
            self.fixture_cib_minimal,
            lambda: resource.bundle_update(
                self.env, "B1",
                container_options={
                    "extra": "option",
                },
                force_options=True
            ),
            self.fixture_cib_extra_option,
            [
                (
                    severities.WARNING,
                    report_codes.INVALID_OPTION,
                    {
                        "option_names": ["extra", ],
                        "option_type": "container",
                        "allowed": self.allowed_options,
                    },
                    None
                ),
            ]
        )

    def test_unknown_option_remove(self):
        self.assert_command_effect(
            self.fixture_cib_extra_option,
            lambda: resource.bundle_update(
                self.env, "B1",
                container_options={
                    "extra": "",
                }
            ),
            self.fixture_cib_minimal,
        )


class Network(CommonTest):
    allowed_options = [
        "control-port",
        "host-interface",
        "host-netmask",
        "ip-range-start",
    ]

    fixture_cib_interface = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" />
                <network host-interface="eth0" />
            </bundle>
        </resources>
    """

    fixture_cib_extra_option = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" />
                <network host-interface="eth0" extra="option" />
            </bundle>
        </resources>
    """

    def test_add_network(self):
        self.assert_command_effect(
            self.fixture_cib_minimal,
            lambda: resource.bundle_update(
                self.env, "B1",
                network_options={
                    "host-interface": "eth0",
                }
            ),
            self.fixture_cib_interface
        )

    def test_remove_network(self):
        self.assert_command_effect(
            self.fixture_cib_interface,
            lambda: resource.bundle_update(
                self.env, "B1",
                network_options={
                    "host-interface": "",
                }
            ),
            self.fixture_cib_minimal
        )

    def test_keep_network_when_port_map_set(self):
        fixture_cib_pre = """
            <resources>
                <bundle id="B1">
                    <docker image="pcs:test" />
                    <network host-interface="eth0">
                        <something />
                    </network>
                </bundle>
            </resources>
        """
        fixture_cib_post = """
            <resources>
                <bundle id="B1">
                    <docker image="pcs:test" />
                    <network>
                        <something />
                    </network>
                </bundle>
            </resources>
        """
        self.assert_command_effect(
            fixture_cib_pre,
            lambda: resource.bundle_update(
                self.env, "B1",
                network_options={
                    "host-interface": "",
                }
            ),
            fixture_cib_post
        )

    def test_success(self):
        fixture_cib_pre = """
            <resources>
                <bundle id="B1">
                    <docker image="pcs:test" />
                    <network host-interface="eth0" control-port="12345" />
                </bundle>
            </resources>
        """
        fixture_cib_post = """
            <resources>
                <bundle id="B1">
                    <docker image="pcs:test" />
                    <network host-interface="eth0" host-netmask="24" />
                </bundle>
            </resources>
        """
        self.assert_command_effect(
            fixture_cib_pre,
            lambda: resource.bundle_update(
                self.env, "B1",
                network_options={
                    "control-port": "",
                    "host-netmask": "24",
                }
            ),
            fixture_cib_post
        )

    def test_unknow_option(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(self.fixture_cib_interface)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env, "B1",
                network_options={
                    "extra": "option",
                }
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option_names": ["extra", ],
                    "option_type": "network",
                    "allowed": self.allowed_options,
                },
                report_codes.FORCE_OPTIONS
            ),
        )
        self.runner.assert_everything_launched()

    def test_unknow_option_forced(self):
        self.assert_command_effect(
            self.fixture_cib_interface,
            lambda: resource.bundle_update(
                self.env, "B1",
                network_options={
                    "extra": "option",
                },
                force_options=True
            ),
            self.fixture_cib_extra_option,
            [
                (
                    severities.WARNING,
                    report_codes.INVALID_OPTION,
                    {
                        "option_names": ["extra", ],
                        "option_type": "network",
                        "allowed": self.allowed_options,
                    },
                    None
                ),
            ]
        )

    def test_unknown_option_remove(self):
        self.assert_command_effect(
            self.fixture_cib_extra_option,
            lambda: resource.bundle_update(
                self.env, "B1",
                network_options={
                    "extra": "",
                }
            ),
            self.fixture_cib_interface,
        )


class PortMap(CommonTest):
    allowed_options = [
        "id",
        "port",
        "internal-port",
        "range",
    ]

    fixture_cib_port_80 = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" />
                <network>
                    <port-mapping id="B1-port-map-80" port="80" />
                </network>
            </bundle>
        </resources>
    """

    fixture_cib_port_80_8080 = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" />
                <network>
                    <port-mapping id="B1-port-map-80" port="80" />
                    <port-mapping id="B1-port-map-8080" port="8080" />
                </network>
            </bundle>
        </resources>
    """

    def test_add_network(self):
        self.assert_command_effect(
            self.fixture_cib_minimal,
            lambda: resource.bundle_update(
                self.env, "B1",
                port_map_add=[
                    {
                        "port": "80",
                    }
                ]
            ),
            self.fixture_cib_port_80
        )

    def test_remove_network(self):
        self.assert_command_effect(
            self.fixture_cib_port_80,
            lambda: resource.bundle_update(
                self.env, "B1",
                port_map_remove=[
                    "B1-port-map-80",
                ]
            ),
            self.fixture_cib_minimal
        )

    def test_keep_network_when_options_set(self):
        fixture_cib_pre = """
            <resources>
                <bundle id="B1">
                    <docker image="pcs:test" />
                    <network host-interface="eth0">
                        <port-mapping id="B1-port-map-80" port="80" />
                    </network>
                </bundle>
            </resources>
        """
        fixture_cib_post = """
            <resources>
                <bundle id="B1">
                    <docker image="pcs:test" />
                    <network host-interface="eth0" />
                </bundle>
            </resources>
        """
        self.assert_command_effect(
            fixture_cib_pre,
            lambda: resource.bundle_update(
                self.env, "B1",
                port_map_remove=[
                    "B1-port-map-80",
                ]
            ),
            fixture_cib_post
        )

    def test_add(self):
        self.assert_command_effect(
            self.fixture_cib_port_80,
            lambda: resource.bundle_update(
                self.env, "B1",
                port_map_add=[
                    {
                        "port": "8080",
                    }
                ]
            ),
            self.fixture_cib_port_80_8080
        )

    def test_remove(self):
        self.assert_command_effect(
            self.fixture_cib_port_80_8080,
            lambda: resource.bundle_update(
                self.env, "B1",
                port_map_remove=[
                    "B1-port-map-8080",
                ]
            ),
            self.fixture_cib_port_80
        )

    def test_remove_missing(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(self.fixture_cib_port_80)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env, "B1",
                port_map_remove=[
                    "B1-port-map-8080",
                ]
            ),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "B1-port-map-8080",
                    "id_description": "port-map",
                    "context_type": "bundle",
                    "context_id": "B1",
                },
                None
            ),
        )
        self.runner.assert_everything_launched()


class StorageMap(CommonTest):
    allowed_options = [
        "id",
        "options",
        "source-dir",
        "source-dir-root",
        "target-dir",
    ]

    fixture_cib_storage_1 = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" />
                <storage>
                    <storage-mapping
                        id="B1-storage-map"
                        source-dir="/tmp/docker1a"
                        target-dir="/tmp/docker1b"
                    />
                </storage>
            </bundle>
        </resources>
    """

    fixture_cib_storage_1_2 = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" />
                <storage>
                    <storage-mapping
                        id="B1-storage-map"
                        source-dir="/tmp/docker1a"
                        target-dir="/tmp/docker1b"
                    />
                    <storage-mapping
                        id="B1-storage-map-1"
                        source-dir="/tmp/docker2a"
                        target-dir="/tmp/docker2b"
                    />
                </storage>
            </bundle>
        </resources>
    """

    def test_add_storage(self):
        self.assert_command_effect(
            self.fixture_cib_minimal,
            lambda: resource.bundle_update(
                self.env, "B1",
                storage_map_add=[
                    {
                        "source-dir": "/tmp/docker1a",
                        "target-dir": "/tmp/docker1b",
                    }
                ]
            ),
            self.fixture_cib_storage_1
        )

    def test_remove_storage(self):
        self.assert_command_effect(
            self.fixture_cib_storage_1,
            lambda: resource.bundle_update(
                self.env, "B1",
                storage_map_remove=[
                    "B1-storage-map",
                ]
            ),
            self.fixture_cib_minimal
        )

    def test_add(self):
        self.assert_command_effect(
            self.fixture_cib_storage_1,
            lambda: resource.bundle_update(
                self.env, "B1",
                storage_map_add=[
                    {
                        "source-dir": "/tmp/docker2a",
                        "target-dir": "/tmp/docker2b",
                    }
                ]
            ),
            self.fixture_cib_storage_1_2
        )

    def test_remove(self):
        self.assert_command_effect(
            self.fixture_cib_storage_1_2,
            lambda: resource.bundle_update(
                self.env, "B1",
                storage_map_remove=[
                    "B1-storage-map-1",
                ]
            ),
            self.fixture_cib_storage_1
        )

    def test_remove_missing(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(self.fixture_cib_storage_1)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env, "B1",
                storage_map_remove=[
                    "B1-storage-map-1",
                ]
            ),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "B1-storage-map-1",
                    "id_description": "storage-map",
                    "context_type": "bundle",
                    "context_id": "B1",
                },
                None
            ),
        )
        self.runner.assert_everything_launched()


class Wait(CommonTest):
    fixture_status_running = """
        <resources>
        <bundle id="B1" managed="true" image="new:image">
                <replica id="0">
                    <resource id="B1-docker-0" managed="true" role="Started">
                        <node name="node1" id="1" cached="false"/>
                    </resource>
                </replica>
                <replica id="1">
                    <resource id="B1-docker-1" managed="true" role="Started">
                        <node name="node2" id="2" cached="false"/>
                    </resource>
                </replica>
            </bundle>
        </resources>
    """

    fixture_status_not_running = """
        <resources>
            <bundle id="B1" managed="true" image="new:image">
                <replica id="0">
                    <resource id="B1-docker-0" managed="true" role="Stopped" />
                </replica>
                <replica id="1">
                    <resource id="B1-docker-1" managed="true" role="Stopped" />
                </replica>
            </bundle>
        </resources>
    """

    fixture_cib_pre = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" />
            </bundle>
        </resources>
    """

    fixture_resources_bundle_simple = """
        <resources>
            <bundle id="B1">
                <docker image="new:image" />
            </bundle>
        </resources>
    """

    timeout = 10

    def fixture_calls_initial(self):
        return (
            fixture.call_wait_supported() +
            fixture.calls_cib(
                self.fixture_cib_pre,
                self.fixture_resources_bundle_simple,
                cib_base_file=self.cib_base_file,
            )
        )

    def simple_bundle_update(self, wait=False):
        return resource.bundle_update(
            self.env, "B1", {"image": "new:image"}, wait=wait,
        )

    def test_wait_fail(self):
        fixture_wait_timeout_error = dedent(
            """\
            Pending actions:
                    Action 12: B1-node2-stop on node2
            Error performing operation: Timer expired
            """
        )
        self.runner.set_runs(
            self.fixture_calls_initial() +
            fixture.call_wait(self.timeout, 62, fixture_wait_timeout_error)
        )
        assert_raise_library_error(
            lambda: self.simple_bundle_update(self.timeout),
            fixture.report_wait_for_idle_timed_out(
                fixture_wait_timeout_error
            ),
        )
        self.runner.assert_everything_launched()

    @skip_unless_pacemaker_supports_bundle
    def test_wait_ok_run_ok(self):
        self.runner.set_runs(
            self.fixture_calls_initial() +
            fixture.call_wait(self.timeout) +
            fixture.call_status(fixture.state_complete(
                self.fixture_status_running
            ))
        )
        self.simple_bundle_update(self.timeout)
        self.env.report_processor.assert_reports([
            fixture.report_resource_running(
                "B1", {"Started": ["node1", "node2"]}
            ),
        ])
        self.runner.assert_everything_launched()

    @skip_unless_pacemaker_supports_bundle
    def test_wait_ok_run_fail(self):
        self.runner.set_runs(
            self.fixture_calls_initial() +
            fixture.call_wait(self.timeout) +
            fixture.call_status(fixture.state_complete(
                self.fixture_status_not_running
            ))
        )
        assert_raise_library_error(
            lambda: self.simple_bundle_update(self.timeout),
            fixture.report_resource_not_running("B1", severities.ERROR),
        )
        self.runner.assert_everything_launched()
