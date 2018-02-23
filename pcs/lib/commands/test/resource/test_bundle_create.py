from functools import partial
from textwrap import dedent
from unittest import TestCase

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


TIMEOUT=10

get_env_tools = partial(
    get_env_tools,
    base_cib_filename="cib-empty-2.8.xml"
)


def simple_bundle_create(env, wait=TIMEOUT, disabled=False):
    return resource.bundle_create(
        env, "B1", "docker",
        container_options={"image": "pcs:test"},
        ensure_disabled=disabled,
        wait=wait,
    )

fixture_cib_pre = "<resources />"
fixture_resources_bundle_simple = """
    <resources>
        <bundle id="B1">
            <docker image="pcs:test" />
        </bundle>
    </resources>
"""

class MinimalCreate(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        (self.config
            .runner.cib.load()
            .env.push_cib(resources=fixture_resources_bundle_simple)
        )

    def test_success(self):
        simple_bundle_create(self.env_assist.get_env(), wait=False)

    def test_errors(self):
        self.config.remove("env.push_cib")
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env_assist.get_env(), "B#1", "nonsense"
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_ID,
                    {
                        "invalid_character": "#",
                        "id": "B#1",
                        "id_description": "bundle name",
                        "is_first_char": False,
                    },
                    None
                ),
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "container type",
                        "option_value": "nonsense",
                        "allowed_values": ("docker", ),
                    },
                    None
                ),
            ]
        )

    def test_cib_upgrade(self):
        (self.config
            .runner.cib.load(
                name="load_cib_old_version",
                filename="cib-empty.xml",
                before="runner.cib.load"
            )
            .runner.cib.upgrade(before="runner.cib.load")
        )

        simple_bundle_create(self.env_assist.get_env(), wait=False)

        self.env_assist.assert_reports([
            (
                severities.INFO,
                report_codes.CIB_UPGRADE_SUCCESSFUL,
                {
                },
                None
            ),
        ])


class CreateDocker(TestCase):
    allowed_options = [
        "image",
        "masters",
        "network",
        "options",
        "replicas",
        "replicas-per-host",
        "run-command",
    ]

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(resources=fixture_cib_pre)

    def test_minimal(self):
        self.config.env.push_cib(resources=fixture_resources_bundle_simple)
        simple_bundle_create(self.env_assist.get_env(), wait=False)

    def test_all_options(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="B1">
                        <docker
                            image="pcs:test"
                            masters="0"
                            network="extra network settings"
                            options="extra options"
                            replicas="4"
                            replicas-per-host="2"
                            run-command="/bin/true"
                        />
                    </bundle>
                </resources>
            """
        )
        resource.bundle_create(
            self.env_assist.get_env(), "B1", "docker",
            container_options={
                "image": "pcs:test",
                "masters": "0",
                "network": "extra network settings",
                "options": "extra options",
                "run-command": "/bin/true",
                "replicas": "4",
                "replicas-per-host": "2",
            }
        )

    def test_options_errors(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env_assist.get_env(), "B1", "docker",
                container_options={
                    "replicas-per-host": "0",
                    "replicas": "0",
                    "masters": "-1",
                },
                force_options=True
            ),
            [
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    {
                        "option_type": "container",
                        "option_names": ["image", ],
                    },
                    None
                ),
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "masters",
                        "option_value": "-1",
                        "allowed_values": "a non-negative integer",
                    },
                    None
                ),
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "replicas",
                        "option_value": "0",
                        "allowed_values": "a positive integer",
                    },
                    None
                ),
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "replicas-per-host",
                        "option_value": "0",
                        "allowed_values": "a positive integer",
                    },
                    None
                ),
            ]
        )

    def test_empty_image(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env_assist.get_env(), "B1", "docker",
                container_options={
                    "image": "",
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
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env_assist.get_env(), "B1", "docker",
                container_options={
                    "image": "pcs:test",
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
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE_OPTIONS
                ),
            ]
        )

    def test_unknow_option_forced(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" extra="option" />
                    </bundle>
                </resources>
            """
        )
        resource.bundle_create(
            self.env_assist.get_env(), "B1", "docker",
            container_options={
                "image": "pcs:test",
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
                    "allowed_patterns": [],
                },
                None
            ),
        ])


