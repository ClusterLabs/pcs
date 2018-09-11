from lxml import etree
import shutil
from unittest import TestCase

from pcs.test.tools.assertions import AssertPcsMixin
from pcs.test.tools.cib import get_assert_pcs_effect_mixin
from pcs.test.tools.misc import (
    get_test_resource as rc,
    outdent,
    skip_unless_pacemaker_supports_bundle,
)
from pcs.test.tools.pcs_runner import PcsRunner


class BundleCreateCommon(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    )
):
    temp_cib = rc("temp-cib.xml")

    def setUp(self):
        shutil.copy(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)


@skip_unless_pacemaker_supports_bundle
class BundleCreateUpgradeCib(BundleCreateCommon):
    def setUp(self):
        self.pcs_runner = PcsRunner(self.temp_cib)

    def test_success(self):
        shutil.copy(rc("cib-empty-2.0.xml"), self.temp_cib)
        self.assert_effect(
            "resource bundle create B1 container docker image=pcs:test",
            """
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" />
                    </bundle>
                </resources>
            """,
            "CIB has been upgraded to the latest schema version.\n"
        )

    def test_upgrade_for_promoted_max(self):
        shutil.copy(rc("cib-empty-2.8.xml"), self.temp_cib)
        self.assert_effect(
            "resource bundle create B1 container docker image=pcs:test "
                "promoted-max=2"
            ,
            """
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" promoted-max="2" />
                    </bundle>
                </resources>
            """,
            "CIB has been upgraded to the latest schema version.\n"
        )


