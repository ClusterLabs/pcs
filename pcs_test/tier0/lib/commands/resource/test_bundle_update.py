# pylint: disable=too-many-lines
from functools import partial
from textwrap import dedent
from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common import reports
from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.commands import resource
from pcs.lib.errors import LibraryError

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import ParametrizedTestMetaClass
from pcs_test.tools.misc import get_test_resource as rc

TIMEOUT = 10

get_env_tools = partial(get_env_tools, base_cib_filename="cib-empty.xml")


def simple_bundle_update(env, wait=TIMEOUT):
    return resource.bundle_update(
        env, "B1", container_options={"image": "new:image"}, wait=wait
    )


def fixture_resources_minimal(container_type="docker"):
    return """
        <resources>
            <bundle id="B1">
                <{container_type} image="pcs:test" />
            </bundle>
        </resources>
    """.format(
        container_type=container_type
    )


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
                    None,
                ),
            ],
            expected_in_processor=False,
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
                    None,
                ),
            ],
            expected_in_processor=False,
        )

    def test_no_updates(self):
        (
            self.config.runner.cib.load(
                resources="""
                    <resources>
                        <bundle id="B1">
                            <docker image="pcs:test" />
                        </bundle>
                    </resources>
                """
            ).env.push_cib()
        )
        resource.bundle_update(self.env_assist.get_env(), "B1")


class ContainerParametrized(TestCase):
    allowed_options = [
        "image",
        "network",
        "options",
        "promoted-max",
        "replicas",
        "replicas-per-host",
        "run-command",
    ]
    container_type = None

    @property
    def fixture_cib_extra_option(self):
        return """
            <resources>
                <bundle id="B1">
                    <{container_type} image="pcs:test" extra="option" />
                </bundle>
            </resources>
        """.format(
            container_type=self.container_type
        )

    @property
    def fixture_cib_masters(self):
        return """
            <resources>
                <bundle id="B1">
                    <{container_type} image="pcs:test" masters="2" />
                </bundle>
            </resources>
        """.format(
            container_type=self.container_type
        )

    @property
    def fixture_cib_promoted_max(self):
        return """
            <resources>
                <bundle id="B1">
                    <{container_type} image="pcs:test" promoted-max="3" />
                </bundle>
            </resources>
        """.format(
            container_type=self.container_type
        )

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def _test_success(self):
        (
            self.config.runner.cib.load(
                resources="""
                    <resources>
                        <bundle id="B1">
                            <{container_type} image="pcs:test" promoted-max="3"
                                replicas="6"
                            />
                        </bundle>
                    </resources>
                """.format(
                    container_type=self.container_type
                )
            ).env.push_cib(
                resources="""
                    <resources>
                        <bundle id="B1">
                            <{container_type} image="pcs:test" options="test" replicas="3"
                            />
                        </bundle>
                    </resources>
                """.format(
                    container_type=self.container_type
                )
            )
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            container_options={
                "options": "test",
                "replicas": "3",
                "promoted-max": "",
            },
        )

    def _test_cannot_remove_required_options(self):
        self.config.runner.cib.load(
            resources=fixture_resources_minimal(self.container_type)
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                container_options={
                    "image": "",
                    "options": "test",
                },
                force_options=True,
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="image",
                    option_value="",
                    allowed_values="image name",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
            ]
        )

    def _test_unknow_option(self):
        self.config.runner.cib.load(
            resources=fixture_resources_minimal(self.container_type)
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                container_options={
                    "extra": "option",
                },
            )
        )
        self.env_assist.assert_reports(
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": [
                            "extra",
                        ],
                        "option_type": "container",
                        "allowed": self.allowed_options,
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE,
                ),
            ]
        )

    def _test_unknow_option_forced(self):
        (
            self.config.runner.cib.load(
                resources=fixture_resources_minimal(self.container_type)
            ).env.push_cib(resources=self.fixture_cib_extra_option)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            container_options={
                "extra": "option",
            },
            force_options=True,
        )

        self.env_assist.assert_reports(
            [
                (
                    severities.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": [
                            "extra",
                        ],
                        "option_type": "container",
                        "allowed": self.allowed_options,
                        "allowed_patterns": [],
                    },
                    None,
                ),
            ]
        )

    def _test_unknown_option_remove(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_cib_extra_option
            ).env.push_cib(
                resources=fixture_resources_minimal(self.container_type)
            )
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            container_options={
                "extra": "",
            },
            force_options=True,
        )

    def _test_options_error(self):
        self.config.runner.cib.load(
            resources=fixture_resources_minimal(self.container_type)
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                container_options={
                    "promoted-max": "-2",
                    "replicas": "0",
                    "replicas-per-host": "0",
                },
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="promoted-max",
                    option_value="-2",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="replicas",
                    option_value="0",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="replicas-per-host",
                    option_value="0",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def _test_legacy_options_no_longer_allowed(self):
        self.config.runner.cib.load(
            resources=fixture_resources_minimal(self.container_type)
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                container_options={
                    "masters": "2",
                },
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    force_code=report_codes.FORCE,
                    option_names=["masters"],
                    option_type="container",
                    allowed=self.allowed_options,
                    allowed_patterns=[],
                ),
            ]
        )

    def _test_legacy_options_can_be_removed(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_cib_masters
            ).env.push_cib(
                resources=fixture_resources_minimal(self.container_type)
            )
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            container_options={
                "masters": "",
            },
        )

    def _test_delete_masters_and_promoted_max(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_cib_masters
            ).env.push_cib(
                resources=fixture_resources_minimal(self.container_type)
            )
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            container_options={
                "masters": "",
                "promoted-max": "",
            },
        )

    def _test_promoted_max_set_after_masters(self):
        (self.config.runner.cib.load(resources=self.fixture_cib_masters))
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                container_options={
                    "promoted-max": "3",
                },
            )
        )
        self.env_assist.assert_reports(
            [
                (
                    severities.ERROR,
                    report_codes.PREREQUISITE_OPTION_MUST_NOT_BE_SET,
                    {
                        "option_name": "promoted-max",
                        "option_type": "container",
                        "prerequisite_name": "masters",
                        "prerequisite_type": "container",
                    },
                    None,
                ),
            ]
        )

    def _test_promoted_max_set_after_masters_with_remove(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_cib_masters
            ).env.push_cib(resources=self.fixture_cib_promoted_max)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            container_options={
                "masters": "",
                "promoted-max": "3",
            },
        )


