from unittest import TestCase
from lxml import etree

from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import (
    get_test_resource as rc,
    get_tmp_file,
    outdent,
    skip_unless_pacemaker_supports_bundle,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner

# pylint: disable=line-too-long
# pylint: disable=too-many-public-methods

ERRORS_HAVE_OCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)


class BundleCreateCommon(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    ),
):
    empty_cib = rc("cib-empty.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_bundle_create")
        write_file_to_tmpfile(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    def tearDown(self):
        self.temp_cib.close()


@skip_unless_pacemaker_supports_bundle()
class BundleCreateUpgradeCib(BundleCreateCommon):
    def test_success(self):
        write_file_to_tmpfile(rc("cib-empty-2.0.xml"), self.temp_cib)
        self.assert_effect(
            "resource bundle create B1 container docker image=pcs:test".split(),
            """
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" />
                    </bundle>
                </resources>
            """,
            "CIB has been upgraded to the latest schema version.\n",
        )

    def test_upgrade_for_promoted_max(self):
        write_file_to_tmpfile(rc("cib-empty-2.8.xml"), self.temp_cib)
        self.assert_effect(
            (
                "resource bundle create B1 container docker image=pcs:test "
                "promoted-max=2"
            ).split(),
            """
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" promoted-max="2" />
                    </bundle>
                </resources>
            """,
            "CIB has been upgraded to the latest schema version.\n",
        )


@skip_unless_pacemaker_supports_bundle()
class BundleReset(BundleCreateCommon):
    empty_cib = rc("cib-empty.xml")

    def test_minimal(self):
        self.assert_pcs_success(
            "resource bundle create B1 container docker image=pcs:test".split()
        )
        self.assert_pcs_success(
            "resource bundle create B2 container docker image=pcs:test".split()
        )
        self.assert_effect(
            "resource bundle reset B1 container image=pcs:new".split(),
            """
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:new" />
                    </bundle>
                    <bundle id="B2">
                        <docker image="pcs:test" />
                    </bundle>
                </resources>
            """,
        )


@skip_unless_pacemaker_supports_bundle()
class BundleCreate(BundleCreateCommon):
    empty_cib = rc("cib-empty.xml")

    def test_minimal(self):
        self.assert_effect(
            "resource bundle create B1 container docker image=pcs:test".split(),
            """
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" />
                    </bundle>
                </resources>
            """,
        )

    def test_all_options(self):
        self.assert_effect(
            """
                resource bundle create B1
                container docker replicas=4 replicas-per-host=2
                    run-command=/bin/true
                port-map port=1001
                meta target-role=Stopped
                network control-port=12345 host-interface=eth0 host-netmask=24
                port-map id=B1-port-map-1001 internal-port=2002 port=2000
                port-map range=3000-3300
                storage-map source-dir=/tmp/docker1a target-dir=/tmp/docker1b
                network ip-range-start=192.168.100.200
                storage-map id=B1-storage-map source-dir=/tmp/docker2a
                    target-dir=/tmp/docker2b
                container image=pcs:test promoted-max=0
                meta is-managed=false
                storage-map source-dir-root=/tmp/docker3a
                    target-dir=/tmp/docker3b
                storage-map id=B1-port-map-1001-1 source-dir-root=/tmp/docker4a
                    target-dir=/tmp/docker4b
                container network=extra_network_settings options=extra_options
            """.split(),
            """
                <resources>
                    <bundle id="B1">
                        <docker
                            image="pcs:test"
                            network="extra_network_settings"
                            options="extra_options"
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
                                source-dir-root="/tmp/docker4a"
                                target-dir="/tmp/docker4b"
                            />
                        </storage>
                        <meta_attributes id="B1-meta_attributes">
                            <nvpair
                                id="B1-meta_attributes-is-managed"
                                name="is-managed"
                                value="false"
                            />
                            <nvpair
                                id="B1-meta_attributes-target-role"
                                name="target-role"
                                value="Stopped"
                            />
                        </meta_attributes>
                    </bundle>
                </resources>
            """,
        )

    def test_deprecated_mains(self):
        self.assert_effect(
            """
                resource bundle create B1
                container docker image=pcs:test mains=0
            """.split(),
            """
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" mains="0" />
                    </bundle>
                </resources>
            """,
            "Warning: container option 'mains' is deprecated and should not "
            "be used, use 'promoted-max' instead\n",
        )

    def test_deprecated_mains_and_promoted_max(self):
        self.assert_pcs_fail(
            """
                resource bundle create B1
                container docker image=pcs:test mains=0 promoted-max=0
            """.split(),
            "Error: Only one of container options 'mains' and 'promoted-max' "
            "can be used\n"
            + ERRORS_HAVE_OCURRED
            + "Warning: container option 'mains' is deprecated and should "
            "not be used, use 'promoted-max' instead\n",
        )

    def test_fail_when_missing_args_1(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle".split(),
            stdout_start="\nUsage: pcs resource bundle...\n",
        )

    def test_fail_when_missing_args_2(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle create".split(),
            stdout_start="\nUsage: pcs resource bundle create...\n",
        )

    def test_fail_when_missing_container_type(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle create B1".split(),
            "Error: '' is not a valid container type value, use 'docker', "
            "'podman', 'rkt'\n" + ERRORS_HAVE_OCURRED,
        )

    def test_fail_when_missing_required(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle create B1 container docker".split(),
            "Error: required container option 'image' is missing\n"
            + ERRORS_HAVE_OCURRED,
        )

    def test_fail_on_unknown_option(self):
        self.assert_pcs_fail(
            """
                resource bundle create B1 container docker image=pcs:test
                extra=option
            """.split(),
            "Error: invalid container option 'extra', allowed options are: "
            "'image', 'mains', 'network', 'options', 'promoted-max', "
            "'replicas', 'replicas-per-host', 'run-command', use --force "
            "to override\n" + ERRORS_HAVE_OCURRED,
        )

    def test_unknown_option_forced(self):
        # Test that pcs allows to specify options it does not know about. This
        # ensures some kind of forward compatibility, so the user will be able
        # to specify new options. However, as of now the option is not
        # supported by pacemaker and so the command fails.
        self.assert_pcs_fail(
            """
                resource bundle create B1 container docker image=pcs:test
                extra=option --force
            """.split(),
            stdout_start="Error: Unable to update cib\n",
        )

    def test_more_errors(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle create B#1 container docker replicas=x".split(),
            outdent(
                """\
                Error: invalid bundle name 'B#1', '#' is not a valid character for a bundle name
                Error: required container option 'image' is missing
                Error: 'x' is not a valid replicas value, use a positive integer
                """
            )
            + ERRORS_HAVE_OCURRED,
        )

    def assert_no_options(self, keyword):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle create B".split() + [keyword],
            "Error: No {0} options specified\n".format(keyword),
        )

    def test_empty_container(self):
        self.assert_no_options("container")

    def test_empty_network(self):
        self.assert_no_options("network")

    def test_empty_storage_map(self):
        self.assert_no_options("storage-map")

    def test_empty_port_map(self):
        self.assert_no_options("port-map")

    def test_empty_meta(self):
        self.assert_no_options("meta")