class CreateWithNetwork(TestCase):
    allowed_options = [
        "control-port",
        "host-interface",
        "host-netmask",
        "ip-range-start",
    ]

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(resources=fixture_cib_pre)


    def test_no_options(self):
        self.config.env.push_cib(resources=fixture_resources_bundle_simple)
        resource.bundle_create(
            self.env_assist.get_env(), "B1", "docker",
            {"image": "pcs:test", },
            network_options={}
        )

    def test_all_options(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" />
                        <network
                            control-port="12345"
                            host-interface="eth0"
                            host-netmask="24"
                            ip-range-start="192.168.100.200"
                        />
                    </bundle>
                </resources>
            """
        )
        resource.bundle_create(
            self.env_assist.get_env(), "B1", "docker",
            {"image": "pcs:test", },
            network_options={
                "control-port": "12345",
                "host-interface": "eth0",
                "host-netmask": "24",
                "ip-range-start": "192.168.100.200",
            }
        )

    def test_options_errors(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env_assist.get_env(), "B1", "docker",
                {"image": "pcs:test", },
                network_options={
                    "control-port": "0",
                    "host-netmask": "abc",
                    "extra": "option",
                }
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "control-port",
                        "option_value": "0",
                        "allowed_values": "a port number (1-65535)",
                    },
                    None
                ),
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "host-netmask",
                        "option_value": "abc",
                        "allowed_values": "a number of bits of the mask (1-32)",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["extra", ],
                        "option_type": "network",
                        "allowed": self.allowed_options,
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE_OPTIONS
                ),
            ]
        )

    def test_options_forced(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" />
                        <network host-netmask="abc" extra="option" />
                    </bundle>
                </resources>
            """
        )
        resource.bundle_create(
            self.env_assist.get_env(), "B1", "docker",
            {
                "image": "pcs:test",
            },
            network_options={
                "host-netmask": "abc",
                "extra": "option",
            },
            force_options=True
        )

        self.env_assist.assert_reports([
            (
                severities.WARNING,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "host-netmask",
                    "option_value": "abc",
                    "allowed_values": "a number of bits of the mask (1-32)",
                },
                None
            ),
            (
                severities.WARNING,
                report_codes.INVALID_OPTIONS,
                {
                    "option_names": ["extra", ],
                    "option_type": "network",
                    "allowed": self.allowed_options,
                    "allowed_patterns": [],
                },
                None
            ),
        ])


class CreateWithPortMap(TestCase):
    allowed_options = [
        "id",
        "internal-port",
        "port",
        "range",
    ]

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(resources=fixture_cib_pre)

    def test_no_options(self):
        self.config.env.push_cib(resources=fixture_resources_bundle_simple)
        resource.bundle_create(
            self.env_assist.get_env(), "B1", "docker",
            {"image": "pcs:test", },
            port_map=[]
        )

    def test_several_mappings_and_handle_their_ids(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" />
                        <network>
                            <port-mapping id="B1-port-map-1001-1" port="1001" />
                            <port-mapping
                                id="B1-port-map-1001"
                                internal-port="2002"
                                port="2000"
                            />
                            <port-mapping
                                id="B1-port-map-3000-3300"
                                range="3000-3300"
                            />
                        </network>
                    </bundle>
                </resources>
            """
        )
        resource.bundle_create(
            self.env_assist.get_env(), "B1", "docker",
            {"image": "pcs:test", },
            port_map=[
                {
                    "port": "1001",
                },
                {
                    # use an autogenerated id of the previous item
                    "id": "B1-port-map-1001",
                    "port": "2000",
                    "internal-port": "2002",
                },
                {
                    "range": "3000-3300",
                },
            ]
        )

    def test_options_errors(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env_assist.get_env(), "B1", "docker",
                {"image": "pcs:test", },
                port_map=[
                    {
                    },
                    {
                        "id": "not#valid",
                    },
                    {
                        "internal-port": "1000",
                    },
                    {
                        "port": "abc",
                    },
                    {
                        "port": "2000",
                        "range": "3000-4000",
                        "internal-port": "def",
                    },
                ],
                force_options=True
            ),
            [
                # first
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING,
                    {
                        "option_type": "port-map",
                        "option_names": ["port", "range"],
                    },
                    None
                ),
                # second
                (
                    severities.ERROR,
                    report_codes.INVALID_ID,
                    {
                        "invalid_character": "#",
                        "id": "not#valid",
                        "id_description": "port-map id",
                        "is_first_char": False,
                    },
                    None
                ),
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING,
                    {
                        "option_type": "port-map",
                        "option_names": ["port", "range"],
                    },
                    None
                ),
                # third
                (
                    severities.ERROR,
                    report_codes.PREREQUISITE_OPTION_IS_MISSING,
                    {
                        "option_type": "port-map",
                        "option_name": "internal-port",
                        "prerequisite_type": "port-map",
                        "prerequisite_name": "port",
                    },
                    None
                ),
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING,
                    {
                        "option_type": "port-map",
                        "option_names": ["port", "range"],
                    },
                    None
                ),
                # fourth
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "port",
                        "option_value": "abc",
                        "allowed_values": "a port number (1-65535)",
                    },
                    None
                ),
                # fifth
                (
                    severities.ERROR,
                    report_codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                    {
                        "option_names": ["port", "range", ],
                        "option_type": "port-map",
                    },
                    None
                ),
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "internal-port",
                        "option_value": "def",
                        "allowed_values": "a port number (1-65535)",
                    },
                    None
                ),
            ]
        )

    def test_forceable_options_errors(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env_assist.get_env(), "B1", "docker",
                {"image": "pcs:test", },
                port_map=[
                    {
                        "range": "3000",
                        "extra": "option",
                    },
                ]
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["extra", ],
                        "option_type": "port-map",
                        "allowed": self.allowed_options,
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "range",
                        "option_value": "3000",
                        "allowed_values": "port-port",
                    },
                    report_codes.FORCE_OPTIONS
                ),
            ]
        )

    def test_forceable_options_errors_forced(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" />
                        <network>
                            <port-mapping
                                id="B1-port-map-3000"
                                extra="option"
                                range="3000"
                            />
                        </network>
                    </bundle>
                </resources>
            """,
        )

        resource.bundle_create(
            self.env_assist.get_env(), "B1", "docker",
            {
                "image": "pcs:test",
            },
            port_map=[
                {
                    "range": "3000",
                    "extra": "option",
                },
            ],
            force_options=True
        )

        self.env_assist.assert_reports([
            (
                severities.WARNING,
                report_codes.INVALID_OPTIONS,
                {
                    "option_names": ["extra", ],
                    "option_type": "port-map",
                    "allowed": self.allowed_options,
                    "allowed_patterns": [],
                },
                None
            ),
            (
                severities.WARNING,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "range",
                    "option_value": "3000",
                    "allowed_values": "port-port",
                },
                None
            ),
        ])


