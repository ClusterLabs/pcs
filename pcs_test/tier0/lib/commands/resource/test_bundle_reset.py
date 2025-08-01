from unittest import TestCase

from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.commands.resource import bundle_reset

from pcs_test.tier0.lib.commands.resource.bundle_common import (
    AllOptionsMixin,
    FixturesMixin,
    MetaMixin,
    NetworkMixin,
    ParametrizedContainerMixin,
    PortMapMixin,
    SetUpMixin,
    StorageMapMixin,
    WaitMixin,
)
from pcs_test.tools import fixture


class BaseMixin(FixturesMixin):
    container_type = None
    bundle_id = "B1"
    image = "pcs:test"

    @property
    def initial_resources(self):
        return self.fixture_resources_bundle_simple

    def bundle_reset(self, bundle_id=None, **params):
        if "container_options" not in params:
            params["container_options"] = {"image": self.image}

        bundle_reset(
            self.env_assist.get_env(),
            bundle_id=bundle_id or self.bundle_id,
            **params,
        )

    def run_bundle_cmd(self, *args, **kwargs):
        self.bundle_reset(*args, **kwargs)


class MinimalMixin(BaseMixin, SetUpMixin):
    container_type = None
    initial_cib_filename = "cib-empty-3.2.xml"

    def test_success_zero_change(self):
        # Resets a bundle with only an image set to a bundle with the same
        # image set and no other options.
        self.config.env.push_cib(resources=self.initial_resources)
        self.bundle_reset()

    def test_success_change(self):
        new_image = "{0}:new".format(self.image)

        self.config.env.push_cib(
            replace={
                ".//resources/bundle": """
                    <bundle id="{bundle_id}">
                        <{container_type} image="{image}" />
                    </bundle>
                """.format(
                    bundle_id=self.bundle_id,
                    container_type=self.container_type,
                    image=new_image,
                ),
            }
        )
        self.bundle_reset(
            container_options={"image": new_image},
        )

    def test_nonexistent_id(self):
        self.env_assist.assert_raise_library_error(
            lambda: self.bundle_reset(bundle_id="B0"),
            [
                (
                    severities.ERROR,
                    report_codes.ID_NOT_FOUND,
                    {
                        "id": "B0",
                        "expected_types": ["bundle"],
                        "context_type": "resources",
                        "context_id": "",
                    },
                    None,
                ),
            ],
            expected_in_processor=False,
        )

    def test_no_options_set(self):
        self.env_assist.assert_raise_library_error(
            lambda: bundle_reset(self.env_assist.get_env(), self.bundle_id)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    option_names=["image"],
                    option_type="container",
                ),
            ]
        )


