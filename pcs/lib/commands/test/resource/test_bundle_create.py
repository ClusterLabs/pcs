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
    fixture_cib_pre = "<resources />"
    fixture_resources_bundle_simple = """
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


class MinimalCreate(CommonTest):
    def test_success(self):
        self.assert_command_effect(
            self.fixture_cib_pre,
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {"image": "pcs:test", }
            ),
            self.fixture_resources_bundle_simple
        )

    def test_errors(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(self.fixture_cib_pre)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_create(self.env, "B#1", "nonsense"),
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
        )
        self.runner.assert_everything_launched()

    def test_cib_upgrade(self):
        self.runner.set_runs(
            fixture.calls_cib_load_and_upgrade(self.fixture_cib_pre)
            +
            fixture.calls_cib(
                self.fixture_cib_pre,
                self.fixture_resources_bundle_simple,
                cib_base_file=self.cib_base_file
            )
        )

        resource.bundle_create(
            self.env, "B1", "docker",
            {"image": "pcs:test", }
        )

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



class CreateDocker(CommonTest):
    allowed_options = [
        "image",
        "masters",
        "network",
        "options",
        "replicas",
        "replicas-per-host",
        "run-command",
    ]

    def test_minimal(self):
        self.assert_command_effect(
            self.fixture_cib_pre,
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {"image": "pcs:test", }
            ),
            self.fixture_resources_bundle_simple
        )

    def test_all_options(self):
        self.assert_command_effect(
            self.fixture_cib_pre,
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {
                    "image": "pcs:test",
                    "masters": "0",
                    "network": "extra network settings",
                    "options": "extra options",
                    "run-command": "/bin/true",
                    "replicas": "4",
                    "replicas-per-host": "2",
                }
            ),
            """
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

    def test_options_errors(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(self.fixture_cib_pre)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {
                    "replicas-per-host": "0",
                    "replicas": "0",
                    "masters": "-1",
                },
                force_options=True
            ),
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
        )
        self.runner.assert_everything_launched()

    def test_empty_image(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(self.fixture_cib_pre)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {
                    "image": "",
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
                self.fixture_cib_resources(self.fixture_cib_pre)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {
                    "image": "pcs:test",
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
            self.fixture_cib_pre,
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {
                    "image": "pcs:test",
                    "extra": "option",
                },
                force_options=True
            ),
            """
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" extra="option" />
                    </bundle>
                </resources>
            """,
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


class CreateWithNetwork(CommonTest):
    allowed_options = [
        "control-port",
        "host-interface",
        "host-netmask",
        "ip-range-start",
    ]

    def test_no_options(self):
        self.assert_command_effect(
            self.fixture_cib_pre,
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {"image": "pcs:test", },
                network_options={}
            ),
            self.fixture_resources_bundle_simple
        )

    def test_all_options(self):
        self.assert_command_effect(
            self.fixture_cib_pre,
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {"image": "pcs:test", },
                network_options={
                    "control-port": "12345",
                    "host-interface": "eth0",
                    "host-netmask": "24",
                    "ip-range-start": "192.168.100.200",
                }
            ),
            """
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

    def test_options_errors(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(self.fixture_cib_pre)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {"image": "pcs:test", },
                network_options={
                    "control-port": "0",
                    "host-netmask": "abc",
                    "extra": "option",
                }
            ),
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

    def test_options_forced(self):
        self.assert_command_effect(
            self.fixture_cib_pre,
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {
                    "image": "pcs:test",
                },
                network_options={
                    "host-netmask": "abc",
                    "extra": "option",
                },
                force_options=True
            ),
            """
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" />
                        <network host-netmask="abc" extra="option" />
                    </bundle>
                </resources>
            """,
            [
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


class CreateWithPortMap(CommonTest):
    allowed_options = [
        "id",
        "internal-port",
        "port",
        "range",
    ]

    def test_no_options(self):
        self.assert_command_effect(
            self.fixture_cib_pre,
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {"image": "pcs:test", },
                port_map=[]
            ),
            self.fixture_resources_bundle_simple
        )

    def test_several_mappings_and_handle_their_ids(self):
        self.assert_command_effect(
            self.fixture_cib_pre,
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
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
            ),
            """
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

    def test_options_errors(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(self.fixture_cib_pre)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
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
        )
        self.runner.assert_everything_launched()

    def test_forceable_options_errors(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(self.fixture_cib_pre)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {"image": "pcs:test", },
                port_map=[
                    {
                        "range": "3000",
                        "extra": "option",
                    },
                ]
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option_names": ["extra", ],
                    "option_type": "port-map",
                    "allowed": self.allowed_options,
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
        )

    def test_forceable_options_errors_forced(self):
        self.assert_command_effect(
            self.fixture_cib_pre,
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
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
            ),
            """
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
            [
                (
                    severities.WARNING,
                    report_codes.INVALID_OPTION,
                    {
                        "option_names": ["extra", ],
                        "option_type": "port-map",
                        "allowed": self.allowed_options,
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
            ]
        )


class CreateWithStorageMap(CommonTest):
    allowed_options = [
        "id",
        "options",
        "source-dir",
        "source-dir-root",
        "target-dir",
    ]

    def test_several_mappings_and_handle_their_ids(self):
        self.assert_command_effect(
            self.fixture_cib_pre,
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
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
            ),
            """
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

    def test_options_errors(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(self.fixture_cib_pre)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
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
        )

    def test_forceable_options_errors(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                self.fixture_cib_resources(self.fixture_cib_pre)
            )
        )
        assert_raise_library_error(
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {"image": "pcs:test", },
                storage_map=[
                    {
                        "source-dir": "/tmp/docker1a",
                        "target-dir": "/tmp/docker1b",
                        "extra": "option",
                    },
                ]
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option_names": ["extra", ],
                    "option_type": "storage-map",
                    "allowed": self.allowed_options,
                },
                report_codes.FORCE_OPTIONS
            ),
        )

    def test_forceable_options_errors_forced(self):
        self.assert_command_effect(
            self.fixture_cib_pre,
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
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
            ),
            """
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
            [
                (
                    severities.WARNING,
                    report_codes.INVALID_OPTION,
                    {
                        "option_names": ["extra", ],
                        "option_type": "storage-map",
                        "allowed": self.allowed_options,
                    },
                    None
                ),
            ]
        )


class CreateWithAllOptions(CommonTest):
    def test_success(self):
        self.assert_command_effect(
            self.fixture_cib_pre,
            lambda: resource.bundle_create(
                self.env, "B1", "docker",
                {
                    "image": "pcs:test",
                    "masters": "0",
                    "network": "extra network settings",
                    "options": "extra options",
                    "run-command": "/bin/true",
                    "replicas": "4",
                    "replicas-per-host": "2",
                },
                {
                    "control-port": "12345",
                    "host-interface": "eth0",
                    "host-netmask": "24",
                    "ip-range-start": "192.168.100.200",
                },
                [
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
                [
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
            ),
            """
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


class Wait(CommonTest):
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

    def simple_bundle_create(self, wait=False):
        return resource.bundle_create(
            self.env, "B1", "docker", {"image": "pcs:test"}, wait=wait,
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
            lambda: self.simple_bundle_create(self.timeout),
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
        self.simple_bundle_create(self.timeout)
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
            lambda: self.simple_bundle_create(self.timeout),
            fixture.report_resource_not_running("B1", severities.ERROR),
        )
        self.runner.assert_everything_launched()