class ContainerDocker(
    ContainerParametrized, metaclass=ParametrizedTestMetaClass
):
    container_type = "docker"


class ContainerPodman(
    ContainerParametrized, metaclass=ParametrizedTestMetaClass
):
    container_type = "podman"


class ContainerUnknown(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <bundle id="B1">
                        <meta_attributes id="B1-meta_attributes">
                            <nvpair id="B1-meta_attributes-target-role"
                                name="target-role" value="Stopped" />
                        </meta_attributes>
                        <unknown_container_type image="pcs:test" />
                        <network host-interface="eth0">
                            <port-mapping id="B1-port-map-80" port="80" />
                        </network>
                        <storage>
                            <storage-mapping
                                id="B1-storage-map"
                                source-dir="/tmp/cont1a"
                                target-dir="/tmp/cont1b"
                            />
                        </storage>
                    </bundle>
                </resources>
            """
        )

    def test_no_container_options_minimal(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="B1">
                        <meta_attributes id="B1-meta_attributes">
                            <nvpair id="B1-meta_attributes-target-role"
                                name="target-role" value="Stopped" />
                            <nvpair id="B1-meta_attributes-attr"
                                name="attr" value="val" />
                        </meta_attributes>
                        <unknown_container_type image="pcs:test" />
                        <network host-interface="eth0">
                            <port-mapping id="B1-port-map-80" port="80" />
                        </network>
                        <storage>
                            <storage-mapping
                                id="B1-storage-map"
                                source-dir="/tmp/cont1a"
                                target-dir="/tmp/cont1b"
                            />
                        </storage>
                    </bundle>
                </resources>
            """
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            meta_attributes={
                "attr": "val",
            },
        )

    def test_no_container_options(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="B1">
                        <meta_attributes id="B1-meta_attributes">
                            <nvpair id="B1-meta_attributes-target-role"
                                name="target-role" value="Stopped" />
                            <nvpair id="B1-meta_attributes-attr"
                                name="attr" value="val" />
                        </meta_attributes>
                        <unknown_container_type image="pcs:test" />
                        <network host-interface="eth0" host-netmask="24" />
                        <storage>
                            <storage-mapping
                                id="B1-storage-map"
                                source-dir="/tmp/cont1a"
                                target-dir="/tmp/cont1b"
                            />
                            <storage-mapping
                                id="B1-storage-map-1"
                                source-dir="/tmp/cont2a"
                                target-dir="/tmp/cont2b"
                            />
                        </storage>
                    </bundle>
                </resources>
            """
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            storage_map_add=[
                {
                    "source-dir": "/tmp/cont2a",
                    "target-dir": "/tmp/cont2b",
                }
            ],
            port_map_remove=[
                "B1-port-map-80",
            ],
            meta_attributes={
                "attr": "val",
            },
            network_options={
                "host-netmask": "24",
            },
        )

    def test_with_container_options(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                container_options={
                    "promoted-max": "1",
                },
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.RESOURCE_BUNDLE_UNSUPPORTED_CONTAINER_TYPE,
                    bundle_id="B1",
                    supported_container_types=sorted(["docker", "podman"]),
                    updating_options=True,
                )
            ]
        )


class Network(TestCase):
    allowed_options = [
        "control-port",
        "host-interface",
        "host-netmask",
        "ip-range-start",
    ]

    fixture_cib_network_empty = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" />
                <network />
            </bundle>
        </resources>
    """

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
        (
            self.config.runner.cib.load(
                resources=fixture_resources_minimal()
            ).env.push_cib(resources=self.fixture_cib_interface)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "host-interface": "eth0",
            },
        )

    def test_remove_network_keep_empty(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_cib_interface
            ).env.push_cib(resources=self.fixture_cib_network_empty)
        )

        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "host-interface": "",
            },
        )

    def test_keep_network_when_port_map_set(self):
        (
            self.config.runner.cib.load(
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
            ).env.push_cib(
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
            },
        )

    def test_success(self):
        (
            self.config.runner.cib.load(
                resources="""
                    <resources>
                        <bundle id="B1">
                            <docker image="pcs:test" />
                            <network host-interface="eth0" control-port="12345"
                            />
                        </bundle>
                    </resources>
                """
            ).env.push_cib(
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
            },
        )

    def test_unknow_option(self):
        (self.config.runner.cib.load(resources=self.fixture_cib_interface))
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                network_options={
                    "extra": "option",
                },
            )
        )
        self.env_assist.assert_reports(
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": [
                            "extra",
                        ],
                        "option_type": "network",
                        "allowed": self.allowed_options,
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE,
                ),
            ]
        )

    def test_unknow_option_forced(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_cib_interface
            ).env.push_cib(resources=self.fixture_cib_extra_option)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "extra": "option",
            },
            force_options=True,
        )
        self.env_assist.assert_reports(
            [
                (
                    severities.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": [
                            "extra",
                        ],
                        "option_type": "network",
                        "allowed": self.allowed_options,
                        "allowed_patterns": [],
                    },
                    None,
                ),
            ]
        )

    def test_unknown_option_remove(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_cib_extra_option
            ).env.push_cib(resources=self.fixture_cib_interface)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "extra": "",
            },
        )