class CreateWithStorageMap(TestCase):
    allowed_options = [
        "id",
        "options",
        "source-dir",
        "source-dir-root",
        "target-dir",
    ]

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(resources=fixture_cib_pre)


    def test_several_mappings_and_handle_their_ids(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" />
                        <storage>
                            <storage-mapping
                                id="B1-storage-map-1"
                                source-dir="/tmp/docker1a"
                                target-dir="/tmp/docker1b"
                            />
                            <storage-mapping
                                id="B1-storage-map"
                                options="extra options 1"
                                source-dir="/tmp/docker2a"
                                target-dir="/tmp/docker2b"
                            />
                            <storage-mapping
                                id="B1-storage-map-3"
                                source-dir-root="/tmp/docker3a"
                                target-dir="/tmp/docker3b"
                            />
                            <storage-mapping
                                id="B1-storage-map-2"
                                options="extra options 2"
                                source-dir-root="/tmp/docker4a"
                                target-dir="/tmp/docker4b"
                            />
                        </storage>
                    </bundle>
                </resources>
            """
        )
        resource.bundle_create(
            self.env_assist.get_env(), "B1", "docker",
            {"image": "pcs:test", },
            storage_map=[
                {
                    "source-dir": "/tmp/docker1a",
                    "target-dir": "/tmp/docker1b",
                },
                {
                    # use an autogenerated id of the previous item
                    "id": "B1-storage-map",
                    "source-dir": "/tmp/docker2a",
                    "target-dir": "/tmp/docker2b",
                    "options": "extra options 1"
                },
                {
                    "source-dir-root": "/tmp/docker3a",
                    "target-dir": "/tmp/docker3b",
                },
                {
                    # use an autogenerated id of the previous item
                    "id": "B1-storage-map-2",
                    "source-dir-root": "/tmp/docker4a",
                    "target-dir": "/tmp/docker4b",
                    "options": "extra options 2"
                },
            ]
        )

    def test_options_errors(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env_assist.get_env(), "B1", "docker",
                {"image": "pcs:test", },
                storage_map=[
                    {
                    },
                    {
                        "id": "not#valid",
                        "source-dir": "/tmp/docker1a",
                        "source-dir-root": "/tmp/docker1b",
                        "target-dir": "/tmp/docker1c",
                    },
                ],
                force_options=True
            ),
            [
                # first
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING,
                    {
                        "option_type": "storage-map",
                        "option_names": ["source-dir", "source-dir-root"],
                    },
                    None
                ),
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    {
                        "option_type": "storage-map",
                        "option_names": ["target-dir", ],
                    },
                    None
                ),
                # second
                (
                    severities.ERROR,
                    report_codes.INVALID_ID,
                    {
                        "invalid_character": "#",
                        "id": "not#valid",
                        "id_description": "storage-map id",
                        "is_first_char": False,
                    },
                    None
                ),
                (
                    severities.ERROR,
                    report_codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                    {
                        "option_type": "storage-map",
                        "option_names": ["source-dir", "source-dir-root"],
                    },
                    None
                ),
            ]
        )

    def test_forceable_options_errors(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env_assist.get_env(), "B1", "docker",
                {"image": "pcs:test", },
                storage_map=[
                    {
                        "source-dir": "/tmp/docker1a",
                        "target-dir": "/tmp/docker1b",
                        "extra": "option",
                    },
                ]
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["extra", ],
                        "option_type": "storage-map",
                        "allowed": self.allowed_options,
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE_OPTIONS
                ),
            ]
        )

    def test_forceable_options_errors_forced(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" />
                        <storage>
                            <storage-mapping
                                id="B1-storage-map"
                                source-dir="/tmp/docker1a"
                                target-dir="/tmp/docker1b"
                                extra="option"
                            />
                        </storage>
                    </bundle>
                </resources>
            """,
        )

        resource.bundle_create(
            self.env_assist.get_env(), "B1", "docker",
            {
                "image": "pcs:test",
            },
            storage_map=[
                {
                    "source-dir": "/tmp/docker1a",
                    "target-dir": "/tmp/docker1b",
                    "extra": "option",
                },
            ],
            force_options=True
        )

        self.env_assist.assert_reports(
            [
                (
                    severities.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["extra", ],
                        "option_type": "storage-map",
                        "allowed": self.allowed_options,
                        "allowed_patterns": [],
                    },
                    None
                ),
            ]
        )


