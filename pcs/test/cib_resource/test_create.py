from __future__ import (
    absolute_import,
    division,
    print_function,
)

import re

from pcs.test.tools.misc import (
    get_test_resource as rc,
    skip_unless_pacemaker_supports_bundle,
    skip_unless_pacemaker_supports_systemd,
)
from pcs.test.cib_resource.common import ResourceTest


class Success(ResourceTest):
    def test_base_create(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy --no-default-ops",
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    @skip_unless_pacemaker_supports_systemd()
    def test_base_create_with_agent_name_including_systemd_instance(self):
        # crm_resource returns the same metadata for any systemd resource, no
        # matter if it exists or not
        self.assert_effect(
            "resource create R systemd:test@a:b --no-default-ops",
            """<resources>
                <primitive class="systemd" id="R" type="test@a:b">
                    <operations>
                        <op id="R-monitor-interval-60" interval="60"
                            name="monitor" timeout="100"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_base_create_with_default_ops(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy",
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-migrate_from-interval-0s" interval="0s"
                            name="migrate_from" timeout="20"
                        />
                        <op id="R-migrate_to-interval-0s" interval="0s"
                            name="migrate_to" timeout="20"
                        />
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                        <op id="R-reload-interval-0s" interval="0s"
                            name="reload" timeout="20"
                        />
                        <op id="R-start-interval-0s" interval="0s" name="start"
                            timeout="20"
                        />
                        <op id="R-stop-interval-0s" interval="0s" name="stop"
                            timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_create_with_options(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:heartbeat:IPaddr2"
                " ip=192.168.0.99 cidr_netmask=32"
            ,
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat"
                    type="IPaddr2"
                >
                    <instance_attributes id="R-instance_attributes">
                        <nvpair id="R-instance_attributes-cidr_netmask"
                            name="cidr_netmask" value="32"
                        />
                        <nvpair id="R-instance_attributes-ip" name="ip"
                            value="192.168.0.99"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_create_with_trace_options(self):
        # trace_ra and trace_file options are not defined in metadata but they
        # are allowed for all ocf:heartbeat and ocf:pacemaker agents. This test
        # checks it is possible to set them without --force.
        self.assert_effect(
            "resource create --no-default-ops R ocf:heartbeat:Dummy"
                " trace_ra=1 trace_file=/root/trace"
            ,
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat"
                    type="Dummy"
                >
                    <instance_attributes id="R-instance_attributes">
                        <nvpair id="R-instance_attributes-trace_file"
                            name="trace_file" value="/root/trace"
                        />
                        <nvpair id="R-instance_attributes-trace_ra"
                            name="trace_ra" value="1"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_create_with_options_and_operations(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:heartbeat:IPaddr2"
                " ip=192.168.0.99 cidr_netmask=32  op monitor interval=30s"
            ,
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat"
                    type="IPaddr2"
                >
                    <instance_attributes id="R-instance_attributes">
                        <nvpair id="R-instance_attributes-cidr_netmask"
                            name="cidr_netmask" value="32"
                        />
                        <nvpair id="R-instance_attributes-ip" name="ip"
                            value="192.168.0.99"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="R-monitor-interval-30s" interval="30s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_create_disabled(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy --no-default-ops --disabled",
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <meta_attributes id="R-meta_attributes">
                        <nvpair id="R-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_with_clone(self):
        self.assert_effect(
            [
                "resource create R ocf:heartbeat:Dummy --no-default-ops --clone"
                ,
                "resource create R ocf:heartbeat:Dummy --no-default-ops clone",
            ],
            """<resources>
                <clone id="R-clone">
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>
                </clone>
            </resources>"""
        )

    def test_with_clone_options(self):
        self.assert_effect(
            [
                "resource create R ocf:heartbeat:Dummy --no-default-ops"
                    " --cloneopt notify=true"
                ,
                "resource create R ocf:heartbeat:Dummy --no-default-ops clone"
                    " notify=true"
                ,
                "resource create R ocf:heartbeat:Dummy --no-default-ops --clone"
                    " notify=true"
                ,
            ],
            """<resources>
                <clone id="R-clone">
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="R-clone-meta_attributes">
                        <nvpair id="R-clone-meta_attributes-notify"
                            name="notify" value="true"
                        />
                    </meta_attributes>
                </clone>
            </resources>"""
        )

    def test_with_master(self):
        self.assert_effect(
            [
                "resource create R ocf:heartbeat:Dummy --no-default-ops --master",
                "resource create R ocf:heartbeat:Dummy --no-default-ops master",
            ],
            """<resources>
                <master id="R-master">
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>
                </master>
            </resources>"""
        )

    def test_create_with_options_and_meta(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:heartbeat:IPaddr2"
                " ip=192.168.0.99 cidr_netmask=32 meta is-managed=false"
            ,
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat"
                    type="IPaddr2"
                >
                    <instance_attributes id="R-instance_attributes">
                        <nvpair id="R-instance_attributes-cidr_netmask"
                            name="cidr_netmask" value="32"
                        />
                        <nvpair id="R-instance_attributes-ip" name="ip"
                            value="192.168.0.99"
                        />
                    </instance_attributes>
                    <meta_attributes id="R-meta_attributes">
                        <nvpair id="R-meta_attributes-is-managed"
                            name="is-managed" value="false"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

class SuccessOperations(ResourceTest):
    def test_create_with_operations(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:heartbeat:Dummy"
                " op monitor interval=30s"
            ,
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-30s" interval="30s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_multiple_op_keyword(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy --no-default-ops"
                " op monitor interval=30s op monitor interval=20s"
            ,
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-30s" interval="30s"
                            name="monitor"
                        />
                        <op id="R-monitor-interval-20s" interval="20s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_multiple_operations_same_op_keyword(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy --no-default-ops"
                " op monitor interval=30s monitor interval=20s"
            ,
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-30s" interval="30s"
                            name="monitor"
                        />
                        <op id="R-monitor-interval-20s" interval="20s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_multiple_op_options_for_same_action(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy --no-default-ops"
                " op monitor interval=30s timeout=20s"
            ,
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-30s" interval="30s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_op_with_OCF_CHECK_LEVEL(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy --no-default-ops"
                " op monitor interval=30s timeout=20s OCF_CHECK_LEVEL=1"
            ,
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-30s" interval="30s"
                            name="monitor" timeout="20s"
                        >
                            <instance_attributes
                                id="R-monitor-interval-30s-instance_attributes"
                            >
                                <nvpair
                                    id="R-monitor-interval-30s-"""
                                        +'instance_attributes-OCF_CHECK_LEVEL"'
                                        +"""
                                    name="OCF_CHECK_LEVEL" value="1"
                                />
                            </instance_attributes>
                        </op>
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_default_ops_only(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy",
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-migrate_from-interval-0s" interval="0s"
                            name="migrate_from" timeout="20"
                        />
                        <op id="R-migrate_to-interval-0s" interval="0s"
                            name="migrate_to" timeout="20"
                        />
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                        <op id="R-reload-interval-0s" interval="0s"
                            name="reload" timeout="20"
                        />
                        <op id="R-start-interval-0s" interval="0s" name="start"
                            timeout="20"
                        />
                        <op id="R-stop-interval-0s" interval="0s" name="stop"
                            timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_merging_default_ops_explictly_specified(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy op start timeout=200",
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-migrate_from-interval-0s" interval="0s"
                            name="migrate_from" timeout="20"
                        />
                        <op id="R-migrate_to-interval-0s" interval="0s"
                            name="migrate_to" timeout="20"
                        />
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                        <op id="R-reload-interval-0s" interval="0s"
                            name="reload" timeout="20"
                        />
                        <op id="R-start-interval-0s" interval="0s" name="start"
                            timeout="200"
                        />
                        <op id="R-stop-interval-0s" interval="0s" name="stop"
                            timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_completing_monitor_operation(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:heartbeat:Dummy",
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_adapt_second_op_interval(self):
        self.assert_effect(
            "resource create R ocf:pacemaker:Stateful",
            """<resources>
                <primitive class="ocf" id="R" provider="pacemaker"
                    type="Stateful"
                >
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" role="Master" timeout="20"
                        />
                        <op id="R-monitor-interval-11" interval="11"
                            name="monitor" role="Slave" timeout="20"
                        />
                        <op id="R-notify-interval-0s" interval="0s"
                            name="notify" timeout="5"
                        />
                        <op id="R-start-interval-0s" interval="0s" name="start"
                            timeout="20"
                        />
                        <op id="R-stop-interval-0s" interval="0s" name="stop"
                            timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>"""
            ,
            "Warning: changing a monitor operation interval from 10 to 11 to"
                " make the operation unique\n"
        )

    def test_warn_on_forced_unknown_operation(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:heartbeat:Dummy"
                " op monitro interval=30s --force"
            ,
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                        <op id="R-monitro-interval-30s" interval="30s"
                            name="monitro"
                        />
                    </operations>
                </primitive>
            </resources>"""
            ,
            "Warning: 'monitro' is not a valid operation name value, use"
                " meta-data, migrate_from, migrate_to, monitor, reload, start,"
                " stop, validate-all\n"
        )

    def test_op_id(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:heartbeat:Dummy"
                " op monitor interval=30s id=abcd"
            ,
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="abcd" interval="30s" name="monitor" />
                    </operations>
                </primitive>
            </resources>"""
        )

class SuccessGroup(ResourceTest):
    def test_with_group(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy --no-default-ops --group G",
            """<resources>
                <group id="G">
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>"""
        )

    def test_with_existing_group(self):
        self.assert_pcs_success(
            "resource create R0 ocf:heartbeat:Dummy --no-default-ops --group G"
        )
        self.assert_effect(
            [
                "resource create R ocf:heartbeat:Dummy --no-default-ops --group"
                    " G"
                ,
                "resource create R ocf:heartbeat:Dummy --no-default-ops --group"
                    " G --after R0"
                ,
            ],
            """<resources>
                <group id="G">
                    <primitive class="ocf" id="R0" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R0-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>"""
        )

    def test_with_group_with_after(self):
        self.assert_pcs_success_all([
            "resource create R0 ocf:heartbeat:Dummy --no-default-ops --group G",
            "resource create R1 ocf:heartbeat:Dummy --no-default-ops --group G",
        ])
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy --no-default-ops --group G"
                " --after R0"
            ,
            """<resources>
                <group id="G">
                    <primitive class="ocf" id="R0" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R0-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="R1" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R1-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>

                </group>
            </resources>"""
        )

    def test_with_group_with_before(self):
        self.assert_pcs_success(
            "resource create R0 ocf:heartbeat:Dummy --no-default-ops --group G"
        )
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy --no-default-ops --group G"
                " --before R0"
            ,
            """<resources>
                <group id="G">
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="R0" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R0-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>"""
        )

class SuccessMaster(ResourceTest):
    def test_disable_is_on_master_element(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy --no-default-ops --disabled --master",
            """<resources>
                <master id="R-master">
                    <meta_attributes id="R-master-meta_attributes">
                        <nvpair id="R-master-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>
                </master>
            </resources>"""
        )

    def test_put_options_after_master_as_its_meta_fix_1(self):
        """
        fixes bz 1378107 (do not use master options as primitive options)
        """
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy state=a"
                " --master is-managed=false --force"
            ,
            """<resources>
                <master id="R-master">
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <instance_attributes id="R-instance_attributes">
                            <nvpair id="R-instance_attributes-state"
                                name="state" value="a"
                            />
                        </instance_attributes>
                        <operations>
                            <op id="R-migrate_from-interval-0s" interval="0s"
                                name="migrate_from" timeout="20"
                            />
                            <op id="R-migrate_to-interval-0s" interval="0s"
                                name="migrate_to" timeout="20"
                            />
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                            <op id="R-reload-interval-0s" interval="0s"
                                name="reload" timeout="20"
                            />
                            <op id="R-start-interval-0s" interval="0s"
                                name="start" timeout="20"
                            />
                            <op id="R-stop-interval-0s" interval="0s"
                                name="stop" timeout="20"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="R-master-meta_attributes">
                        <nvpair id="R-master-meta_attributes-is-managed"
                            name="is-managed" value="false"
                    />
                    </meta_attributes>
                </master>
            </resources>"""
        )

    def test_put_options_after_master_as_its_meta_fix_2(self):
        """
        fixes bz 1378107 (do not use master options as operations)
        """
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy state=a op monitor"
                " interval=10s --master is-managed=false --force"
                " --no-default-ops"
            ,
            """<resources>
                <master id="R-master">
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <instance_attributes id="R-instance_attributes">
                            <nvpair id="R-instance_attributes-state"
                                name="state" value="a"
                            />
                        </instance_attributes>
                        <operations>
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="R-master-meta_attributes">
                        <nvpair id="R-master-meta_attributes-is-managed"
                            name="is-managed" value="false"
                    />
                    </meta_attributes>
                </master>
            </resources>"""
        )

    def test_do_not_steal_primitive_meta_options(self):
        """
        fixes bz 1378107
        """
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy meta a=b --master b=c"
                " --no-default-ops"
            ,
            """<resources>
                <master id="R-master">
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <meta_attributes id="R-meta_attributes">
                            <nvpair id="R-meta_attributes-a" name="a"
                                value="b"
                            />
                        </meta_attributes>
                        <operations>
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="R-master-meta_attributes">
                        <nvpair id="R-master-meta_attributes-b" name="b"
                            value="c"
                        />
                    </meta_attributes>
                </master>
            </resources>"""
        )

    def test_takes_master_meta_attributes(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:heartbeat:IPaddr2"
                " ip=192.168.0.99 --master cidr_netmask=32"
            ,
            """<resources>
                <master id="R-master">
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="IPaddr2"
                    >
                        <instance_attributes id="R-instance_attributes">
                            <nvpair id="R-instance_attributes-ip" name="ip"
                                value="192.168.0.99"
                            />
                        </instance_attributes>
                        <operations>
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="R-master-meta_attributes">
                        <nvpair id="R-master-meta_attributes-cidr_netmask"
                            name="cidr_netmask" value="32"
                        />
                    </meta_attributes>
                </master>
            </resources>"""
        )

class SuccessClone(ResourceTest):
    def test_clone_does_not_overshadow_meta_options(self):
        self.assert_effect(
            [
                "resource create R ocf:heartbeat:Dummy meta a=b --clone c=d",
                "resource create R ocf:heartbeat:Dummy --clone c=d meta a=b",
            ],
            """<resources>
                <clone id="R-clone">
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <meta_attributes id="R-meta_attributes">
                            <nvpair id="R-meta_attributes-a" name="a"
                                value="b"
                            />
                        </meta_attributes>
                        <operations>
                            <op id="R-migrate_from-interval-0s" interval="0s"
                                name="migrate_from" timeout="20"
                            />
                            <op id="R-migrate_to-interval-0s" interval="0s"
                                name="migrate_to" timeout="20"
                            />
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                            <op id="R-reload-interval-0s" interval="0s"
                                name="reload" timeout="20"
                            />
                            <op id="R-start-interval-0s" interval="0s"
                                name="start" timeout="20"
                            />
                            <op id="R-stop-interval-0s" interval="0s"
                                name="stop" timeout="20"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="R-clone-meta_attributes">
                        <nvpair id="R-clone-meta_attributes-c" name="c"
                            value="d"
                        />
                    </meta_attributes>
                </clone>
            </resources>"""
        )

    def test_clone_does_not_overshadow_operations(self):
        self.assert_effect(
            [
                "resource create R ocf:heartbeat:Dummy op monitor interval=10"
                    " --clone c=d"
                ,
                "resource create R ocf:heartbeat:Dummy --clone c=d"
                    " op monitor interval=10"
                ,
            ],
            """<resources>
                <clone id="R-clone">
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-migrate_from-interval-0s" interval="0s"
                                name="migrate_from" timeout="20"
                            />
                            <op id="R-migrate_to-interval-0s" interval="0s"
                                name="migrate_to" timeout="20"
                            />
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor"
                            />
                            <op id="R-reload-interval-0s" interval="0s"
                                name="reload" timeout="20"
                            />
                            <op id="R-start-interval-0s" interval="0s"
                                name="start" timeout="20"
                            />
                            <op id="R-stop-interval-0s" interval="0s"
                                name="stop" timeout="20"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="R-clone-meta_attributes">
                        <nvpair id="R-clone-meta_attributes-c" name="c"
                            value="d"
                        />
                    </meta_attributes>
                </clone>
            </resources>"""
        )

    def test_clone_places_disabled_correctly(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy --clone --disabled",
            """<resources>
                <clone id="R-clone">
                    <meta_attributes id="R-clone-meta_attributes">
                        <nvpair id="R-clone-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-migrate_from-interval-0s" interval="0s"
                                name="migrate_from" timeout="20"
                            />
                            <op id="R-migrate_to-interval-0s" interval="0s"
                                name="migrate_to" timeout="20"
                            />
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                            <op id="R-reload-interval-0s" interval="0s"
                                name="reload" timeout="20"
                            />
                            <op id="R-start-interval-0s" interval="0s"
                                name="start" timeout="20"
                            />
                            <op id="R-stop-interval-0s" interval="0s"
                                name="stop" timeout="20"
                            />
                        </operations>
                    </primitive>
                </clone>
            </resources>"""
        )


@skip_unless_pacemaker_supports_bundle
class Bundle(ResourceTest):
    empty_cib = rc("cib-empty-2.8.xml")

    def fixture_primitive(self, name, bundle=None):
        if bundle:
            self.assert_pcs_success(
                "resource create {0} ocf:heartbeat:Dummy bundle {1}".format(
                    name, bundle
                )
            )
        else:
            self.assert_pcs_success(
                "resource create {0} ocf:heartbeat:Dummy".format(name)
            )

    def fixture_bundle(self, name):
        self.assert_pcs_success(
            (
                "resource bundle create {0} container docker image=pcs:test "
                "network control-port=1234"
            ).format(name)
        )

    def test_bundle_id_not_specified(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy --no-default-ops bundle"
            ,
            "Error: you have to specify exactly one bundle\n"
        )

    def test_bundle_id_is_not_bundle(self):
        self.fixture_primitive("R1")
        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy bundle R1",
            "Error: 'R1' is not a bundle\n"
        )

    def test_bundle_id_does_not_exist(self):
        self.assert_pcs_fail(
            "resource create R1 ocf:heartbeat:Dummy bundle B",
            "Error: bundle 'B' does not exist\n"
        )

    def test_primitive_already_in_bundle(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R1", bundle="B")
        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy --no-default-ops bundle B",
            (
                "Error: bundle 'B' already contains resource 'R1', a bundle "
                "may contain at most one resource\n"
            )
        )

    def test_success(self):
        self.fixture_bundle("B")
        self.assert_effect(
            "resource create R1 ocf:heartbeat:Dummy --no-default-ops bundle B",
            """
                <resources>
                    <bundle id="B">
                        <docker image="pcs:test" />
                        <network control-port="1234"/>
                        <primitive class="ocf" id="R1" provider="heartbeat"
                            type="Dummy"
                        >
                            <operations>
                                <op id="R1-monitor-interval-10" interval="10"
                                    name="monitor" timeout="20"
                                />
                            </operations>
                        </primitive>
                    </bundle>
                </resources>
            """
        )


class FailOrWarn(ResourceTest):
    def test_error_group_clone_combination(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy --no-default-ops --clone"
                " --group G"
            ,
            "Error: you can specify only one of clone, master, bundle or"
                " --group\n"
        )

    def test_error_master_clone_combination(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy --no-default-ops --clone"
                " --master"
            ,
            "Error: you can specify only one of clone, master, bundle or"
                " --group\n"
        )

    def test_error_master_group_combination(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy --no-default-ops --master"
                " --group G"
            ,
            "Error: you can specify only one of clone, master, bundle or"
                " --group\n"
        )

    def test_error_bundle_clone_combination(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy --no-default-ops --clone"
                " bundle bundle_id"
            ,
            "Error: you can specify only one of clone, master, bundle or"
                " --group\n"
        )

    def test_error_bundle_master_combination(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy --no-default-ops --master"
                " bundle bundle_id"
            ,
            "Error: you can specify only one of clone, master, bundle or"
                " --group\n"
        )

    def test_error_bundle_group_combination(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy --no-default-ops --group G"
                " bundle bundle_id"
            ,
            "Error: you can specify only one of clone, master, bundle or"
                " --group\n"
        )

    def test_fail_when_nonexisting_agent(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:NoExisting",
            # pacemaker 1.1.18 changes -5 to Input/output error
            stdout_regexp=re.compile("^"
                "Error: Agent 'ocf:heartbeat:NoExisting' is not installed or "
                "does not provide valid metadata: Metadata query for "
                "ocf:heartbeat:NoExisting failed: (-5|Input/output error), use "
                "--force to override\n"
                "$", re.MULTILINE
            )
        )

    def test_warn_when_forcing_noexistent_agent(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:NoExisting --force",
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat"
                    type="NoExisting"
                >
                    <operations>
                        <op id="R-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
            # pacemaker 1.1.18 changes -5 to Input/output error
            output_regexp=re.compile("^"
                "Warning: Agent 'ocf:heartbeat:NoExisting' is not installed or "
                    "does not provide valid metadata: Metadata query for "
                    "ocf:heartbeat:NoExisting failed: (-5|Input/output error)\n"
                "$", re.MULTILINE
            )
        )


    def test_fail_on_invalid_resource_agent_name(self):
        self.assert_pcs_fail(
            "resource create R invalid_agent_name",
            "Error: Unable to find agent 'invalid_agent_name', try specifying"
                " its full name\n"
        )

    def test_fail_on_invalid_resource_agent_name_even_if_forced(self):
        self.assert_pcs_fail(
            "resource create R invalid_agent_name --force",
            "Error: Unable to find agent 'invalid_agent_name', try specifying"
                " its full name\n"
        )

    def test_fail_when_invalid_agent(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat: --force",
            "Error: Invalid resource agent name 'ocf:heartbeat:'. Use"
                " standard:provider:type when standard is 'ocf' or"
                " standard:type otherwise. List of standards and providers can"
                " be obtained by using commands 'pcs resource standards' and"
                " 'pcs resource providers'\n"
        )

    def test_vail_when_agent_class_is_not_allowed(self):
        self.assert_pcs_fail(
            "resource create R invalid:Dummy --force",
            "Error: Invalid resource agent name 'invalid:Dummy'. Use"
                " standard:provider:type when standard is 'ocf' or"
                " standard:type otherwise. List of standards and providers can"
                " be obtained by using commands 'pcs resource standards' and"
                " 'pcs resource providers'\n"
        )

    def test_fail_when_missing_provider_with_ocf_resource_agent(self):
        self.assert_pcs_fail(
            "resource create R ocf:Dummy",
            "Error: Invalid resource agent name 'ocf:Dummy'. Use"
                " standard:provider:type when standard is 'ocf' or"
                " standard:type otherwise. List of standards and providers can"
                " be obtained by using commands 'pcs resource standards' and"
                " 'pcs resource providers'\n"
        )

    def test_fail_when_provider_appear_with_non_ocf_resource_agent(self):
        self.assert_pcs_fail(
            "resource create R lsb:provider:Dummy --force",
            "Error: Invalid resource agent name 'lsb:provider:Dummy'. Use"
                " standard:provider:type when standard is 'ocf' or"
                " standard:type otherwise. List of standards and providers can"
                " be obtained by using commands 'pcs resource standards' and"
                " 'pcs resource providers'\n"
        )

    def test_print_info_about_agent_completion(self):
        self.assert_pcs_success(
            "resource create R delay",
            "Assumed agent name 'ocf:heartbeat:Delay' (deduced from 'delay')\n"
        )

    def test_fail_for_unambiguous_agent(self):
        self.assert_pcs_fail(
            "resource create R Dummy",
            "Error: Multiple agents match 'Dummy', please specify full name:"
                " ocf:heartbeat:Dummy, ocf:pacemaker:Dummy\n"
        )

    def test_for_options_not_matching_resource_agent(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy a=b c=d",
            "Error: invalid resource options: 'a', 'c', allowed options are: "
                "fake, state, trace_file, trace_ra, use --force to override\n"
        )

    def test_for_missing_options_of_resource_agent(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops R IPaddr2",
            "Error: required resource option 'ip' is missing,"
                " use --force to override\n"
                "Assumed agent name 'ocf:heartbeat:IPaddr2' (deduced from"
                " 'IPaddr2')\n"
        )

    def test_fail_on_invalid_resource_id(self):
        self.assert_pcs_fail(
            "resource create #R ocf:heartbeat:Dummy",
            "Error: invalid resource name '#R',"
                " '#' is not a valid first character for a resource name\n"
        )

    def test_fail_on_existing_resource_id(self):
        self.assert_pcs_success("resource create R ocf:heartbeat:Dummy")
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy",
            "Error: 'R' already exists\n"
        )

    def test_fail_on_invalid_operation_id(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy op monitor interval=30 id=#O",
            "Error: invalid operation id '#O',"
                " '#' is not a valid first character for a operation id\n"
        )

    def test_fail_on_existing_operation_id(self):
        self.assert_pcs_success("resource create R ocf:heartbeat:Dummy")
        self.assert_pcs_fail(
            "resource create S ocf:heartbeat:Dummy op monitor interval=30 id=R",
            "Error: 'R' already exists\n"
        )

    def test_fail_on_duplicate_operation_id(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy"
                " op monitor interval=30 id=O"
                " op monitor interval=60 id=O"
            ,
            "Error: 'O' already exists\n"
        )

    def test_fail_on_resource_id_same_as_operation_id(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy op monitor interval=30 id=R",
            "Error: 'R' already exists\n"
        )

    def test_fail_on_unknown_operation(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy op monitro interval=100",
            "Error: 'monitro' is not a valid operation name value, use"
                " meta-data, migrate_from, migrate_to, monitor, reload, start,"
                " stop, validate-all, use --force to override\n"
        )

    def test_fail_on_ambiguous_value_of_option(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy op monitor timeout=10"
                " timeout=20"
            ,
            "Error: duplicate option 'timeout' with different values '10' and"
                " '20'\n"
        )

class FailOrWarnOp(ResourceTest):
    def test_fail_empty(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops R ocf:heartbeat:Dummy"
                " op meta is-managed=false"
            ,
            "Error: When using 'op' you must specify an operation name and at"
                " least one option\n"
        )

    def test_fail_only_name_without_any_option(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops R ocf:heartbeat:Dummy"
                " op monitor meta is-managed=false"
            ,
            "Error: When using 'op' you must specify an operation name and at"
                " least one option\n"
        )

    def test_fail_duplicit(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops R ocf:heartbeat:Dummy op"
                " monitor interval=1h monitor interval=3600sec"
                " monitor interval=1min monitor interval=60s"
            ,
            [
                "Error: multiple specification of the same operation with the"
                    " same interval:"
                ,
                "monitor with intervals 1h, 3600sec",
                "monitor with intervals 1min, 60s",
            ]
        )

    def test_fail_invalid_first_action(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops R ocf:heartbeat:Dummy op"
                " mo=nitor interval=1min"
            ,
            "Error: When using 'op' you must specify an operation name after"
                " 'op'\n"
            ,
        )

    def test_fail_invalid_option(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops R ocf:heartbeat:Dummy op"
                " monitor interval=1min moni=tor timeout=80s"
            ,
            "Error: invalid resource operation option 'moni', allowed options"
                " are: OCF_CHECK_LEVEL, description, enabled, id, interval,"
                " interval-origin, name, on-fail, record-pending, requires,"
                " role, start-delay, timeout\n"
        )

    def test_fail_on_invalid_role(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops R ocf:heartbeat:Dummy op"
                " monitor role=abc"
            ,
            "Error: 'abc' is not a valid role value, use Master, Slave,"
                " Started, Stopped\n"
        )

    def test_force_invalid_role(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops R ocf:heartbeat:Dummy op"
                " monitor role=abc --force"
            ,
            "Error: 'abc' is not a valid role value, use Master, Slave,"
                " Started, Stopped\n"
        )

    def test_fail_on_invalid_requires(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource create --no-default-ops R ocf:heartbeat:Dummy op"
                " monitor requires=Abc"
            ,
            "Error: 'Abc' is not a valid requires value, use fencing, nothing,"
                " quorum, unfencing\n"
        )

    def test_fail_on_invalid_on_fail(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource create --no-default-ops R ocf:heartbeat:Dummy op"
                " monitor on-fail=Abc"
            ,
            "Error: 'Abc' is not a valid on-fail value, use block, fence,"
                " ignore, restart, restart-container, standby, stop\n"
        )

    def test_fail_on_invalid_record_pending(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource create --no-default-ops R ocf:heartbeat:Dummy op"
                " monitor record-pending=Abc"
            ,
            "Error: 'Abc' is not a valid record-pending value, use 0, 1, false,"
                " true\n"
        )

    def test_fail_on_invalid_enabled(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource create --no-default-ops R ocf:heartbeat:Dummy op"
                " monitor enabled=Abc"
            ,
            "Error: 'Abc' is not a valid enabled value, use 0, 1, false, true\n"
        )

    def test_fail_on_combination_of_start_delay_and_interval_origin(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource create --no-default-ops R ocf:heartbeat:Dummy op"
                " monitor start-delay=10 interval-origin=20"
            ,
            "Error: Only one of resource operation options 'interval-origin'"
                " and 'start-delay' can be used\n"
        )

class FailOrWarnGroup(ResourceTest):
    def test_fail_when_invalid_group(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy --group 1",
            "Error: invalid group name '1', '1' is not a valid first character"
                " for a group name\n"
        )

    def test_fail_when_try_use_id_of_another_element(self):
        self.assert_effect(
            "resource create R1 ocf:heartbeat:Dummy --no-default-ops meta a=b",
            """<resources>
                <primitive class="ocf" id="R1" provider="heartbeat"
                    type="Dummy"
                >
                    <meta_attributes id="R1-meta_attributes">
                        <nvpair id="R1-meta_attributes-a" name="a" value="b"/>
                    </meta_attributes>
                    <operations>
                        <op id="R1-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )
        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy --group R1-meta_attributes",
            "Error: 'R1-meta_attributes' is not a group\n"
        )


    def test_fail_when_entered_both_after_and_before(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy --group G --after S1 --before S2",
            "Error: you cannot specify both --before and --after\n"
        )

    def test_fail_when_after_is_used_without_group(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy --after S1",
            "Error: you cannot use --after without --group\n"
        )

    def test_fail_when_before_is_used_without_group(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy --before S1",
            "Error: you cannot use --before without --group\n"
        )

    def test_fail_when_before_after_conflicts_and_moreover_without_group(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy --after S1 --before S2",
            "Error: you cannot specify both --before and --after"
                " and you have to specify --group\n"
        )

    def test_fail_when_before_does_not_exist(self):
        self.assert_pcs_success(
            "resource create R0 ocf:heartbeat:Dummy --group G1 "
        )
        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy --group G1 --before R1",
            "Error: there is no resource 'R1' in the group 'G1'\n"
        )

    def test_fail_when_use_before_with_new_group(self):
        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy --group G1 --before R1",
            "Error: there is no resource 'R1' in the group 'G1'\n"
        )

    def test_fail_when_after_does_not_exist(self):
        self.assert_pcs_success(
            "resource create R0 ocf:heartbeat:Dummy --group G1 "
        )
        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy --group G1 --after R1",
            "Error: there is no resource 'R1' in the group 'G1'\n"
        )

    def test_fail_when_use_after_with_new_group(self):
        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy --group G1 --after R1",
            "Error: there is no resource 'R1' in the group 'G1'\n"
        )

    def test_fail_when_on_pacemaker_remote_attempt(self):
        self.assert_pcs_fail(
            "resource create R2 ocf:pacemaker:remote",
            "Error: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'"
                ", use --force to override\n"
        )

    def test_warn_when_on_pacemaker_remote_attempt(self):
        self.assert_pcs_success(
            "resource create R2 ocf:pacemaker:remote --force",
            "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
        )

    def test_fail_when_on_pacemaker_remote_conflict_with_existing_node(self):
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote --force",
            "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
        )

        self.assert_pcs_fail(
            "resource create R2 ocf:pacemaker:remote server=R --force",
            "Error: 'R' already exists\n"
                "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
        )

    def test_fail_when_on_pacemaker_remote_conflict_with_existing_id(self):
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote server=R2 --force",
            "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
        )

        self.assert_pcs_fail(
            "resource create R2 ocf:pacemaker:remote --force",
            "Error: 'R2' already exists\n"
                "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
        )

    def test_fail_when_on_guest_conflict_with_existing_node(self):
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote --force",
            "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
        )

        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy meta remote-node=R --force",
            "Error: 'R' already exists\n"
                "Warning: this command is not sufficient for creating a guest node"
                ", use 'pcs cluster node add-guest'\n"
        )

    def test_fail_when_on_guest_conflict_with_existing_node_host(self):
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote server=HOST --force",
            "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
        )

        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy meta remote-node=HOST"
                " --force"
            ,
            "Error: 'HOST' already exists\n"
                "Warning: this command is not sufficient for creating a guest node"
                ", use 'pcs cluster node add-guest'\n"
        )

    def test_fail_when_on_guest_conflict_with_existing_node_host_addr(self):
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote server=HOST --force",
            "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
        )

        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy meta remote-node=A"
                " remote-addr=HOST --force"
            ,
            "Error: 'HOST' already exists\n"
                "Warning: this command is not sufficient for creating a guest node"
                ", use 'pcs cluster node add-guest'\n"
        )

    def test_not_fail_when_on_guest_when_conflict_host_with_name(self):
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote server=HOST --force",
            "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
        )

        self.assert_pcs_success(
            "resource create R2 ocf:heartbeat:Dummy meta remote-node=HOST"
                " remote-addr=R --force"
            ,
            "Warning: this command is not sufficient for creating a guest node, use"
                " 'pcs cluster node add-guest'\n"
        )

    def test_fail_when_on_pacemaker_remote_guest_attempt(self):
        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy meta remote-node=HOST",
            "Error: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest', use --force to override\n"
        )

    def test_warn_when_on_pacemaker_remote_guest_attempt(self):
        self.assert_pcs_success(
            "resource create R2 ocf:heartbeat:Dummy meta remote-node=HOST"
                " --force"
            ,
            "Warning: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest'\n"
        )