class PortMap(TestCase):
    allowed_options = [
        "id",
        "port",
        "internal-port",
        "range",
    ]

    fixture_cib_network_empty = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" />
                <network />
            </bundle>
        </resources>
    """

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
        (
            self.config.runner.cib.load(
                resources=fixture_resources_minimal()
            ).env.push_cib(resources=self.fixture_cib_port_80)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            port_map_add=[
                {
                    "port": "80",
                }
            ],
        )

    def test_remove_network_keep_empty(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_cib_port_80
            ).env.push_cib(resources=self.fixture_cib_network_empty)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            port_map_remove=[
                "B1-port-map-80",
            ],
        )

    def test_keep_network_when_options_set(self):
        (
            self.config.runner.cib.load(
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
            ).env.push_cib(
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
            ],
        )

    def test_add(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_cib_port_80
            ).env.push_cib(resources=self.fixture_cib_port_80_8080)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            port_map_add=[
                {
                    "port": "8080",
                }
            ],
        )

    def test_remove(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_cib_port_80_8080
            ).env.push_cib(resources=self.fixture_cib_port_80)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            port_map_remove=[
                "B1-port-map-8080",
            ],
        )

    def test_remove_missing(self):
        self.config.runner.cib.load(resources=self.fixture_cib_port_80)

        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                port_map_remove=[
                    "B1-port-map-8080",
                ],
            )
        )
        self.env_assist.assert_reports(
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
                    None,
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

    fixture_cib_storage_empty = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" />
                <storage />
            </bundle>
        </resources>
    """

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
        (
            self.config.runner.cib.load(
                resources=fixture_resources_minimal()
            ).env.push_cib(resources=self.fixture_cib_storage_1)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            storage_map_add=[
                {
                    "source-dir": "/tmp/docker1a",
                    "target-dir": "/tmp/docker1b",
                }
            ],
        )

    def test_remove_storage_keep_empty(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_cib_storage_1
            ).env.push_cib(resources=self.fixture_cib_storage_empty)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            storage_map_remove=[
                "B1-storage-map",
            ],
        )

    def test_add(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_cib_storage_1
            ).env.push_cib(resources=self.fixture_cib_storage_1_2)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            storage_map_add=[
                {
                    "source-dir": "/tmp/docker2a",
                    "target-dir": "/tmp/docker2b",
                }
            ],
        )

    def test_remove(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_cib_storage_1_2
            ).env.push_cib(resources=self.fixture_cib_storage_1)
        )

        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            storage_map_remove=[
                "B1-storage-map-1",
            ],
        )

    def test_remove_missing(self):
        (self.config.runner.cib.load(resources=self.fixture_cib_storage_1))
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_update(
                self.env_assist.get_env(),
                "B1",
                storage_map_remove=[
                    "B1-storage-map-1",
                ],
            )
        )
        self.env_assist.assert_reports(
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
                    None,
                )
            ]
        )