class CreateWithMeta(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(resources=fixture_cib_pre)

    def test_success(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" />
                        <meta_attributes id="B1-meta_attributes">
                            <nvpair id="B1-meta_attributes-is-managed"
                                name="is-managed" value="false" />
                            <nvpair id="B1-meta_attributes-target-role"
                                name="target-role" value="Stopped" />
                        </meta_attributes>
                    </bundle>
                </resources>
            """
        )
        resource.bundle_create(
            self.env_assist.get_env(), "B1", "docker",
            container_options={"image": "pcs:test", },
            meta_attributes={
                "target-role": "Stopped",
                "is-managed": "false",
            }
        )

    def test_disabled(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="B1">
                        <meta_attributes id="B1-meta_attributes">
                            <nvpair id="B1-meta_attributes-target-role"
                                name="target-role" value="Stopped" />
                        </meta_attributes>
                        <docker image="pcs:test" />
                    </bundle>
                </resources>
            """
        )
        resource.bundle_create(
            self.env_assist.get_env(), "B1", "docker",
            container_options={"image": "pcs:test", },
            ensure_disabled=True
        )

class CreateWithAllOptions(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(resources=fixture_cib_pre)

    def test_success(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="B1">
                        <docker
                            image="pcs:test"
                            masters="0"
                            network="extra network settings"
                            options="extra options"
                            replicas="4"
                            replicas-per-host="2"
                            run-command="/bin/true"
                        />
                        <network
                            control-port="12345"
                            host-interface="eth0"
                            host-netmask="24"
                            ip-range-start="192.168.100.200"
                        >
                            <port-mapping id="B1-port-map-1001-2" port="1001" />
                            <port-mapping
                                id="B1-port-map-1001"
                                internal-port="2002"
                                port="2000"
                            />
                            <port-mapping
                                id="B1-port-map-3000-3300"
                                range="3000-3300"
                            />
                        </network>
                        <storage>
                            <storage-mapping
                                id="B1-storage-map-1"
                                source-dir="/tmp/docker1a"
                                target-dir="/tmp/docker1b"
                            />
                            <storage-mapping
                                id="B1-storage-map"
                                options="extra options 1"
                                source-dir="/tmp/docker2a"
                                target-dir="/tmp/docker2b"
                            />
                            <storage-mapping
                                id="B1-storage-map-2"
                                source-dir-root="/tmp/docker3a"
                                target-dir="/tmp/docker3b"
                            />
                            <storage-mapping
                                id="B1-port-map-1001-1"
                                options="extra options 2"
                                source-dir-root="/tmp/docker4a"
                                target-dir="/tmp/docker4b"
                            />
                        </storage>
                    </bundle>
                </resources>
            """
        )
        resource.bundle_create(
            self.env_assist.get_env(), "B1", "docker",
            container_options={
                "image": "pcs:test",
                "masters": "0",
                "network": "extra network settings",
                "options": "extra options",
                "run-command": "/bin/true",
                "replicas": "4",
                "replicas-per-host": "2",
            },
            network_options={
                "control-port": "12345",
                "host-interface": "eth0",
                "host-netmask": "24",
                "ip-range-start": "192.168.100.200",
            },
            port_map=[
                {
                    "port": "1001",
                },
                {
                    # use an autogenerated id of the previous item
                    "id": "B1-port-map-1001",
                    "port": "2000",
                    "internal-port": "2002",
                },
                {
                    "range": "3000-3300",
                },
            ],
            storage_map=[
                {
                    "source-dir": "/tmp/docker1a",
                    "target-dir": "/tmp/docker1b",
                },
                {
                    # use an autogenerated id of the previous item
                    "id": "B1-storage-map",
                    "source-dir": "/tmp/docker2a",
                    "target-dir": "/tmp/docker2b",
                    "options": "extra options 1"
                },
                {
                    "source-dir-root": "/tmp/docker3a",
                    "target-dir": "/tmp/docker3b",
                },
                {
                    # use an autogenerated id of the previous item
                    "id": "B1-port-map-1001-1",
                    "source-dir-root": "/tmp/docker4a",
                    "target-dir": "/tmp/docker4b",
                    "options": "extra options 2"
                },
            ]
        )


class Wait(TestCase):
    fixture_status_running = """
        <resources>
            <bundle id="B1" managed="true">
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
            <bundle id="B1" managed="true">
                <replica id="0">
                    <resource id="B1-docker-0" managed="true" role="Stopped" />
                </replica>
                <replica id="1">
                    <resource id="B1-docker-1" managed="true" role="Stopped" />
                </replica>
            </bundle>
        </resources>
    """

    fixture_resources_bundle_simple_disabled = """
        <resources>
            <bundle id="B1">
                <meta_attributes id="B1-meta_attributes">
                    <nvpair id="B1-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
                <docker image="pcs:test" />
            </bundle>
        </resources>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        (self.config
            .runner.pcmk.can_wait()
            .runner.cib.load(resources=fixture_cib_pre)
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
            resources=fixture_resources_bundle_simple,
            wait=TIMEOUT,
            exception=LibraryError(
                reports.wait_for_idle_timed_out(wait_error_message)
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: simple_bundle_create(self.env_assist.get_env()),
            [
                fixture.report_wait_for_idle_timed_out(wait_error_message)
            ],
            expected_in_processor=False
        )

    @skip_unless_pacemaker_supports_bundle
    def test_wait_ok_run_ok(self):
        (self.config
            .env.push_cib(
                resources=fixture_resources_bundle_simple,
                wait=TIMEOUT
            )
            .runner.pcmk.load_state(resources=self.fixture_status_running)
        )
        simple_bundle_create(self.env_assist.get_env())
        self.env_assist.assert_reports([
            fixture.report_resource_running(
                "B1", {"Started": ["node1", "node2"]}
            ),
        ])

    @skip_unless_pacemaker_supports_bundle
    def test_wait_ok_run_fail(self):
        (self.config
            .env.push_cib(
                resources=fixture_resources_bundle_simple,
                wait=TIMEOUT
            )
            .runner.pcmk.load_state(resources=self.fixture_status_not_running)
        )
        self.env_assist.assert_raise_library_error(
            lambda: simple_bundle_create(self.env_assist.get_env()),
            [
                fixture.report_resource_not_running("B1", severities.ERROR),
            ]
        )

    @skip_unless_pacemaker_supports_bundle
    def test_disabled_wait_ok_run_ok(self):
        (self.config
            .env.push_cib(
                resources=self.fixture_resources_bundle_simple_disabled,
                wait=TIMEOUT
            )
            .runner.pcmk.load_state(resources=self.fixture_status_not_running)
        )
        simple_bundle_create(self.env_assist.get_env(), disabled=True)
        self.env_assist.assert_reports([
            (
                severities.INFO,
                report_codes.RESOURCE_DOES_NOT_RUN,
                {
                    "resource_id": "B1"
                },
                None
            )
        ])

    @skip_unless_pacemaker_supports_bundle
    def test_disabled_wait_ok_run_fail(self):
        (self.config
            .env.push_cib(
                resources=self.fixture_resources_bundle_simple_disabled,
                wait=TIMEOUT
            )
            .runner.pcmk.load_state(resources=self.fixture_status_running)
        )
        self.env_assist.assert_raise_library_error(
            lambda:
            simple_bundle_create(self.env_assist.get_env(), disabled=True),
            [
                fixture.report_resource_running(
                    "B1", {"Started": ["node1", "node2"]}, severities.ERROR
                )
            ]
        )
