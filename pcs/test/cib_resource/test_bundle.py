from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree
import shutil

from pcs.test.tools.cib import get_assert_pcs_effect_mixin
from pcs.test.tools.pcs_unittest import TestCase
from pcs.test.tools.misc import (
    get_test_resource as rc,
    outdent,
    skip_unless_pacemaker_version,
)
from pcs.test.tools.pcs_runner import PcsRunner


skip_unless_resource_bundle_supported = skip_unless_pacemaker_version(
    (1, 1, 16),
    "bundle resources"
)

class BundleCreateCommon(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            etree.parse(cib).findall(".//resources")[0]
        )
    )
):
    temp_cib = rc("temp-cib.xml")

    def setUp(self):
        shutil.copy(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)


@skip_unless_resource_bundle_supported
class BundleCreateUpgradeCib(BundleCreateCommon):
    empty_cib = rc("cib-empty.xml")

    def test_success(self):
        self.assert_effect(
            "resource bundle create B1 container image=pcs:test",
            """
                <resources>
                    <bundle id="B1">
                        <docker image="pcs:test" />
                    </bundle>
                </resources>
            """,
            "CIB has been upgraded to the latest schema version.\n"
        )


@skip_unless_resource_bundle_supported
class BundleCreate(BundleCreateCommon):
    empty_cib = rc("cib-empty-2.8.xml")

    def test_minimal(self):
        self.assert_effect(
            "resource bundle create B1 container image=pcs:test",
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
                container replicas=4 replicas-per-host=2 run-command=/bin/true
                port-map port=1001
                network control-port=12345 host-interface=eth0 host-netmask=24
                port-map id=B1-port-map-1001 internal-port=2002 port=2000
                port-map range=3000-3300
                storage-map source-dir=/tmp/docker1a target-dir=/tmp/docker1b
                network ip-range-start=192.168.100.200
                storage-map id=B1-storage-map source-dir=/tmp/docker2a
                    target-dir=/tmp/docker2b
                container image=pcs:test masters=0
                storage-map source-dir-root=/tmp/docker3a
                    target-dir=/tmp/docker3b
                storage-map id=B1-port-map-1001-1 source-dir-root=/tmp/docker4a
                    target-dir=/tmp/docker4b
                container network=extra_network_settings options=extra_options
            """
            ,
            """
                <resources>
                    <bundle id="B1">
                        <docker
                            image="pcs:test"
                            masters="0"
                            network="extra_network_settings"
                            options="extra_options"
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
                    </bundle>
                </resources>
            """
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

    def test_fail_when_missing_required(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle create B1",
            "Error: required container option 'image' is missing\n"
        )

    def test_fail_on_unknown_option(self):
        self.assert_pcs_fail(
            "resource bundle create B1 container image=pcs:test extra=option",
            "Error: invalid container option 'extra', allowed options are: "
                "image, masters, network, options, replicas, replicas-per-host,"
                " run-command, use --force to override\n"
        )

    def test_unknown_option_forced(self):
        # Test that pcs allows to specify options it does not know about. This
        # ensures some kind of forward compatibility, so the user will be able
        # to specify new options. However, as of now the option is not
        # supported by pacemaker and so the command fails.
        self.assert_pcs_fail(
            """
                resource bundle create B1 container image=pcs:test extra=option
                --force
            """
            ,
            stdout_start="Error: Unable to update cib\n"
        )

    def test_more_errors(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource bundle create B#1 container replicas=x",
            outdent(
                """\
                Error: invalid bundle name 'B#1', '#' is not a valid character for a bundle name
                Error: required container option 'image' is missing
                Error: 'x' is not a valid replicas value, use a positive integer
                """
            )
        )
