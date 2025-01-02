from unittest import TestCase

from pcs.common.tools import xml_fromstring


class XmlFromstring(TestCase):
    def test_large_xml(self):
        # pylint: disable=no-self-use
        # it raises on a huge xml without the flag huge_tree=True
        # see https://bugzilla.redhat.com/show_bug.cgi?id=1506864
        xml_fromstring(large_xml)


large_xml = """
<cib admin_epoch="1" epoch="1305" num_updates="0" validate-with="pacemaker-2.8">
      <configuration>
        <crm_config/>
        <nodes/>
        <resources>{0}</resources>
        <constraints/>
      </configuration>
  <status>{1}</status>
</cib>
""".format(
    "".join(
        [
            """
        <bundle id="scale{0}-bundle">
            <meta_attributes id="scale{0}-bundle-meta_attributes">
                <nvpair id="scale{0}-bundle-meta_attributes-target-role"
                    name="target-role" value="Stopped"
                />
            </meta_attributes>
            <docker run-command="/usr/sbin/pacemaker-remoted"
                image="user:remote"
                options="--user=root --log-driver=journald" replicas="20"
            />
            <network control-port="{0}"/>
            <storage>
                <storage-mapping target-dir="/dev/log"
                    id="dev-log-{0}" source-dir="/dev/log"
                />
            </storage>
        </bundle>
        """.format(i)
            for i in range(20000)
        ]
    ),
    "".join(
        [
            """
        <node_state id="{1}" uname="c09-h05-r630" in_ccm="true" crmd="online"
            crm-debug-origin="do_update_resource" join="member"
            expected="member"
        >
            <transient_attributes id="{1}">
                <instance_attributes id="status-{1}"/>
            </transient_attributes>
            <lrm id="1">
                <lrm_resources>{0}</lrm_resources>
            </lrm>
        </node_state>
        """.format(
                "".join(
                    [
                        """
            <lrm_resource id="scale13-bundle-{0}" type="remote" class="ocf"
                provider="pacemaker" container="scale13-bundle-docker-{0}"
            >
                <lrm_rsc_op id="scale13-bundle-{0}_last_0"
                    operation_key="scale13-bundle-{0}_start_0"
                    operation="start" crm-debug-origin="do_update_resource"
                    crm_feature_set="3.0.14"
                    transition-key="2957:15:0:2459ea96-7c1d-4276-9c21-828061199"
                    transition-magic="0:0;2957:15:0:2459ea96-7c1d-4276-9c21-828"
                    on_node="c09-h05-r630" call-id="2223" rc-code="0"
                    op-status="0" interval="0" last-run="1509318692"
                    last-rc-change="1509318692" exec-time="0" queue-time="0"
                    op-digest="802dc0edf5e736d13a41ac47626295eb"
                    op-force-restart=" reconnect_interval  port "
                    op-restart-digest="e38862dec2edf868edfcb2d64d77ff55"
                />
                <lrm_rsc_op id="scale13-bundle-{0}_monitor_60000"
                    operation_key="scale13-bundle-1{0}_monitor_60000"
                    operation="monitor" crm-debug-origin="do_update_resource"
                    crm_feature_set="3.0.14"
                    transition-key="2994:16:0:2459ea96-7c1d-4276-9c21-828061199"
                    transition-magic="0:0;2994:16:0:2459ea96-7c1d-4276-9c21-828"
                    on_node="c09-h05-r630" call-id="2264" rc-code="0"
                    op-status="0" interval="60000" last-rc-change="1509318915"
                    exec-time="0" queue-time="0"
                    op-digest="3b2ba04195253e454b50aa4a340af042"
                />
            </lrm_resource>
            """.format("{0}-{1}".format(i, j))
                        for j in range(98)
                    ]
                ),
                i,
            )
            for i in range(5)
        ]
    ),
)
