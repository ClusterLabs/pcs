from textwrap import dedent
from unittest import mock

from pcs import settings
from pcs.common import reports
from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.cib.resource.bundle import (
    GENERIC_CONTAINER_OPTIONS,
    NETWORK_OPTIONS,
    PORT_MAP_OPTIONS,
    STORAGE_MAP_OPTIONS,
)
from pcs.lib.errors import LibraryError

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc

TIMEOUT = 10


class FixturesMixin:
    container_type = None
    bundle_id = None
    image = None

    @property
    def fixture_resources_bundle_simple(self):
        return """
            <resources>
                <bundle id="{bundle_id}">
                    <{container_type} image="{image}" />
                </bundle>
            </resources>
        """.format(
            container_type=self.container_type,
            bundle_id=self.bundle_id,
            image=self.image,
        )


class SetUpMixin:
    initial_resources = "<resources/>"
    initial_cib_filename = "cib-empty.xml"

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(
            filename=self.initial_cib_filename,
            resources=self.initial_resources,
        )


class UpgradeMixin(FixturesMixin):
    old_version_cib_filename = None

    def test_cib_upgrade(self):
        (
            self.config.runner.cib.load(
                name="load_cib_old_version",
                filename=self.old_version_cib_filename,
                before="runner.cib.load",
            )
            .runner.cib.upgrade(before="runner.cib.load")
            .env.push_cib(resources=self.fixture_resources_bundle_simple)
        )

        self.run_bundle_cmd()

        self.env_assist.assert_reports(
            [fixture.info(report_codes.CIB_UPGRADE_SUCCESSFUL)]
        )


