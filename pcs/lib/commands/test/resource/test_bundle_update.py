from __future__ import (
    absolute_import,
    division,
    print_function,
)

from functools import partial
from textwrap import dedent

from pcs.common import report_codes
from pcs.lib import reports
from pcs.lib.commands import resource
from pcs.lib.errors import (
    LibraryError,
    ReportItemSeverity as severities,
)
from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.misc import skip_unless_pacemaker_supports_bundle
from pcs.test.tools.pcs_unittest import TestCase


TIMEOUT=10

get_env_tools = partial(
    get_env_tools,
    base_cib_filename="cib-empty-2.8.xml"
)

def simple_bundle_update(env, wait=TIMEOUT):
    return resource.bundle_update(env, "B1", {"image": "new:image"}, wait=wait)


fixture_resources_minimal = """
    <resources>
        <bundle id="B1">
            <docker image="pcs:test" />
        </bundle>
    </resources>
"""

class Basics(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_nonexisting_id(self):
        self.config.runner.cib.load()
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(self.env_assist.get_env(), "B1"),
            [
                (
                    severities.ERROR,
                    report_codes.ID_NOT_FOUND,
                    {
                        "id": "B1",
                        "expected_types": ["bundle"],
                        "context_type": "resources",
                        "context_id": "",
                    },
                    None
                ),
            ],
            expected_in_processor=False
        )

    def test_not_bundle_id(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="B1" />
                </resources>
            """
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(self.env_assist.get_env(), "B1"),
            [
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
            ],
            expected_in_processor=False
        )

    def test_no_updates(self):
        (self.config
            .runner.cib.load(
                resources="""
                    <resources>
                        <bundle id="B1">
                            <docker image="pcs:test" />
                        </bundle>
                    </resources>
                """
            )
            .env.push_cib()
        )
        resource.bundle_update(self.env_assist.get_env(), "B1")


    def test_cib_upgrade(self):
        (self.config
            .runner.cib.load(
                filename="cib-empty.xml",
                name="load_cib_old_version"
            )
            .runner.cib.upgrade()
            .runner.cib.load(
                resources="""
                    <resources>
                        <bundle id="B1">
                            <docker image="pcs:test" />
                        </bundle>
                    </resources>
                """
            )
            .env.push_cib()
        )
        resource.bundle_update(self.env_assist.get_env(), "B1")
        self.env_assist.assert_reports([
            (
                severities.INFO,
                report_codes.CIB_UPGRADE_SUCCESSFUL,
                {
                },
                None
            ),
        ])

class ContainerDocker(TestCase):
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

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success(self):
        (self.config
            .runner.cib.load(
                resources="""
                    <resources>
                        <bundle id="B1">
                            <docker image="pcs:test" masters="3" replicas="6"/>
                        </bundle>
                    </resources>
                """
            )
            .env.push_cib(
                resources="""
                    <resources>
                        <bundle id="B1">
                            <docker image="pcs:test" options="test" replicas="3"
                            />
                        </bundle>
                    </resources>
                """
            )
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            container_options={
                "options": "test",
                "replicas": "3",
                "masters": "",
            }
        )

    def test_cannot_remove_required_options(self):
        self.config.runner.cib.load(resources=fixture_resources_minimal)
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                container_options={
                    "image": "",
                    "options": "test",
                },
                force_options=True
            ),
            [
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
            ]
        )

    def test_unknow_option(self):
        self.config.runner.cib.load(resources=fixture_resources_minimal)
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                container_options={
                    "extra": "option",
                }
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["extra", ],
                        "option_type": "container",
                        "allowed": self.allowed_options,
                    },
                    report_codes.FORCE_OPTIONS
                ),
            ]
        )

    def test_unknow_option_forced(self):
        (self.config
            .runner.cib.load(resources=fixture_resources_minimal)
            .env.push_cib(resources=self.fixture_cib_extra_option)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            container_options={
                "extra": "option",
            },
            force_options=True
        )

        self.env_assist.assert_reports([
            (
                severities.WARNING,
                report_codes.INVALID_OPTIONS,
                {
                    "option_names": ["extra", ],
                    "option_type": "container",
                    "allowed": self.allowed_options,
                },
                None
            ),
        ])

    def test_unknown_option_remove(self):
        (self.config
            .runner.cib.load(resources=self.fixture_cib_extra_option)
            .env.push_cib(resources=fixture_resources_minimal)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            container_options={
                "extra": "",
            },
            force_options=True
        )


class Network(TestCase):
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

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_add_network(self):
        (self.config
            .runner.cib.load(resources=fixture_resources_minimal)
            .env.push_cib(resources=self.fixture_cib_interface)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "host-interface": "eth0",
            }
        )

    def test_remove_network(self):
        (self.config
            .runner.cib.load(resources=self.fixture_cib_interface)
            .env.push_cib(resources=fixture_resources_minimal)
        )

        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "host-interface": "",
            }
        )

    def test_keep_network_when_port_map_set(self):
        (self.config
            .runner.cib.load(
                resources="""
                    <resources>
                        <bundle id="B1">
                            <docker image="pcs:test" />
                            <network host-interface="eth0">
                                <something />
                            </network>
                        </bundle>
                    </resources>
                """
            )
            .env.push_cib(
                resources="""
                    <resources>
                        <bundle id="B1">
                            <docker image="pcs:test" />
                            <network>
                                <something />
                            </network>
                        </bundle>
                    </resources>
                """
            )
        )

        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "host-interface": "",
            }
        )

    def test_success(self):
        (self.config
            .runner.cib.load(
                resources="""
                    <resources>
                        <bundle id="B1">
                            <docker image="pcs:test" />
                            <network host-interface="eth0" control-port="12345"
                            />
                        </bundle>
                    </resources>
                """
            )
            .env.push_cib(
                resources="""
                    <resources>
                        <bundle id="B1">
                            <docker image="pcs:test" />
                            <network host-interface="eth0" host-netmask="24" />
                        </bundle>
                    </resources>
                """
            )
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "control-port": "",
                "host-netmask": "24",
            }
        )

    def test_unknow_option(self):
        (self.config.runner.cib.load(resources=self.fixture_cib_interface))
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                network_options={
                    "extra": "option",
                }
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["extra", ],
                        "option_type": "network",
                        "allowed": self.allowed_options,
                    },
                    report_codes.FORCE_OPTIONS
                ),
            ]
        )

    def test_unknow_option_forced(self):
        (self.config
            .runner.cib.load(resources=self.fixture_cib_interface)
            .env.push_cib(resources=self.fixture_cib_extra_option)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "extra": "option",
            },
            force_options=True
        )
        self.env_assist.assert_reports(
            [
                (
                    severities.WARNING,
                    report_codes.INVALID_OPTIONS,
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
        (self.config
            .runner.cib.load(resources=self.fixture_cib_extra_option)
            .env.push_cib(resources=self.fixture_cib_interface)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "extra": "",
            }
        )

class PortMap(TestCase):
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

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_add_network(self):
        (self.config
            .runner.cib.load(resources=fixture_resources_minimal)
            .env.push_cib(resources=self.fixture_cib_port_80)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            port_map_add=[
                {
                    "port": "80",
                }
            ]
        )

    def test_remove_network(self):
        (self.config
            .runner.cib.load(resources=self.fixture_cib_port_80)
            .env.push_cib(resources=fixture_resources_minimal)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            port_map_remove=[
                "B1-port-map-80",
            ]
        )

    def test_keep_network_when_options_set(self):
        (self.config
            .runner.cib.load(
                resources="""
                    <resources>
                        <bundle id="B1">
                            <docker image="pcs:test" />
                            <network host-interface="eth0">
                                <port-mapping id="B1-port-map-80" port="80" />
                            </network>
                        </bundle>
                    </resources>
                """
            )
            .env.push_cib(
                resources="""
                    <resources>
                        <bundle id="B1">
                            <docker image="pcs:test" />
                            <network host-interface="eth0" />
                        </bundle>
                    </resources>
                """
            )
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            port_map_remove=[
                "B1-port-map-80",
            ]
        )

    def test_add(self):
        (self.config
            .runner.cib.load(resources=self.fixture_cib_port_80)
            .env.push_cib(resources=self.fixture_cib_port_80_8080)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            port_map_add=[
                {
                    "port": "8080",
                }
            ]
        )

    def test_remove(self):
        (self.config
            .runner.cib.load(resources=self.fixture_cib_port_80_8080)
            .env.push_cib(resources=self.fixture_cib_port_80)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            port_map_remove=[
                "B1-port-map-8080",
            ]
        )

    def test_remove_missing(self):
        self.config.runner.cib.load(resources=self.fixture_cib_port_80)

        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                port_map_remove=[
                    "B1-port-map-8080",
                ]
            ),
            [
                (
                    severities.ERROR,
                    report_codes.ID_NOT_FOUND,
                    {
                        "id": "B1-port-map-8080",
                        "expected_types": ["port-map"],
                        "context_type": "bundle",
                        "context_id": "B1",
                    },
                    None
                ),
            ]
        )


class StorageMap(TestCase):
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

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_add_storage(self):
        (self.config
            .runner.cib.load(resources=fixture_resources_minimal)
            .env.push_cib(resources=self.fixture_cib_storage_1)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            storage_map_add=[
                {
                    "source-dir": "/tmp/docker1a",
                    "target-dir": "/tmp/docker1b",
                }
            ]
        )

    def test_remove_storage(self):
        (self.config
            .runner.cib.load(resources=self.fixture_cib_storage_1)
            .env.push_cib(resources=fixture_resources_minimal)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            storage_map_remove=[
                "B1-storage-map",
            ]
        )

    def test_add(self):
        (self.config
            .runner.cib.load(resources=self.fixture_cib_storage_1)
            .env.push_cib(resources=self.fixture_cib_storage_1_2)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            storage_map_add=[
                {
                    "source-dir": "/tmp/docker2a",
                    "target-dir": "/tmp/docker2b",
                }
            ]
        )

    def test_remove(self):
        (self.config
            .runner.cib.load(resources=self.fixture_cib_storage_1_2)
            .env.push_cib(resources=self.fixture_cib_storage_1)
        )

        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            storage_map_remove=[
                "B1-storage-map-1",
            ]
        )

    def test_remove_missing(self):
        (self.config
            .runner.cib.load(resources=self.fixture_cib_storage_1)
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(), "B1",
                storage_map_remove=[
                    "B1-storage-map-1",
                ]
            ),
            [
                (
                    severities.ERROR,
                    report_codes.ID_NOT_FOUND,
                    {
                        "id": "B1-storage-map-1",
                        "expected_types": ["storage-map"],
                        "context_type": "bundle",
                        "context_id": "B1",
                    },
                    None
                )
            ]
        )

class Meta(TestCase):
    fixture_no_meta = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" masters="3" replicas="6"/>
            </bundle>
        </resources>
    """

    fixture_meta_stopped = """
        <resources>
            <bundle id="B1">
                <meta_attributes id="B1-meta_attributes">
                <nvpair id="B1-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
                </meta_attributes>
                <docker image="pcs:test" masters="3" replicas="6"/>
            </bundle>
        </resources>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_add_meta_element(self):
        (self.config
            .runner.cib.load(resources=self.fixture_no_meta)
            .env.push_cib(resources=self.fixture_meta_stopped)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            meta_attributes={
                "target-role": "Stopped",
            }
        )

    def test_remove_meta_element(self):
        (self.config
            .runner.cib.load(resources=self.fixture_meta_stopped)
            .env.push_cib(resources=self.fixture_no_meta)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            meta_attributes={
                "target-role": "",
            }
        )

    def test_change_meta(self):
        fixture_cib_pre = """
            <resources>
                <bundle id="B1">
                    <meta_attributes id="B1-meta_attributes">
                    <nvpair id="B1-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                    <nvpair id="B1-meta_attributes-priority"
                        name="priority" value="15" />
                    <nvpair id="B1-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                    </meta_attributes>
                    <docker image="pcs:test" masters="3" replicas="6"/>
                </bundle>
            </resources>
        """
        fixture_cib_post = """
            <resources>
                <bundle id="B1">
                    <meta_attributes id="B1-meta_attributes">
                    <nvpair id="B1-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                    <nvpair id="B1-meta_attributes-priority"
                        name="priority" value="10" />
                    <nvpair id="B1-meta_attributes-resource-stickiness"
                        name="resource-stickiness" value="100" />
                    </meta_attributes>
                    <docker image="pcs:test" masters="3" replicas="6"/>
                </bundle>
            </resources>
        """
        (self.config
            .runner.cib.load(resources=fixture_cib_pre)
            .env.push_cib(resources=fixture_cib_post)
        )
        resource.bundle_update(
            self.env_assist.get_env(), "B1",
            meta_attributes={
                "priority": "10",
                "resource-stickiness": "100",
                "is-managed": "",
            }
        )


class Wait(TestCase):
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


    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        (self.config
            .runner.pcmk.can_wait()
            .runner.cib.load(resources=self.fixture_cib_pre)
            .env.push_cib(
                resources=self.fixture_resources_bundle_simple,
                wait=TIMEOUT
            )
        )

    def test_wait_fail(self):
        wait_error_message = dedent(
            """\
            Pending actions:
                    Action 12: B1-node2-stop on node2
            Error performing operation: Timer expired
            """
        ).strip()
        self.config.env.push_cib(
            resources=self.fixture_resources_bundle_simple,
            wait=TIMEOUT,
            exception=LibraryError(
                reports.wait_for_idle_timed_out(wait_error_message)
            ),
            instead="env.push_cib"
        )

        self.env_assist.assert_raise_library_error(
            lambda: simple_bundle_update(self.env_assist.get_env()),
            [
                fixture.report_wait_for_idle_timed_out(wait_error_message)
            ],
            expected_in_processor=False
        )

    @skip_unless_pacemaker_supports_bundle
    def test_wait_ok_running(self):
        (self.config
            .runner.pcmk.load_state(resources=self.fixture_status_running)
        )
        simple_bundle_update(self.env_assist.get_env())
        self.env_assist.assert_reports([
            fixture.report_resource_running(
                "B1", {"Started": ["node1", "node2"]}
            ),
        ])

    @skip_unless_pacemaker_supports_bundle
    def test_wait_ok_not_running(self):
        (self.config
            .runner.pcmk.load_state(resources=self.fixture_status_not_running)
        )
        simple_bundle_update(self.env_assist.get_env())
        self.env_assist.assert_reports([
            fixture.report_resource_not_running("B1", severities.INFO),
        ])

class WithPrimitive(TestCase):
    fixture_resources_pre = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" />
                <primitive id="P"/>
                {network}
            </bundle>
        </resources>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_already_not_accessible(self):
        (self.config
            .runner.cib.load(
                resources=self.fixture_resources_pre.format(network="")
            )
            .env.push_cib(resources=self.fixture_resources_pre.format(
                network='<network host-interface="int"/>'
            ))
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "host-interface": "int",
            }
        )

    def test_add_ip_remove_port(self):
        (self.config
            .runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network='<network control-port="1234"/>'
                )
            )
            .env.push_cib(resources=self.fixture_resources_pre.format(
                network='<network ip-range-start="192.168.100.200"/>'
            ))
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "ip-range-start": "192.168.100.200",
                "control-port": "",
            }
        )

    def test_remove_ip_add_port(self):
        (self.config
            .runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network='<network ip-range-start="192.168.100.200"/>'
                )
            )
            .env.push_cib(resources=self.fixture_resources_pre.format(
                network='<network control-port="1234"/>'
            ))
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "ip-range-start": "",
                "control-port": "1234",
            }
        )

    def test_remove_ip_remove_port(self):
        (self.config
            .runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network="""
                        <network
                            ip-range-start="192.168.100.200"
                            control-port="1234"
                        />
                    """
                )
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                network_options={
                    "ip-range-start": "",
                    "control-port": "",
                }
            ),
            [
                fixture.error(
                    report_codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
                    bundle_id="B1",
                    inner_resource_id="P",
                    force_code=report_codes.FORCE_OPTIONS,
                )
            ]
        )

    def test_remove_ip_remove_port_force(self):
        (self.config
            .runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network="""
                        <network
                            ip-range-start="192.168.100.200"
                            control-port="1234"
                        />
                    """
                )
            )
            .env.push_cib(resources=self.fixture_resources_pre.format(
                network=''
            ))
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "ip-range-start": "",
                "control-port": "",
            },
            force_options=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
                    bundle_id="B1",
                    inner_resource_id="P",
                )
            ]
        )

    def test_remove_ip_left_port(self):
        (self.config
            .runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network="""
                        <network
                            ip-range-start="192.168.100.200"
                            control-port="1234"
                        />
                    """
                )
            )
            .env.push_cib(resources=self.fixture_resources_pre.format(
                network='<network control-port="1234"/>'
            ))
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "ip-range-start": "",
            }
        )

    def test_left_ip_remove_port(self):
        (self.config
            .runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network="""
                        <network
                            ip-range-start="192.168.100.200"
                            control-port="1234"
                        />
                    """
                )
            )
            .env.push_cib(resources=self.fixture_resources_pre.format(
                network='<network ip-range-start="192.168.100.200"/>'
            ))
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "control-port": "",
            }
        )

    def test_remove_ip(self):
        (self.config
            .runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network='<network ip-range-start="192.168.100.200"/>'
                )
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                network_options={
                    "ip-range-start": "",
                }
            ),
            [
                fixture.error(
                    report_codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
                    bundle_id="B1",
                    inner_resource_id="P",
                    force_code=report_codes.FORCE_OPTIONS,
                )
            ]
        )

    def test_remove_ip_force(self):
        (self.config
            .runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network='<network ip-range-start="192.168.100.200"/>'
                )
            )
            .env.push_cib(resources=self.fixture_resources_pre.format(
                network=''
            ))
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "ip-range-start": "",
            },
            force_options=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
                    bundle_id="B1",
                    inner_resource_id="P",
                )
            ]
        )

    def test_remove_port(self):
        (self.config
            .runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network='<network control-port="1234"/>'
                )
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                network_options={
                    "control-port": "",
                }
            ),
            [
                fixture.error(
                    report_codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
                    bundle_id="B1",
                    inner_resource_id="P",
                    force_code=report_codes.FORCE_OPTIONS,
                )
            ]
        )

    def test_remove_port_force(self):
        (self.config
            .runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network='<network control-port="1234"/>'
                )
            )
            .env.push_cib(resources=self.fixture_resources_pre.format(
                network=''
            ))
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "control-port": "",
            },
            force_options=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
                    bundle_id="B1",
                    inner_resource_id="P",
                )
            ]
        )