class FullMixin(SetUpMixin, BaseMixin):
    container_type = None
    fixture_primitive = """
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy"/>
    """

    @property
    def initial_resources(self):
        return """
            <resources>
                <bundle id="{bundle_id}">
                    <{container_type}
                        image="{image}"
                        promoted-max="0"
                        replicas="1"
                        replicas-per-host="1"
                    />
                    <network
                        control-port="12345"
                        host-interface="eth0"
                        host-netmask="24"
                        ip-range-start="192.168.100.200"
                    >
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
                            id="{bundle_id}-storage-map"
                            options="extra options 2"
                            source-dir="/tmp/{container_type}2a"
                            target-dir="/tmp/{container_type}2b"
                        />
                    </storage>
                    <meta_attributes id="{bundle_id}-meta_attributes">
                        <nvpair
                            id="{bundle_id}-meta_attributes-target-role"
                            name="target-role"
                            value="Stopped"
                        />
                    </meta_attributes>
                    {fixture_primitive}
                </bundle>
            </resources>
        """.format(
            container_type=self.container_type,
            bundle_id=self.bundle_id,
            fixture_primitive=self.fixture_primitive,
            image=self.image,
        )

    def test_success_minimal(self):
        new_image = "{0}:new".format(self.image)

        # Garbage (empty tags network, storage and meta_attributes) are kept.
        # See https://bugzilla.redhat.com/show_bug.cgi?id=1642514
        self.config.env.push_cib(
            replace={
                ".//resources/bundle": """
                    <bundle id="{bundle_id}">
                        <{container_type} image="{image}" />
                        <network/>
                        <storage/>
                        <meta_attributes id="{bundle_id}-meta_attributes"/>
                        {fixture_primitive}
                    </bundle>
                """.format(
                    container_type=self.container_type,
                    bundle_id=self.bundle_id,
                    fixture_primitive=self.fixture_primitive,
                    image=new_image,
                ),
            }
        )

        self.bundle_reset(
            container_options={"image": new_image},
        )

    def test_success_full(self):
        new_image = "{0}:new".format(self.image)

        self.config.env.push_cib(
            replace={
                ".//resources/bundle": """
                    <bundle id="{bundle_id}">
                        <{container_type}
                            image="{image}"
                            promoted-max="1"
                            replicas="2"
                            replicas-per-host="3"
                        />
                        <network
                            control-port="54321"
                            host-interface="eth1"
                            host-netmask="16"
                            ip-range-start="192.168.100.1"
                        >
                            <port-mapping
                                id="{bundle_id}-port-map-3000"
                                internal-port="3002"
                                port="3000"
                            />
                            <port-mapping
                                id="{bundle_id}-port-map-4000-4400"
                                range="4000-4400"
                            />
                        </network>
                        <storage>
                            <storage-mapping
                                id="{bundle_id}-storage-map"
                                options="extra options 2"
                                source-dir="/tmp/{container_type}2aa"
                                target-dir="/tmp/{container_type}2bb"
                            />
                        </storage>
                        <meta_attributes id="{bundle_id}-meta_attributes">
                            <nvpair
                                id="{bundle_id}-meta_attributes-target-role"
                                name="target-role"
                                value="Started"
                            />
                        </meta_attributes>
                        {fixture_primitive}
                    </bundle>
                """.format(
                    container_type=self.container_type,
                    bundle_id=self.bundle_id,
                    fixture_primitive=self.fixture_primitive,
                    image=new_image,
                ),
            }
        )
        self.bundle_reset(
            container_options={
                "image": new_image,
                "promoted-max": "1",
                "replicas": "2",
                "replicas-per-host": "3",
            },
            network_options={
                "control-port": "54321",
                "host-interface": "eth1",
                "host-netmask": "16",
                "ip-range-start": "192.168.100.1",
            },
            port_map=[
                {"internal-port": "3002", "port": "3000"},
                {"range": "4000-4400"},
            ],
            storage_map=[
                {
                    "options": "extra options 2",
                    "source-dir": f"/tmp/{self.container_type}2aa",
                    "target-dir": f"/tmp/{self.container_type}2bb",
                },
            ],
            meta_attributes={
                "target-role": "Started",
            },
        )

    def test_success_keep_map_ids(self):
        self.config.env.push_cib(
            replace={
                ".//resources/bundle/network": f"""
                    <network
                        control-port="12345"
                        host-interface="eth0"
                        host-netmask="24"
                        ip-range-start="192.168.100.200"
                    >
                        <port-mapping
                            id="{self.bundle_id}-port-map-1001"
                            internal-port="3002"
                            port="3000"
                        />
                        <port-mapping
                            id="{self.bundle_id}-port-map-3000-3300"
                            range="4000-4400"
                        />
                    </network>
                """,
                ".//resources/bundle/storage": f"""
                    <storage>
                        <storage-mapping
                            id="{self.bundle_id}-storage-map"
                            options="extra options 2"
                            source-dir="/tmp/{self.container_type}2aa"
                            target-dir="/tmp/{self.container_type}2bb"
                        />
                    </storage>
                """,
            }
        )

        # Every value is kept as before except port_map and storage_map.
        self.bundle_reset(
            container_options={
                "image": self.image,
                "promoted-max": "0",
                "replicas": "1",
                "replicas-per-host": "1",
            },
            network_options={
                "control-port": "12345",
                "host-interface": "eth0",
                "host-netmask": "24",
                "ip-range-start": "192.168.100.200",
            },
            port_map=[
                {
                    "id": f"{self.bundle_id}-port-map-1001",
                    "internal-port": "3002",
                    "port": "3000",
                },
                {
                    "id": f"{self.bundle_id}-port-map-3000-3300",
                    "range": "4000-4400",
                },
            ],
            storage_map=[
                {
                    "id": f"{self.bundle_id}-storage-map",
                    "options": "extra options 2",
                    "source-dir": f"/tmp/{self.container_type}2aa",
                    "target-dir": f"/tmp/{self.container_type}2bb",
                },
            ],
            meta_attributes={
                "target-role": "Stopped",
            },
        )