class ParametrizedContainerMixin(SetUpMixin):
    container_type = None
    bundle_id = None
    image = None
    initial_cib_filename = "cib-empty-3.2.xml"

    def test_all_options(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="{bundle_id}">
                        <{container_type}
                            image="{image}"
                            network="extra network settings"
                            options="extra options"
                            promoted-max="0"
                            replicas="4"
                            replicas-per-host="2"
                            run-command="/bin/true"
                        />
                    </bundle>
                </resources>
            """.format(
                container_type=self.container_type,
                bundle_id=self.bundle_id,
                image=self.image,
            )
        )
        self.run_bundle_cmd(
            container_options={
                "image": self.image,
                "network": "extra network settings",
                "options": "extra options",
                "promoted-max": "0",
                "run-command": "/bin/true",
                "replicas": "4",
                "replicas-per-host": "2",
            }
        )

    def test_deprecated_options(self):
        # Setting both deprecated options and their new variants is tested in
        # self.test_options_errors. This shows deprecated options emit warning
        # even when not forced.
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="{bundle_id}">
                        <{container_type} image="{image}" masters="1" />
                    </bundle>
                </resources>
            """.format(
                container_type=self.container_type,
                bundle_id=self.bundle_id,
                image=self.image,
            ),
        )
        self.run_bundle_cmd(
            container_options={
                "image": self.image,
                "masters": "1",
            },
        )
        self.env_assist.assert_reports(
            [
                (
                    severities.DEPRECATION,
                    report_codes.DEPRECATED_OPTION,
                    {
                        "option_name": "masters",
                        "option_type": "container",
                        "replaced_by": ["promoted-max"],
                    },
                    None,
                ),
            ]
        )

    def test_invalid_container_options(self):
        self.env_assist.assert_raise_library_error(
            lambda: self.run_bundle_cmd(
                container_options={
                    "replicas-per-host": "0",
                    "replicas": "0",
                    "masters": "-1",
                    "promoted-max": "-2",
                },
                force_options=True,
            )
        )
        self.env_assist.assert_reports(
            [
                (
                    severities.DEPRECATION,
                    report_codes.DEPRECATED_OPTION,
                    {
                        "option_name": "masters",
                        "option_type": "container",
                        "replaced_by": ["promoted-max"],
                    },
                    None,
                ),
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    {
                        "option_type": "container",
                        "option_names": [
                            "image",
                        ],
                    },
                    None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="masters",
                    option_value="-1",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="promoted-max",
                    option_value="-2",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                (
                    severities.ERROR,
                    report_codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                    {
                        "option_names": [
                            "masters",
                            "promoted-max",
                        ],
                        "option_type": "container",
                    },
                    None,
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

    def test_empty_image(self):
        self.env_assist.assert_raise_library_error(
            lambda: self.run_bundle_cmd(
                container_options={
                    "image": "",
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

    def test_unknown_container_option(self):
        self.env_assist.assert_raise_library_error(
            lambda: self.run_bundle_cmd(
                container_options={
                    "image": self.image,
                    "extra": "option",
                }
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
                        "allowed": sorted(GENERIC_CONTAINER_OPTIONS),
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE,
                ),
            ]
        )

    def test_unknown_container_option_forced(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="{bundle_id}">
                        <{container_type} image="{image}" extra="option" />
                    </bundle>
                </resources>
            """.format(
                container_type=self.container_type,
                bundle_id=self.bundle_id,
                image=self.image,
            ),
        )
        self.run_bundle_cmd(
            container_options={
                "image": self.image,
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
                        "allowed": sorted(GENERIC_CONTAINER_OPTIONS),
                        "allowed_patterns": [],
                    },
                    None,
                ),
            ]
        )


class NetworkMixin(SetUpMixin):
    container_type = None
    bundle_id = None
    image = None

    def test_all_options(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="{bundle_id}">
                        <{container_type} image="{image}" />
                        <network
                            control-port="12345"
                            host-interface="eth0"
                            host-netmask="24"
                            ip-range-start="192.168.100.200"
                        />
                    </bundle>
                </resources>
            """.format(
                container_type=self.container_type,
                bundle_id=self.bundle_id,
                image=self.image,
            ),
        )
        self.run_bundle_cmd(
            network_options={
                "control-port": "12345",
                "host-interface": "eth0",
                "host-netmask": "24",
                "ip-range-start": "192.168.100.200",
            }
        )

    def test_options_errors(self):
        self.env_assist.assert_raise_library_error(
            lambda: self.run_bundle_cmd(
                network_options={
                    "control-port": "0",
                    "host-netmask": "abc",
                    "extra": "option",
                }
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="control-port",
                    option_value="0",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="host-netmask",
                    option_value="abc",
                    allowed_values="a number of bits of the mask (1..32)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    force_code=report_codes.FORCE,
                    option_names=["extra"],
                    option_type="network",
                    allowed=sorted(NETWORK_OPTIONS),
                    allowed_patterns=[],
                ),
            ]
        )

    def test_options_forced(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="{bundle_id}">
                        <{container_type} image="{image}" />
                        <network host-netmask="abc" extra="option" />
                    </bundle>
                </resources>
            """.format(
                container_type=self.container_type,
                bundle_id=self.bundle_id,
                image=self.image,
            ),
        )
        self.run_bundle_cmd(
            network_options={
                "host-netmask": "abc",
                "extra": "option",
            },
            force_options=True,
        )

        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host-netmask",
                    option_value="abc",
                    allowed_values="a number of bits of the mask (1..32)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                (
                    severities.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": [
                            "extra",
                        ],
                        "option_type": "network",
                        "allowed": sorted(NETWORK_OPTIONS),
                        "allowed_patterns": [],
                    },
                    None,
                ),
            ]
        )


class PortMapMixin(SetUpMixin):
    container_type = None
    bundle_id = None
    image = None

    def test_several_mappings_and_handle_their_ids(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="{bundle_id}">
                        <{container_type} image="{image}" />
                        <network>
                            <port-mapping
                                id="{bundle_id}-port-map-1001-1"
                                port="1001"
                            />
                            <port-mapping
                                id="{bundle_id}-port-map-1001"
                                internal-port="2002"
                                port="2000"
                            />
                            <port-mapping
                                id="{bundle_id}-port-map-3000-3300"
                                range="3000-3300"
                            />
                        </network>
                    </bundle>
                </resources>
            """.format(
                container_type=self.container_type,
                bundle_id=self.bundle_id,
                image=self.image,
            )
        )
        self.run_bundle_cmd(
            port_map=[
                {
                    "port": "1001",
                },
                {
                    # use an autogenerated id of the previous item
                    "id": "{bundle_id}-port-map-1001".format(
                        bundle_id=self.bundle_id
                    ),
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
            lambda: self.run_bundle_cmd(
                port_map=[
                    {},
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
                force_options=True,
            )
        )
        self.env_assist.assert_reports(
            [
                # first
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING,
                    {
                        "option_type": "port-map",
                        "option_names": ["port", "range"],
                        "deprecated_names": [],
                    },
                    None,
                ),
                # second
                (
                    severities.ERROR,
                    report_codes.INVALID_ID_BAD_CHAR,
                    {
                        "invalid_character": "#",
                        "id": "not#valid",
                        "id_description": "port-map id",
                        "is_first_char": False,
                    },
                    None,
                ),
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING,
                    {
                        "option_type": "port-map",
                        "option_names": ["port", "range"],
                        "deprecated_names": [],
                    },
                    None,
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
                    None,
                ),
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING,
                    {
                        "option_type": "port-map",
                        "option_names": ["port", "range"],
                        "deprecated_names": [],
                    },
                    None,
                ),
                # fourth
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="port",
                    option_value="abc",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                # fifth
                (
                    severities.ERROR,
                    report_codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                    {
                        "option_names": ["port", "range"],
                        "option_type": "port-map",
                    },
                    None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="internal-port",
                    option_value="def",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_forceable_options_errors(self):
        self.env_assist.assert_raise_library_error(
            lambda: self.run_bundle_cmd(
                port_map=[
                    {
                        "range": "3000",
                        "extra": "option",
                    },
                ]
            )
        )
        self.env_assist.assert_reports(
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["extra"],
                        "option_type": "port-map",
                        "allowed": sorted(PORT_MAP_OPTIONS),
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="range",
                    option_value="3000",
                    allowed_values="port-port",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_forceable_options_errors_forced(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="{bundle_id}">
                        <{container_type} image="{image}" />
                        <network>
                            <port-mapping
                                id="{bundle_id}-port-map-3000"
                                extra="option"
                                range="3000"
                            />
                        </network>
                    </bundle>
                </resources>
            """.format(
                container_type=self.container_type,
                bundle_id=self.bundle_id,
                image=self.image,
            )
        )

        self.run_bundle_cmd(
            port_map=[
                {
                    "range": "3000",
                    "extra": "option",
                },
            ],
            force_options=True,
        )

        self.env_assist.assert_reports(
            [
                (
                    severities.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["extra"],
                        "option_type": "port-map",
                        "allowed": sorted(PORT_MAP_OPTIONS),
                        "allowed_patterns": [],
                    },
                    None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="range",
                    option_value="3000",
                    allowed_values="port-port",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )


class StorageMapMixin(SetUpMixin):
    container_type = None
    bundle_id = None
    image = None

    def test_several_mappings_and_handle_their_ids(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="{bundle_id}">
                        <{container_type} image="{image}" />
                        <storage>
                            <storage-mapping
                                id="{bundle_id}-storage-map-1"
                                source-dir="/tmp/bundle1a"
                                target-dir="/tmp/bundle1b"
                            />
                            <storage-mapping
                                id="{bundle_id}-storage-map"
                                options="extra options 1"
                                source-dir="/tmp/bundle2a"
                                target-dir="/tmp/bundle2b"
                            />
                            <storage-mapping
                                id="{bundle_id}-storage-map-3"
                                source-dir-root="/tmp/bundle3a"
                                target-dir="/tmp/bundle3b"
                            />
                            <storage-mapping
                                id="{bundle_id}-storage-map-2"
                                options="extra options 2"
                                source-dir-root="/tmp/bundle4a"
                                target-dir="/tmp/bundle4b"
                            />
                        </storage>
                    </bundle>
                </resources>
            """.format(
                container_type=self.container_type,
                bundle_id=self.bundle_id,
                image=self.image,
            )
        )

        self.run_bundle_cmd(
            storage_map=[
                {
                    "source-dir": "/tmp/bundle1a",
                    "target-dir": "/tmp/bundle1b",
                },
                {
                    # use an autogenerated id of the previous item
                    "id": "{bundle_id}-storage-map".format(
                        bundle_id=self.bundle_id
                    ),
                    "source-dir": "/tmp/bundle2a",
                    "target-dir": "/tmp/bundle2b",
                    "options": "extra options 1",
                },
                {
                    "source-dir-root": "/tmp/bundle3a",
                    "target-dir": "/tmp/bundle3b",
                },
                {
                    # use an autogenerated id of the previous item
                    "id": "{bundle_id}-storage-map-2".format(
                        bundle_id=self.bundle_id
                    ),
                    "source-dir-root": "/tmp/bundle4a",
                    "target-dir": "/tmp/bundle4b",
                    "options": "extra options 2",
                },
            ]
        )

    def test_options_errors(self):
        self.env_assist.assert_raise_library_error(
            lambda: self.run_bundle_cmd(
                storage_map=[
                    {},
                    {
                        "id": "not#valid",
                        "source-dir": "/tmp/bundle1a",
                        "source-dir-root": "/tmp/bundle1b",
                        "target-dir": "/tmp/bundle1c",
                    },
                ],
                force_options=True,
            )
        )
        self.env_assist.assert_reports(
            [
                # first
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING,
                    {
                        "option_type": "storage-map",
                        "option_names": ["source-dir", "source-dir-root"],
                        "deprecated_names": [],
                    },
                    None,
                ),
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    {
                        "option_type": "storage-map",
                        "option_names": ["target-dir"],
                    },
                    None,
                ),
                # second
                (
                    severities.ERROR,
                    report_codes.INVALID_ID_BAD_CHAR,
                    {
                        "invalid_character": "#",
                        "id": "not#valid",
                        "id_description": "storage-map id",
                        "is_first_char": False,
                    },
                    None,
                ),
                (
                    severities.ERROR,
                    report_codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                    {
                        "option_type": "storage-map",
                        "option_names": ["source-dir", "source-dir-root"],
                    },
                    None,
                ),
            ]
        )

    def test_forceable_options_errors(self):
        self.env_assist.assert_raise_library_error(
            lambda: self.run_bundle_cmd(
                storage_map=[
                    {
                        "source-dir": "/tmp/bundle1a",
                        "target-dir": "/tmp/bundle1b",
                        "extra": "option",
                    },
                ]
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
                        "option_type": "storage-map",
                        "allowed": sorted(STORAGE_MAP_OPTIONS),
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE,
                ),
            ]
        )

    def test_forceable_options_errors_forced(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="{bundle_id}">
                        <{container_type} image="{image}" />
                        <storage>
                            <storage-mapping
                                id="{bundle_id}-storage-map"
                                source-dir="/tmp/bundle1a"
                                target-dir="/tmp/bundle1b"
                                extra="option"
                            />
                        </storage>
                    </bundle>
                </resources>
            """.format(
                container_type=self.container_type,
                bundle_id=self.bundle_id,
                image=self.image,
            )
        )

        self.run_bundle_cmd(
            storage_map=[
                {
                    "source-dir": "/tmp/bundle1a",
                    "target-dir": "/tmp/bundle1b",
                    "extra": "option",
                },
            ],
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
                        "option_type": "storage-map",
                        "allowed": sorted(STORAGE_MAP_OPTIONS),
                        "allowed_patterns": [],
                    },
                    None,
                ),
            ]
        )


class MetaMixin(SetUpMixin):
    container_type = None
    bundle_id = None
    image = None

    def test_success(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="{bundle_id}">
                        <{container_type} image="{image}" />
                        <meta_attributes id="{bundle_id}-meta_attributes">
                            <nvpair id="{bundle_id}-meta_attributes-is-managed"
                                name="is-managed" value="false" />
                            <nvpair id="{bundle_id}-meta_attributes-target-role"
                                name="target-role" value="Stopped" />
                        </meta_attributes>
                    </bundle>
                </resources>
            """.format(
                container_type=self.container_type,
                bundle_id=self.bundle_id,
                image=self.image,
            )
        )
        self.run_bundle_cmd(
            meta_attributes={
                "target-role": "Stopped",
                "is-managed": "false",
            }
        )

    def test_disabled(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="{bundle_id}">
                        <meta_attributes id="{bundle_id}-meta_attributes">
                            <nvpair id="{bundle_id}-meta_attributes-target-role"
                                name="target-role" value="Stopped" />
                        </meta_attributes>
                        <{container_type} image="{image}" />
                    </bundle>
                </resources>
            """.format(
                container_type=self.container_type,
                bundle_id=self.bundle_id,
                image=self.image,
            )
        )
        self.run_bundle_cmd(ensure_disabled=True)


class AllOptionsMixin(SetUpMixin):
    container_type = None
    bundle_id = None
    image = None

    def test_success(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="{bundle_id}">
                        <{container_type}
                            image="{image}"
                            network="extra network settings"
                            options="extra options"
                            promoted-max="0"
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
                            <port-mapping
                                id="{bundle_id}-port-map-1001-2"
                                port="1001"
                            />
                            <port-mapping
                                id="{bundle_id}-port-map-1001"
                                internal-port="2002"
                                port="2000"
                            />
                            <port-mapping
                                id="{bundle_id}-port-map-3000-3300"
                                range="3000-3300"
                            />
                        </network>
                        <storage>
                            <storage-mapping
                                id="{bundle_id}-storage-map-1"
                                source-dir="/tmp/bundle1a"
                                target-dir="/tmp/bundle1b"
                            />
                            <storage-mapping
                                id="{bundle_id}-storage-map"
                                options="extra options 1"
                                source-dir="/tmp/bundle2a"
                                target-dir="/tmp/bundle2b"
                            />
                            <storage-mapping
                                id="{bundle_id}-storage-map-2"
                                source-dir-root="/tmp/bundle3a"
                                target-dir="/tmp/bundle3b"
                            />
                            <storage-mapping
                                id="{bundle_id}-port-map-1001-1"
                                options="extra options 2"
                                source-dir-root="/tmp/bundle4a"
                                target-dir="/tmp/bundle4b"
                            />
                        </storage>
                    </bundle>
                </resources>
            """.format(
                container_type=self.container_type,
                bundle_id=self.bundle_id,
                image=self.image,
            )
        )
        self.run_bundle_cmd(
            container_options={
                "image": self.image,
                "promoted-max": "0",
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
                    "id": "{bundle_id}-port-map-1001".format(
                        bundle_id=self.bundle_id
                    ),
                    "port": "2000",
                    "internal-port": "2002",
                },
                {
                    "range": "3000-3300",
                },
            ],
            storage_map=[
                {
                    "source-dir": "/tmp/bundle1a",
                    "target-dir": "/tmp/bundle1b",
                },
                {
                    # use an autogenerated id of the previous item
                    "id": "{bundle_id}-storage-map".format(
                        bundle_id=self.bundle_id
                    ),
                    "source-dir": "/tmp/bundle2a",
                    "target-dir": "/tmp/bundle2b",
                    "options": "extra options 1",
                },
                {
                    "source-dir-root": "/tmp/bundle3a",
                    "target-dir": "/tmp/bundle3b",
                },
                {
                    # use an autogenerated id of the previous item
                    "id": "{bundle_id}-port-map-1001-1".format(
                        bundle_id=self.bundle_id
                    ),
                    "source-dir-root": "/tmp/bundle4a",
                    "target-dir": "/tmp/bundle4b",
                    "options": "extra options 2",
                },
            ],
        )


class WaitMixin(FixturesMixin, SetUpMixin):
    initial_resources = "<resources/>"
    bundle_id = None
    image = None

    @property
    def fixture_status_running(self):
        return """
            <resources>
                <bundle id="{bundle_id}" managed="true">
                    <replica id="0">
                        <resource
                            id="{bundle_id}-docker-0"
                            managed="true"
                            role="Started"
                        >
                            <node name="node1" id="1" cached="false"/>
                        </resource>
                    </replica>
                    <replica id="1">
                        <resource
                            id="{bundle_id}-docker-1"
                            managed="true"
                            role="Started"
                        >
                            <node name="node2" id="2" cached="false"/>
                        </resource>
                    </replica>
                </bundle>
            </resources>
        """.format(bundle_id=self.bundle_id)

    @property
    def fixture_status_not_running(self):
        return """
            <resources>
                <bundle id="{bundle_id}" managed="true">
                    <replica id="0">
                        <resource
                            id="{bundle_id}-docker-0"
                            managed="true"
                            role="Stopped"
                        />
                    </replica>
                    <replica id="1">
                        <resource
                            id="{bundle_id}-docker-1"
                            managed="true"
                            role="Stopped"
                        />
                    </replica>
                </bundle>
            </resources>
        """.format(bundle_id=self.bundle_id)

    @property
    def fixture_resources_bundle_simple_disabled(self):
        return """
            <resources>
                <bundle id="{bundle_id}">
                    <meta_attributes id="{bundle_id}-meta_attributes">
                        <nvpair id="{bundle_id}-meta_attributes-target-role"
                            name="target-role" value="Stopped" />
                    </meta_attributes>
                    <docker image="{image}" />
                </bundle>
            </resources>
        """.format(bundle_id=self.bundle_id, image=self.image)

    def test_wait_fail(self):
        wait_error_message = dedent(
            """\
            Pending actions:
                    Action 12: {bundle_id}-node2-stop on node2
            Error performing operation: Timer expired
            """.format(bundle_id=self.bundle_id)
        ).strip()
        self.config.env.push_cib(
            resources=self.fixture_resources_bundle_simple,
            wait=TIMEOUT,
            exception=LibraryError(
                reports.item.ReportItem.error(
                    reports.messages.WaitForIdleTimedOut(wait_error_message)
                )
            ),
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.run_bundle_cmd(wait=TIMEOUT),
            [fixture.report_wait_for_idle_timed_out(wait_error_message)],
            expected_in_processor=False,
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_run_ok(self):
        (
            self.config.env.push_cib(
                resources=self.fixture_resources_bundle_simple, wait=TIMEOUT
            ).runner.pcmk.load_state(resources=self.fixture_status_running)
        )
        self.run_bundle_cmd(wait=TIMEOUT)
        self.env_assist.assert_reports(
            [
                fixture.report_resource_running(
                    self.bundle_id, {"Started": ["node1", "node2"]}
                ),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_run_fail(self):
        (
            self.config.env.push_cib(
                resources=self.fixture_resources_bundle_simple, wait=TIMEOUT
            ).runner.pcmk.load_state(resources=self.fixture_status_not_running)
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.run_bundle_cmd(wait=TIMEOUT)
        )
        self.env_assist.assert_reports(
            [
                fixture.report_resource_not_running(
                    self.bundle_id, severities.ERROR
                ),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_disabled_wait_ok_run_ok(self):
        (
            self.config.env.push_cib(
                resources=self.fixture_resources_bundle_simple_disabled,
                wait=TIMEOUT,
            ).runner.pcmk.load_state(resources=self.fixture_status_not_running)
        )
        self.run_bundle_cmd(ensure_disabled=True, wait=TIMEOUT)
        self.env_assist.assert_reports(
            [
                (
                    severities.INFO,
                    report_codes.RESOURCE_DOES_NOT_RUN,
                    {
                        "resource_id": self.bundle_id,
                    },
                    None,
                )
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_disabled_wait_ok_run_fail(self):
        (
            self.config.env.push_cib(
                resources=self.fixture_resources_bundle_simple_disabled,
                wait=TIMEOUT,
            ).runner.pcmk.load_state(resources=self.fixture_status_running)
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.run_bundle_cmd(ensure_disabled=True, wait=TIMEOUT)
        )
        self.env_assist.assert_reports(
            [
                fixture.report_resource_running(
                    self.bundle_id,
                    {"Started": ["node1", "node2"]},
                    severities.ERROR,
                )
            ]
        )