class Meta(TestCase):
    fixture_no_meta = """
        <resources>
            <bundle id="B1">
                <docker image="pcs:test" promoted-max="3" replicas="6"/>
            </bundle>
        </resources>
    """

    fixture_empty_meta = """
        <resources>
            <bundle id="B1">
                <meta_attributes id="B1-meta_attributes" />
                <docker image="pcs:test" promoted-max="3" replicas="6"/>
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
                <docker image="pcs:test" promoted-max="3" replicas="6"/>
            </bundle>
        </resources>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_add_meta_element(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_no_meta
            ).env.push_cib(resources=self.fixture_meta_stopped)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            meta_attributes={
                "target-role": "Stopped",
            },
        )

    def test_keep_meta_element(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_meta_stopped
            ).env.push_cib(resources=self.fixture_empty_meta)
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            meta_attributes={
                "target-role": "",
            },
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
                    <docker image="pcs:test" promoted-max="3" replicas="6"/>
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
                    <docker image="pcs:test" promoted-max="3" replicas="6"/>
                </bundle>
            </resources>
        """
        (
            self.config.runner.cib.load(resources=fixture_cib_pre).env.push_cib(
                resources=fixture_cib_post
            )
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            meta_attributes={
                "priority": "10",
                "resource-stickiness": "100",
                "is-managed": "",
            },
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
        (
            self.config.runner.cib.load(
                resources=self.fixture_cib_pre
            ).env.push_cib(
                resources=self.fixture_resources_bundle_simple, wait=TIMEOUT
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
                reports.item.ReportItem.error(
                    reports.messages.WaitForIdleTimedOut(wait_error_message)
                )
            ),
            instead="env.push_cib",
        )

        self.env_assist.assert_raise_library_error(
            lambda: simple_bundle_update(self.env_assist.get_env()),
            [fixture.report_wait_for_idle_timed_out(wait_error_message)],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            [fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED)]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_running(self):
        (
            self.config.runner.pcmk.load_state(
                resources=self.fixture_status_running
            )
        )
        simple_bundle_update(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.report_resource_running(
                    "B1", {"Started": ["node1", "node2"]}
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_not_running(self):
        (
            self.config.runner.pcmk.load_state(
                resources=self.fixture_status_not_running
            )
        )
        simple_bundle_update(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.report_resource_not_running("B1", severities.INFO),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )


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
        (
            self.config.runner.cib.load(
                resources=self.fixture_resources_pre.format(network="")
            ).env.push_cib(
                resources=self.fixture_resources_pre.format(
                    network='<network host-interface="int"/>'
                )
            )
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "host-interface": "int",
            },
        )

    def test_add_ip_remove_port(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network='<network control-port="1234"/>'
                )
            ).env.push_cib(
                resources=self.fixture_resources_pre.format(
                    network='<network ip-range-start="192.168.100.200"/>'
                )
            )
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "ip-range-start": "192.168.100.200",
                "control-port": "",
            },
        )

    def test_remove_ip_add_port(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network='<network ip-range-start="192.168.100.200"/>'
                )
            ).env.push_cib(
                resources=self.fixture_resources_pre.format(
                    network='<network control-port="1234"/>'
                )
            )
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "ip-range-start": "",
                "control-port": "1234",
            },
        )

    def test_remove_ip_remove_port(self):
        (
            self.config.runner.cib.load(
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
                },
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
                    bundle_id="B1",
                    inner_resource_id="P",
                    force_code=report_codes.FORCE,
                )
            ]
        )

    def test_remove_ip_remove_port_force(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network="""
                        <network
                            ip-range-start="192.168.100.200"
                            control-port="1234"
                        />
                    """
                )
            ).env.push_cib(
                resources=self.fixture_resources_pre.format(
                    network="<network />"
                )
            )
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
        (
            self.config.runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network="""
                        <network
                            ip-range-start="192.168.100.200"
                            control-port="1234"
                        />
                    """
                )
            ).env.push_cib(
                resources=self.fixture_resources_pre.format(
                    network='<network control-port="1234"/>'
                )
            )
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "ip-range-start": "",
            },
        )

    def test_left_ip_remove_port(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network="""
                        <network
                            ip-range-start="192.168.100.200"
                            control-port="1234"
                        />
                    """
                )
            ).env.push_cib(
                resources=self.fixture_resources_pre.format(
                    network='<network ip-range-start="192.168.100.200"/>'
                )
            )
        )
        resource.bundle_update(
            self.env_assist.get_env(),
            "B1",
            network_options={
                "control-port": "",
            },
        )

    def test_remove_ip(self):
        (
            self.config.runner.cib.load(
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
                },
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
                    bundle_id="B1",
                    inner_resource_id="P",
                    force_code=report_codes.FORCE,
                )
            ]
        )

    def test_remove_ip_force(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network='<network ip-range-start="192.168.100.200"/>'
                )
            ).env.push_cib(
                resources=self.fixture_resources_pre.format(
                    network="<network />"
                )
            )
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
        (
            self.config.runner.cib.load(
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
                },
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
                    bundle_id="B1",
                    inner_resource_id="P",
                    force_code=report_codes.FORCE,
                )
            ]
        )

    def test_remove_port_force(self):
        (
            self.config.runner.cib.load(
                resources=self.fixture_resources_pre.format(
                    network='<network control-port="1234"/>'
                )
            ).env.push_cib(
                resources=self.fixture_resources_pre.format(
                    network="<network />"
                )
            )
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