class ResetParametrizedContainerMixin(BaseMixin, ParametrizedContainerMixin):
    pass


class MinimalPodman(MinimalMixin, TestCase):
    container_type = "podman"


class MinimalDocker(MinimalMixin, TestCase):
    container_type = "docker"


class FullPodman(FullMixin, TestCase):
    container_type = "podman"


class FullDocker(FullMixin, TestCase):
    container_type = "docker"


class ResetParametrizedPodman(ResetParametrizedContainerMixin, TestCase):
    container_type = "podman"


class ResetParametrizedDocker(ResetParametrizedContainerMixin, TestCase):
    container_type = "docker"


class ResetWithNetwork(BaseMixin, NetworkMixin, TestCase):
    container_type = "docker"


class ResetWithPortMap(BaseMixin, PortMapMixin, TestCase):
    container_type = "docker"


class ResetWithStorageMap(BaseMixin, StorageMapMixin, TestCase):
    container_type = "docker"


class ResetWithMetaMap(BaseMixin, MetaMixin, TestCase):
    container_type = "docker"

    def test_success(self):
        # When there is no meta attributes the new one are put on the first
        # position (since reset now uses update internally). This is the reason
        # for reimplementation of this MetaMixin test.
        self.config.env.push_cib(
            resources="""
                <resources>
                    <bundle id="{bundle_id}">
                        <meta_attributes id="{bundle_id}-meta_attributes">
                            <nvpair id="{bundle_id}-meta_attributes-is-managed"
                                name="is-managed" value="false" />
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
        self.run_bundle_cmd(
            meta_attributes={
                "target-role": "Stopped",
                "is-managed": "false",
            }
        )


class ResetWithAllOptions(BaseMixin, AllOptionsMixin, TestCase):
    container_type = "docker"


class ResetWithWait(BaseMixin, WaitMixin, TestCase):
    container_type = "docker"


class ResetUnknownContainerType(BaseMixin, SetUpMixin, TestCase):
    container_type = "unknown"

    def test_error_or_unknown_container(self):
        self.env_assist.assert_raise_library_error(
            lambda: bundle_reset(self.env_assist.get_env(), self.bundle_id)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.RESOURCE_BUNDLE_UNSUPPORTED_CONTAINER_TYPE,
                    bundle_id="B1",
                    supported_container_types=["docker", "podman"],
                    updating_options=True,
                ),
            ]
        )


class NoMetaIdRegenerationMixin(BaseMixin, SetUpMixin):
    @property
    def initial_resources(self):
        return """
            <resources>
                <bundle id="{bundle_id}">
                    <{container_type}
                        image="{image}"
                        promoted-max="0"
                        replicas="1"
                        replicas-per-host="1"
                    />
                    <meta_attributes id="CUSTOM_ID">
                        <nvpair
                            id="ANOTHER_ID-target-role"
                            name="target-role"
                            value="Stopped"
                        />
                    </meta_attributes>
                </bundle>
            </resources>
        """.format(
            container_type=self.container_type,
            bundle_id=self.bundle_id,
            image=self.image,
        )

    def test_dont_regenerate_meta_attributes_id(self):
        self.config.env.push_cib(
            replace={
                ".//resources/bundle/meta_attributes": """
                    <meta_attributes id="CUSTOM_ID">
                        <nvpair
                            id="CUSTOM_ID-target-role"
                            name="target-role"
                            value="Stopped"
                        />
                    </meta_attributes>
                """,
            }
        )
        self.bundle_reset(
            container_options={
                "image": self.image,
                "promoted-max": "0",
                "replicas": "1",
                "replicas-per-host": "1",
            },
            meta_attributes={
                "target-role": "Stopped",
            },
        )


class NoMetaIdRegenerationDocker(NoMetaIdRegenerationMixin, TestCase):
    container_type = "docker"


class NoMetaIdRegenerationPodman(NoMetaIdRegenerationMixin, TestCase):
    container_type = "podman"
