from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.cib_resource.common import ResourceTest


class Success(ResourceTest):
    def test_base_create(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy --no-default-ops",
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-60s" interval="60s"
                            name="monitor"
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
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
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
                        <op id="R-monitor-interval-60s" interval="60s"
                            name="monitor"
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
                        <op id="R-monitor-interval-60s" interval="60s"
                            name="monitor"
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
                            <op id="R-monitor-interval-60s" interval="60s"
                                name="monitor"
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
                            <op id="R-monitor-interval-60s" interval="60s"
                                name="monitor"
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
            "resource create R ocf:heartbeat:Dummy --no-default-ops --master",
            """<resources>
                <master id="R-master">
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                </master>
            </resources>"""
        )

    def test_with_master_options(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:heartbeat:IPaddr2"
                " ip=192.168.0.99 cidr_netmask=32 --master"
            ,
            """<resources>
                <master id="R-master">
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
                            <op id="R-monitor-interval-60s" interval="60s"
                                name="monitor"
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
                        <op id="R-monitor-interval-60s" interval="60s"
                            name="monitor"
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
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
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
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
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
                        <op id="R-monitor-interval-60s" interval="60s"
                            name="monitor"
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
                            <op id="R-monitor-interval-60s" interval="60s"
                                name="monitor"
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
                            <op id="R0-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-60s" interval="60s"
                                name="monitor"
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
                            <op id="R0-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="R1" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R1-monitor-interval-60s" interval="60s"
                                name="monitor"
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
                            <op id="R-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="R0" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R0-monitor-interval-60s" interval="60s"
                                name="monitor"
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
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="R-master-meta_attributes">
                        <nvpair id="R-master-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
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
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
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
                            <op id="R-monitor-interval-60s" interval="60s"
                                name="monitor"
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

    def test_master_flag_makes_do_not_steal_meta_when_ignored(self):
        """
        fixes bz 1378107
        """
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy meta a=b --clone"
                " --no-default-ops --master"
            ,
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
                            <op id="R-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                </clone>
            </resources>"""
            ,
            "Warning: --master ignored when creating a clone\n",
        )

    def test_master_flag_does_not_invalidate_flag_disabled(self):
        """
        fixes bz 1378107
        """
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy --clone --disable"
                " --master"
            ,
            """<resources>
                <clone id="R-clone">
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <meta_attributes id="R-meta_attributes">
                            <nvpair id="R-meta_attributes-target-role"
                                name="target-role" value="Stopped"
                            />
                        </meta_attributes>
                        <operations>
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
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
            ,
            "Warning: --master ignored when creating a clone\n",
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
                            <op id="R-monitor-interval-60s" interval="60s"
                                name="monitor"
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

    def test_not_steal_primitive_meta_attributes(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:heartbeat:IPaddr2"
                " ip=192.168.0.99 cidr_netmask=32 meta is-managed=false"
                " --master"
            ,
            """<resources>
                <master id="R-master">
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
                            <op id="R-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                </master>
            </resources>"""
        )

    def test_master_places_disabled_correctly(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:Dummy --master --disabled",
            """<resources>
                <master id="R-master">
                    <primitive class="ocf" id="R" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
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
                        <nvpair id="R-master-meta_attributes-target-role"
                            name="target-role" value="Stopped"
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
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
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
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor"
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