@skip_unless_pacemaker_supports_bundle
class BundleCreate(BundleCreateCommon):
    empty_cib = rc("cib-empty.xml")

    def test_minimal(self):
        self.assert_effect(
            "resource bundle create B1 container docker image=pcs:test",
            """
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" />
                    </bundle>
                </resources>
            """
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
            """,
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
            """
        )

    def test_deprecated_masters(self):
        self.assert_effect(
            """
                resource bundle create B1
                container docker image=pcs:test masters=0
            """,
            """
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" masters="0" />
                    </bundle>
                </resources>
            """,
            "Warning: container option 'masters' is deprecated and should not "
                "be used, use promoted-max instead\n"
        )

    def test_deprecated_masters_and_promoted_max(self):
        self.assert_pcs_fail(
            """
                resource bundle create B1
                container docker image=pcs:test masters=0 promoted-max=0
            """,
            "Error: Only one of container options 'masters' and 'promoted-max' "
                "can be used\n"
                "Warning: container option 'masters' is deprecated and should "
                "not be used, use promoted-max instead\n"
        )

    def test_fail_when_missing_args_1(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle",
            stdout_start="\nUsage: pcs resource bundle ...\n"
        )

    def test_fail_when_missing_args_2(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle create",
            stdout_start="\nUsage: pcs resource bundle create...\n"
        )

    def test_fail_when_missing_container_type(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle create B1",
            "Error: '' is not a valid container type value, use docker, podman, rkt\n"
        )

    def test_fail_when_missing_required(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle create B1 container docker",
            "Error: required container option 'image' is missing\n"
        )

    def test_fail_on_unknown_option(self):
        self.assert_pcs_fail(
            """
                resource bundle create B1 container docker image=pcs:test
                extra=option
            """,
            "Error: invalid container option 'extra', allowed options are: "
                "image, masters, network, options, promoted-max, replicas, "
                "replicas-per-host, run-command, use --force to override\n"
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
            """
            ,
            stdout_start="Error: Unable to update cib\n"
        )

    def test_more_errors(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle create B#1 container docker replicas=x",
            outdent(
                """\
                Error: invalid bundle name 'B#1', '#' is not a valid character for a bundle name
                Error: required container option 'image' is missing
                Error: 'x' is not a valid replicas value, use a positive integer
                """
            )
        )

    def assert_no_options(self, keyword):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle create B {0}".format(keyword),
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


@skip_unless_pacemaker_supports_bundle
class BundleUpdateUpgradeCib(BundleCreateCommon):
    def setUp(self):
        self.pcs_runner = PcsRunner(self.temp_cib)

    def test_upgrade_for_promoted_max(self):
        shutil.copy(rc("cib-empty-2.8.xml"), self.temp_cib)
        self.assert_pcs_success(
            "resource bundle create B container docker image=pcs:test"
        )
        self.assert_pcs_success(
            "resource bundle update B container promoted-max=3",
            "CIB has been upgraded to the latest schema version.\n"
        )

@skip_unless_pacemaker_supports_bundle
class BundleUpdate(BundleCreateCommon):
    empty_cib = rc("cib-empty.xml")

    def fixture_bundle(self, name):
        self.assert_pcs_success(
            "resource bundle create {0} container docker image=pcs:test".format(
                name
            )
        )

    def fixture_bundle_complex(self, name):
        self.assert_pcs_success(
            ("""
                resource bundle create {0}
                container docker image=pcs:test replicas=4 promoted-max=2
                network control-port=12345 host-interface=eth0 host-netmask=24
                port-map internal-port=1000 port=2000
                port-map internal-port=1001 port=2001
                port-map internal-port=1002 port=2002
                storage-map source-dir=/tmp/docker1a target-dir=/tmp/docker1b
                storage-map source-dir=/tmp/docker2a target-dir=/tmp/docker2b
                storage-map source-dir=/tmp/docker3a target-dir=/tmp/docker3b
                meta priority=15 resource-stickiness=100 is-managed=false
            """).format(name)
        )

    def test_fail_when_missing_args_1(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle update",
            stdout_start="\nUsage: pcs resource bundle update...\n"
        )

    def test_fail_when_missing_args_2(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle update B port-map",
            "Error: No port-map options specified\n"
        )

    def test_fail_when_missing_args_3(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle update B storage-map remove",
            "Error: When using 'storage-map' you must specify either 'add' and "
                "options or 'remove' and id(s)\n"
        )

    def test_bad_id(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle update B1 container image=test",
            "Error: bundle 'B1' does not exist\n"
        )

    def test_success(self):
        self.fixture_bundle_complex("B")
        self.assert_effect(
            """
                resource bundle update B
                container promoted-max= replicas=6 replicas-per-host=2
                network control-port= host-interface=eth1
                    ip-range-start=192.168.100.200
                port-map remove B-port-map-2000 B-port-map-2002
                port-map add internal-port=1003 port=2003
                storage-map remove B-storage-map B-storage-map-2
                storage-map add source-dir=/tmp/docker4a target-dir=/tmp/docker4b
                meta priority=10 is-managed= target-role=Stopped
            """,
            """
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
        )

    def test_deprecated_masters_set(self):
        # Setting both deprecated options and their new variants is tested in
        # self.test_options_errors. This shows deprecated options emit warning
        # even when not forced.
        self.fixture_bundle("B")
        self.assert_effect(
            "resource bundle update B container masters=2",
            """
                <resources>
                    <bundle id="B">
                        <docker image="pcs:test" masters="2" />
                    </bundle>
                </resources>
            """,
            "Warning: container option 'masters' is deprecated and should not "
                "be used, use promoted-max instead\n"
        )

    def test_delete_masters(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource bundle update B container masters=2",
            "Warning: container option 'masters' is deprecated and should not "
                "be used, use promoted-max instead\n"
        )
        self.assert_effect(
            "resource bundle update B container masters=",
            """
                <resources>
                    <bundle id="B">
                        <docker image="pcs:test" />
                    </bundle>
                </resources>
            """,
        )

    def test_delete_masters_and_promoted_max(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource bundle update B container masters= promoted-max=",
        )

    def test_masters_set_after_promoted_max(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource bundle update B container promoted-max=3",
        )
        self.assert_pcs_fail(
            "resource bundle update B container masters=2",
            "Error: Cannot set container option 'masters' because container "
                "option 'promoted-max' is already set\n"
                "Warning: container option 'masters' is deprecated and should "
                "not be used, use promoted-max instead\n"
        )

    def test_masters_set_after_promoted_max_with_remove(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource bundle update B container promoted-max=3",
        )
        self.assert_effect(
            "resource bundle update B container masters=2 promoted-max=",
            """
                <resources>
                    <bundle id="B">
                        <docker image="pcs:test" masters="2" />
                    </bundle>
                </resources>
            """,
            "Warning: container option 'masters' is deprecated and should not "
                "be used, use promoted-max instead\n"
        )

    def test_promoted_max_set_after_masters(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource bundle update B container masters=2",
            "Warning: container option 'masters' is deprecated and should not "
                "be used, use promoted-max instead\n"
        )
        self.assert_pcs_fail(
            "resource bundle update B container promoted-max=3",
            "Error: Cannot set container option 'promoted-max' because "
                "container option 'masters' is already set\n"
        )

    def test_promoted_max_set_after_masters_with_remove(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource bundle update B container masters=2",
            "Warning: container option 'masters' is deprecated and should not "
                "be used, use promoted-max instead\n"
        )
        self.assert_effect(
            "resource bundle update B container masters= promoted-max=3",
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
            "resource bundle update B container extra=option",
            "Error: invalid container option 'extra', allowed options are: "
                "image, masters, network, options, promoted-max, replicas, "
                "replicas-per-host, run-command, use --force to override\n"
        )
        # Test that pcs allows to specify options it does not know about. This
        # ensures some kind of forward compatibility, so the user will be able
        # to specify new options. However, as of now the option is not
        # supported by pacemaker and so the command fails.
        self.assert_pcs_fail(
            "resource bundle update B container extra=option --force",
            stdout_start="Error: Unable to update cib\n"
        )

        # no force needed when removing an unknown option
        self.assert_effect(
            "resource bundle update B container extra=",
            """
                <resources>
                    <bundle id="B">
                        <docker image="pcs:test" />
                    </bundle>
                </resources>
            """
        )

    def assert_no_options(self, keyword):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle update B {0}".format(keyword),
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