@skip_unless_pacemaker_supports_bundle()
class BundleUpdateUpgradeCib(BundleCreateCommon):
    def test_upgrade_for_promoted_max(self):
        write_file_to_tmpfile(rc("cib-empty-2.8.xml"), self.temp_cib)
        self.assert_pcs_success(
            "resource bundle create B container docker image=pcs:test".split()
        )
        self.assert_pcs_success(
            "resource bundle update B container promoted-max=3".split(),
            "CIB has been upgraded to the latest schema version.\n",
        )


@skip_unless_pacemaker_supports_bundle()
class BundleUpdate(BundleCreateCommon):
    empty_cib = rc("cib-empty.xml")

    success_xml = """
        <resources>
            <bundle id="B">
                <docker
                    image="pcs:test"
                    replicas="6"
                    replicas-per-host="2"
                />
                <network
                    host-interface="eth1"
                    host-netmask="24"
                    ip-range-start="192.168.100.200"
                >
                    <port-mapping
                        id="B-port-map-2001"
                        internal-port="1001"
                        port="2001"
                    />
                    <port-mapping
                        id="B-port-map-2003"
                        internal-port="1003"
                        port="2003"
                    />
                </network>
                <storage>
                    <storage-mapping
                        id="B-storage-map-1"
                        source-dir="/tmp/docker2a"
                        target-dir="/tmp/docker2b"
                    />
                    <storage-mapping
                        id="B-storage-map"
                        source-dir="/tmp/docker4a"
                        target-dir="/tmp/docker4b"
                    />
                </storage>
                <meta_attributes id="B-meta_attributes">
                    <nvpair id="B-meta_attributes-priority"
                        name="priority" value="10" />
                    <nvpair id="B-meta_attributes-resource-stickiness"
                        name="resource-stickiness" value="100" />
                    <nvpair id="B-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </bundle>
        </resources>
    """

    @staticmethod
    def success_command(remove_command):
        return [
            "resource",
            "bundle",
            "update",
            "B",
            "container",
            "promoted-max=",
            "replicas=6",
            "replicas-per-host=2",
            "network",
            "control-port=",
            "host-interface=eth1",
            "ip-range-start=192.168.100.200",
            "port-map",
            remove_command,
            "B-port-map-2000",
            "B-port-map-2002",
            "port-map",
            "add",
            "internal-port=1003",
            "port=2003",
            "storage-map",
            remove_command,
            "B-storage-map",
            "B-storage-map-2",
            "storage-map",
            "add",
            "source-dir=/tmp/docker4a",
            "target-dir=/tmp/docker4b",
            "meta",
            "priority=10",
            "is-managed=",
            "target-role=Stopped",
        ]

    def fixture_bundle(self, name):
        self.assert_pcs_success(
            [
                "resource",
                "bundle",
                "create",
                name,
                "container",
                "docker",
                "image=pcs:test",
            ]
        )

    def fixture_bundle_complex(self, name):
        self.assert_pcs_success(
            [
                "resource",
                "bundle",
                "create",
                name,
                "container",
                "docker",
                "image=pcs:test",
                "replicas=4",
                "promoted-max=2",
                "network",
                "control-port=12345",
                "host-interface=eth0",
                "host-netmask=24",
                "port-map",
                "internal-port=1000",
                "port=2000",
                "port-map",
                "internal-port=1001",
                "port=2001",
                "port-map",
                "internal-port=1002",
                "port=2002",
                "storage-map",
                "source-dir=/tmp/docker1a",
                "target-dir=/tmp/docker1b",
                "storage-map",
                "source-dir=/tmp/docker2a",
                "target-dir=/tmp/docker2b",
                "storage-map",
                "source-dir=/tmp/docker3a",
                "target-dir=/tmp/docker3b",
                "meta",
                "priority=15",
                "resource-stickiness=100",
                "is-managed=false",
            ]
        )

    def test_fail_when_missing_args_1(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle update".split(),
            stdout_start="\nUsage: pcs resource bundle update...\n",
        )

    def test_fail_when_missing_args_2(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle update B port-map".split(),
            "Error: No port-map options specified\n",
        )

    def test_fail_when_missing_args_3(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle update B storage-map remove".split(),
            "Error: When using 'storage-map' you must specify either 'add' and "
            "options or either of 'delete' or 'remove' and id(s)\n",
        )

    def test_fail_when_missing_args_4(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle update B storage-map delete".split(),
            "Error: When using 'storage-map' you must specify either 'add' and "
            "options or either of 'delete' or 'remove' and id(s)\n",
        )

    def test_bad_id(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle update B1 container image=test".split(),
            "Error: bundle 'B1' does not exist\n",
        )

    def test_success_delete(self):
        self.fixture_bundle_complex("B")
        self.assert_effect(
            self.success_command(remove_command="delete"), self.success_xml,
        )

    def test_success_remove(self):
        self.fixture_bundle_complex("B")
        self.assert_effect(
            self.success_command(remove_command="remove"), self.success_xml,
        )

    def test_deprecated_mains_set(self):
        # Setting both deprecated options and their new variants is tested in
        # self.test_options_errors. This shows deprecated options emit warning
        # even when not forced.
        self.fixture_bundle("B")
        self.assert_effect(
            "resource bundle update B container mains=2".split(),
            """
                <resources>
                    <bundle id="B">
                        <docker image="pcs:test" mains="2" />
                    </bundle>
                </resources>
            """,
            "Warning: container option 'mains' is deprecated and should not "
            "be used, use 'promoted-max' instead\n",
        )

    def test_delete_mains(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource bundle update B container mains=2".split(),
            "Warning: container option 'mains' is deprecated and should not "
            "be used, use 'promoted-max' instead\n",
        )
        self.assert_effect(
            "resource bundle update B container mains=".split(),
            """
                <resources>
                    <bundle id="B">
                        <docker image="pcs:test" />
                    </bundle>
                </resources>
            """,
        )

    def test_delete_mains_and_promoted_max(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource bundle update B container mains= promoted-max=".split(),
        )

    def test_mains_set_after_promoted_max(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource bundle update B container promoted-max=3".split(),
        )
        self.assert_pcs_fail(
            "resource bundle update B container mains=2".split(),
            "Error: Cannot set container option 'mains' because container "
            "option 'promoted-max' is already set\n"
            + ERRORS_HAVE_OCURRED
            + "Warning: container option 'mains' is deprecated and should "
            "not be used, use 'promoted-max' instead\n",
        )

    def test_mains_set_after_promoted_max_with_remove(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource bundle update B container promoted-max=3".split(),
        )
        self.assert_effect(
            "resource bundle update B container mains=2 promoted-max=".split(),
            """
                <resources>
                    <bundle id="B">
                        <docker image="pcs:test" mains="2" />
                    </bundle>
                </resources>
            """,
            "Warning: container option 'mains' is deprecated and should not "
            "be used, use 'promoted-max' instead\n",
        )

    def test_promoted_max_set_after_mains(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource bundle update B container mains=2".split(),
            "Warning: container option 'mains' is deprecated and should not "
            "be used, use 'promoted-max' instead\n",
        )
        self.assert_pcs_fail(
            "resource bundle update B container promoted-max=3".split(),
            "Error: Cannot set container option 'promoted-max' because "
            "container option 'mains' is already set\n" + ERRORS_HAVE_OCURRED,
        )

    def test_promoted_max_set_after_mains_with_remove(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource bundle update B container mains=2".split(),
            "Warning: container option 'mains' is deprecated and should not "
            "be used, use 'promoted-max' instead\n",
        )
        self.assert_effect(
            "resource bundle update B container mains= promoted-max=3".split(),
            """
                <resources>
                    <bundle id="B">
                        <docker image="pcs:test" promoted-max="3" />
                    </bundle>
                </resources>
            """,
        )

    def test_force_unknown_option(self):
        self.fixture_bundle("B")

        self.assert_pcs_fail(
            "resource bundle update B container extra=option".split(),
            "Error: invalid container option 'extra', allowed options are: "
            "'image', 'mains', 'network', 'options', 'promoted-max', "
            "'replicas', 'replicas-per-host', 'run-command', use --force "
            "to override\n" + ERRORS_HAVE_OCURRED,
        )
        # Test that pcs allows to specify options it does not know about. This
        # ensures some kind of forward compatibility, so the user will be able
        # to specify new options. However, as of now the option is not
        # supported by pacemaker and so the command fails.
        self.assert_pcs_fail(
            "resource bundle update B container extra=option --force".split(),
            stdout_start="Error: Unable to update cib\n",
        )

        # no force needed when removing an unknown option
        self.assert_effect(
            "resource bundle update B container extra=".split(),
            """
                <resources>
                    <bundle id="B">
                        <docker image="pcs:test" />
                    </bundle>
                </resources>
            """,
        )

    def assert_no_options(self, keyword):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle update B".split() + [keyword],
            "Error: No {0} options specified\n".format(keyword),
        )

    def test_empty_container(self):
        self.assert_no_options("container")

    def test_empty_network(self):
        self.assert_no_options("network")

    def test_empty_storage_map(self):
        self.assert_no_options("storage-map")

    def test_empty_port_map(self):
        self.assert_no_options("port-map")

    def test_empty_meta(self):
        self.assert_no_options("meta")