class FailOrWarn(ResourceTest):
    def test_warn_group_clone_combination(self):
        self.assert_pcs_success(
            "resource create R ocf:heartbeat:Dummy --no-default-ops --clone"
                " --group G"
            ,
            "Warning: --group ignored when creating a clone\n"
        )

    def test_warn_master_clone_combination(self):
        self.assert_pcs_success(
            "resource create R ocf:heartbeat:Dummy --no-default-ops --clone"
                " --master"
            ,
            "Warning: --master ignored when creating a clone\n"
        )

    def test_warn_master_group_combination(self):
        self.assert_pcs_success(
            "resource create R ocf:heartbeat:Dummy --no-default-ops --master"
                " --group G"
            ,
            "Warning: --group ignored when creating a master\n"
        )

    def test_fail_when_nonexisting_agent(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:NoExisting",
            "Error: Agent 'ocf:heartbeat:NoExisting' is not installed or does"
                " not provide valid metadata: Metadata query for"
                " ocf:heartbeat:NoExisting failed: -5\n"
        )

    def test_warn_when_forcing_noexistent_agent(self):
        self.assert_pcs_success(
            "resource create R ocf:heartbeat:NoExisting --force",
            "Warning: Agent 'ocf:heartbeat:NoExisting' is not installed or does"
            " not provide valid metadata: Metadata query for"
            " ocf:heartbeat:NoExisting failed: -5\n"
        )

    def test_fail_when_invalid_agent(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat: --force",
            "Error: Invalid resource agent name 'ocf:heartbeat:'. Use"
                " standard:provider:type or standard:type. List of standards"
                " and providers can be obtained by using commands 'pcs resource"
                " standards' and 'pcs resource providers'\n"
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
            "Error: invalid resource operation options: 'a', 'c',"
            " allowed options are: fake, state, use --force to override\n"
        )

    def test_for_missing_options_of_resource_agent(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops R IPaddr2",
            "Error: required resource operation option 'ip' is missing,"
                " use --force to override\n"
                "Assumed agent name 'ocf:heartbeat:IPaddr2' (deduced from"
                " 'IPaddr2')\n"
        )

    def test_fail_on_invalid_id(self):
        self.assert_pcs_fail(
            "resource create #R ocf:heartbeat:Dummy",
            "Error: invalid resource name '#R',"
                " '#' is not a valid first character for a resource name\n"
        )

    def test_fail_on_existing_id(self):
        self.assert_pcs_success("resource create R ocf:heartbeat:Dummy")
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy",
            "Error: 'R' already exists\n"
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

    def test_fail_duplicit(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops R ocf:heartbeat:Dummy op"
                " monitor interval=1h monitor interval=3600sec"
                " monitor interval=1min monitor interval=60s"
            ,
            [
                "Error: multiple specification the same operation with the same"
                    " interval:"
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
                " role, start-delay, timeout, use --force to override\n"
        )

    def test_fail_on_invalid_role(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops R ocf:heartbeat:Dummy op"
                " monitor role=abc"
            ,
            "Error: 'Abc' is not a valid role value, use Master, Slave,"
                " Started, Stopped, use --force to override\n"
        )

    def test_force_invalid_role(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops R ocf:heartbeat:Dummy op"
                " monitor role=abc --force"
            ,
            stdout_start="Error: Unable to update cib"
        )

class FailOrWarnGroup(ResourceTest):
    def test_fail_when_invalid_group(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy --group 1",
            "Error: invalid group name '1', '1' is not a valid first character"
                " for a group name\n"
        )

    def test_fail_when_group_id_in_use_as_primitive(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:Dummy --group R",
            "Error: 'R' is not a group\n"
        )

    def test_fail_when_group_id_in_use_as_existing_primitive(self):
        self.assert_pcs_success("resource create R1 ocf:heartbeat:Dummy")
        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy --group R1",
            "Error: 'R1' is not a group\n"
        )

    def test_fail_when_group_id_in_use_as_clone(self):
        self.assert_pcs_success(
            "resource create R1 ocf:heartbeat:Dummy --clone"
        )
        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy --group R1-clone",
            "Error: 'R1-clone' is not a group\n"
        )

    def test_fail_when_group_id_in_use_as_master(self):
        self.assert_pcs_success(
            "resource create R1 ocf:heartbeat:Dummy --master"
        )
        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy --group R1-master",
            "Error: 'R1-master' is not a group\n"
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
                        <op id="R1-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )
        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy --group R1-meta_attributes",
            "Error: 'R1-meta_attributes' is not a group\n"
        )


    def test_fail_when_specified_both_before_after(self):
        self.assert_pcs_fail(
            "resource create R2 ocf:heartbeat:Dummy --group G1"
                " --before R1 --after R1"
            ,
            "Error: you cannot specify both --before and --after\n"
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
