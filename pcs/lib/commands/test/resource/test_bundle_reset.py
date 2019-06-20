from unittest import TestCase

from pcs.common import report_codes
from pcs.lib.commands.resource import bundle_reset
from pcs.lib.commands.test.resource.bundle_common import(
    FixturesMixin,
    SetUpMixin,
    UpgradeMixin,
    ParametrizedContainerMixin,
    NetworkMixin,
    PortMapMixin,
    StorageMapMixin,
    MetaMixin,
    AllOptionsMixin,
    WaitMixin,
)
from pcs.lib.errors import  ReportItemSeverity as severities

class BaseMixin(FixturesMixin):
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
            **params
        )

    def run_bundle_cmd(self, *args, **kwargs):
        self.bundle_reset(*args, **kwargs)

class Minimal(BaseMixin, SetUpMixin, TestCase):
    container_type = "docker"

    def test_success_zero_change(self):
        self.config.env.push_cib(resources=self.initial_resources)
        self.bundle_reset()

    def test_success_change(self):
        new_image = "{0}:new".format(self.image)

        self.config.env.push_cib(replace={
            ".//resources/bundle":
                """
                    <bundle id="{bundle_id}">
                        <{container_type} image="{image}" />
                    </bundle>
                """
                .format(
                    bundle_id=self.bundle_id,
                    container_type=self.container_type,
                    image=new_image,
                )
            ,
        })
        self.bundle_reset(
            container_options={"image": new_image},
        )

    def test_noexistent_id(self):
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
                    None
                ),
            ],
            expected_in_processor=False,
        )

class Full(BaseMixin, SetUpMixin, TestCase):
    container_type = "docker"
    fixture_primitive = """
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy"/>
    """

    @property
    def initial_resources(self):
        return """
            <resources>
                <bundle id="{bundle_id}">
                    <meta_attributes id="{bundle_id}-meta_attributes">
                        <nvpair id="{bundle_id}-meta_attributes-target-role"
                            name="target-role"
                            value="Stopped"
                        />
                    </meta_attributes>
                    <{container_type}
                        image="{image}"
                        replicas="0"
                        replicas-per-host="0"
                    />
                    <meta_attributes id="{bundle_id}-meta_attributes">
                        <nvpair
                            id="{bundle_id}-meta_attributes-is-managed"
                            name="is-managed"
                            value="false"
                        />
                    </meta_attributes>
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
        self.config.env.push_cib(replace={
            ".//resources/bundle":
                """
                    <bundle id="{bundle_id}">
                        <{container_type} image="{image}" />
                        <network/>
                        <storage/>
                        <meta_attributes id="{bundle_id}-meta_attributes"/>
                        {fixture_primitive}
                    </bundle>
                """
                .format(
                    container_type=self.container_type,
                    bundle_id=self.bundle_id,
                    fixture_primitive=self.fixture_primitive,
                    image=new_image,
                )
            ,
        })

        self.bundle_reset(
            container_options={"image": new_image},
        )

    def test_success_full(self):
        new_image = "{0}:new".format(self.image)

        self.config.env.push_cib(replace={
            ".//resources/bundle":
                """
                    <bundle id="{bundle_id}">
                        <{container_type}
                            image="{image}"
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
                            <nvpair id="{bundle_id}-meta_attributes-target-role"
                                name="target-role"
                                value="Started"
                            />
                        </meta_attributes>
                        {fixture_primitive}
                    </bundle>
                """
                .format(
                    container_type=self.container_type,
                    bundle_id=self.bundle_id,
                    fixture_primitive=self.fixture_primitive,
                    image=new_image,
                )
            ,
        })
        self.bundle_reset(
            container_options={
                "image": new_image,
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
                    "source-dir": "/tmp/{0}2aa".format(self.container_type),
                    "target-dir": "/tmp/{0}2bb".format(self.container_type),
                },
            ],
            meta_attributes={
                "target-role": "Started",
            }
        )
class Parametrized(
    BaseMixin, ParametrizedContainerMixin, UpgradeMixin, TestCase
):
    container_type = "docker"

class ResetWithNetwork(BaseMixin, NetworkMixin, TestCase):
    container_type = "docker"

class ResetWithPortMap(BaseMixin, PortMapMixin, TestCase):
    container_type = "docker"

class ResetWithStorageMap(BaseMixin, StorageMapMixin, TestCase):
    container_type = "docker"

class ResetWithMetaMap(BaseMixin, MetaMixin, TestCase):
    container_type = "docker"

class ResetWithAllOptions(BaseMixin, AllOptionsMixin, TestCase):
    container_type = "docker"

class ResetWithWait(BaseMixin, WaitMixin, TestCase):
    container_type = "docker"