@skip_unless_pacemaker_supports_bundle
class BundleShow(TestCase, AssertPcsMixin):
    empty_cib = rc("cib-empty.xml")
    temp_cib = rc("temp-cib.xml")

    def setUp(self):
        shutil.copy(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)

    def test_minimal(self):
        self.assert_pcs_success(
            "resource bundle create B1 container docker image=pcs:test"
        )
        self.assert_pcs_success("resource show B1", outdent(
            """\
             Bundle: B1
              Docker: image=pcs:test
            """
        ))

    def test_container(self):
        self.assert_pcs_success(
            """
                resource bundle create B1
                container docker image=pcs:test promoted-max=2 replicas=4
                    options='a b c'
            """
        )
        self.assert_pcs_success("resource show B1", outdent(
            """\
             Bundle: B1
              Docker: image=pcs:test options="a b c" promoted-max=2 replicas=4
            """
        ))

    def test_network(self):
        self.assert_pcs_success(
            """
                resource bundle create B1
                container docker image=pcs:test
                network host-interface=eth0 host-netmask=24 control-port=12345
            """
        )
        self.assert_pcs_success("resource show B1", outdent(
            """\
             Bundle: B1
              Docker: image=pcs:test
              Network: control-port=12345 host-interface=eth0 host-netmask=24
            """
        ))

    def test_port_map(self):
        self.assert_pcs_success(
            """
                resource bundle create B1
                container docker image=pcs:test
                port-map id=B1-port-map-1001 internal-port=2002 port=2000
                port-map range=3000-3300
            """
        )
        self.assert_pcs_success("resource show B1", outdent(
            """\
             Bundle: B1
              Docker: image=pcs:test
              Port Mapping:
               internal-port=2002 port=2000 (B1-port-map-1001)
               range=3000-3300 (B1-port-map-3000-3300)
            """
        ))

    def test_storage_map(self):
        self.assert_pcs_success(
            """
                resource bundle create B1
                container docker image=pcs:test
                storage-map source-dir=/tmp/docker1a target-dir=/tmp/docker1b
                storage-map id=my-storage-map source-dir=/tmp/docker2a
                    target-dir=/tmp/docker2b
            """
        )
        self.assert_pcs_success("resource show B1", outdent(
            """\
             Bundle: B1
              Docker: image=pcs:test
              Storage Mapping:
               source-dir=/tmp/docker1a target-dir=/tmp/docker1b (B1-storage-map)
               source-dir=/tmp/docker2a target-dir=/tmp/docker2b (my-storage-map)
            """
        ))

    def test_meta(self):
        self.assert_pcs_success("""
            resource bundle create B1 container docker image=pcs:test
            --disabled
        """)
        self.assert_pcs_success("resource show B1", outdent(
            """\
             Bundle: B1
              Docker: image=pcs:test
              Meta Attrs: target-role=Stopped
            """
        ))

    def test_resource(self):
        self.assert_pcs_success(
            "resource bundle create B1 container docker image=pcs:test network "
            "control-port=1234"
        )
        self.assert_pcs_success(
            "resource create A ocf:pacemaker:Dummy bundle B1 --no-default-ops"
        )
        self.assert_pcs_success("resource show B1", outdent(
            """\
             Bundle: B1
              Docker: image=pcs:test
              Network: control-port=1234
              Resource: A (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10 timeout=20 (A-monitor-interval-10)
            """
        ))

    def test_all(self):
        self.assert_pcs_success(
            """
                resource bundle create B1
                container docker image=pcs:test promoted-max=2 replicas=4
                    options='a b c'
                network host-interface=eth0 host-netmask=24 control-port=12345
                port-map id=B1-port-map-1001 internal-port=2002 port=2000
                port-map range=3000-3300
                storage-map source-dir=/tmp/docker1a target-dir=/tmp/docker1b
                storage-map id=my-storage-map source-dir=/tmp/docker2a
                    target-dir=/tmp/docker2b
                meta target-role=Stopped is-managed=false
            """
        )
        self.assert_pcs_success(
            "resource create A ocf:pacemaker:Dummy bundle B1 --no-default-ops"
        )
        self.assert_pcs_success("resource show B1", outdent(
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
               Operations: monitor interval=10 timeout=20 (A-monitor-interval-10)
            """
        ))