@skip_unless_pacemaker_supports_bundle()
class BundleShow(TestCase, AssertPcsMixin):
    empty_cib = rc("cib-empty.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_bundle_show")
        write_file_to_tmpfile(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    def tearDown(self):
        self.temp_cib.close()

    def test_minimal(self):
        self.assert_pcs_success(
            "resource bundle create B1 container docker image=pcs:test".split()
        )
        self.assert_pcs_success(
            "resource config B1".split(),
            outdent(
                """\
             Bundle: B1
              Docker: image=pcs:test
            """
            ),
        )

    def test_container(self):
        self.assert_pcs_success(
            [
                "resource",
                "bundle",
                "create",
                "B1",
                "container",
                "docker",
                "image=pcs:test",
                "promoted-max=2",
                "replicas=4",
                "options=a b c",
            ]
        )
        self.assert_pcs_success(
            "resource config B1".split(),
            outdent(
                """\
             Bundle: B1
              Docker: image=pcs:test options="a b c" promoted-max=2 replicas=4
            """
            ),
        )

    def test_network(self):
        self.assert_pcs_success(
            """
                resource bundle create B1
                container docker image=pcs:test
                network host-interface=eth0 host-netmask=24 control-port=12345
            """.split()
        )
        self.assert_pcs_success(
            "resource config B1".split(),
            outdent(
                """\
             Bundle: B1
              Docker: image=pcs:test
              Network: control-port=12345 host-interface=eth0 host-netmask=24
            """
            ),
        )

    def test_port_map(self):
        self.assert_pcs_success(
            """
                resource bundle create B1
                container docker image=pcs:test
                port-map id=B1-port-map-1001 internal-port=2002 port=2000
                port-map range=3000-3300
            """.split()
        )
        self.assert_pcs_success(
            "resource config B1".split(),
            outdent(
                """\
             Bundle: B1
              Docker: image=pcs:test
              Port Mapping:
               internal-port=2002 port=2000 (B1-port-map-1001)
               range=3000-3300 (B1-port-map-3000-3300)
            """
            ),
        )

    def test_storage_map(self):
        self.assert_pcs_success(
            """
                resource bundle create B1
                container docker image=pcs:test
                storage-map source-dir=/tmp/docker1a target-dir=/tmp/docker1b
                storage-map id=my-storage-map source-dir=/tmp/docker2a
                    target-dir=/tmp/docker2b
            """.split()
        )
        self.assert_pcs_success(
            "resource config B1".split(),
            outdent(
                """\
             Bundle: B1
              Docker: image=pcs:test
              Storage Mapping:
               source-dir=/tmp/docker1a target-dir=/tmp/docker1b (B1-storage-map)
               source-dir=/tmp/docker2a target-dir=/tmp/docker2b (my-storage-map)
            """
            ),
        )

    def test_meta(self):
        self.assert_pcs_success(
            """
            resource bundle create B1 container docker image=pcs:test
            --disabled
            """.split()
        )
        self.assert_pcs_success(
            "resource config B1".split(),
            outdent(
                """\
             Bundle: B1
              Docker: image=pcs:test
              Meta Attrs: target-role=Stopped
            """
            ),
        )

    def test_resource(self):
        self.assert_pcs_success(
            (
                "resource bundle create B1 "
                "container docker image=pcs:test "
                "network control-port=1234"
            ).split()
        )
        self.assert_pcs_success(
            "resource create A ocf:pacemaker:Dummy bundle B1 --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource config B1".split(),
            outdent(
                """\
             Bundle: B1
              Docker: image=pcs:test
              Network: control-port=1234
              Resource: A (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10s timeout=20s (A-monitor-interval-10s)
            """
            ),
        )

    def test_all(self):
        self.assert_pcs_success(
            [
                "resource",
                "bundle",
                "create",
                "B1",
                "container",
                "docker",
                "image=pcs:test",
                "promoted-max=2",
                "replicas=4",
                "options=a b c",
                "network",
                "host-interface=eth0",
                "host-netmask=24",
                "control-port=12345",
                "port-map",
                "id=B1-port-map-1001",
                "internal-port=2002",
                "port=2000",
                "port-map",
                "range=3000-3300",
                "storage-map",
                "source-dir=/tmp/docker1a",
                "target-dir=/tmp/docker1b",
                "storage-map",
                "id=my-storage-map",
                "source-dir=/tmp/docker2a",
                "target-dir=/tmp/docker2b",
                "meta",
                "target-role=Stopped",
                "is-managed=false",
            ]
        )
        self.assert_pcs_success(
            "resource create A ocf:pacemaker:Dummy bundle B1 --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource config B1".split(),
            outdent(
                """\
             Bundle: B1
              Docker: image=pcs:test options="a b c" promoted-max=2 replicas=4
              Network: control-port=12345 host-interface=eth0 host-netmask=24
              Port Mapping:
               internal-port=2002 port=2000 (B1-port-map-1001)
               range=3000-3300 (B1-port-map-3000-3300)
              Storage Mapping:
               source-dir=/tmp/docker1a target-dir=/tmp/docker1b (B1-storage-map)
               source-dir=/tmp/docker2a target-dir=/tmp/docker2b (my-storage-map)
              Meta Attrs: is-managed=false target-role=Stopped
              Resource: A (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10s timeout=20s (A-monitor-interval-10s)
            """
            ),
        )
