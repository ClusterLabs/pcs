# pylint: disable=too-many-lines
import json
from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common import (
    communication,
    reports,
)
from pcs.common.interface import dto
from pcs.common.tools import timeout_to_seconds
from pcs.lib.commands import stonith

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.command_env.config_http_corosync import (
    corosync_running_check_response,
)
from pcs_test.tools.misc import get_test_resource as rc

from .cluster.common import (
    corosync_conf_fixture,
    get_two_node,
    node_fixture,
)

STONITH_ID_SCSI = "scsi-fence-device"
STONITH_ID_MPATH = "mpath-fence-device"
STONITH_TYPE_SCSI = "fence_scsi"
STONITH_TYPE_MPATH = "fence_mpath"
STONITH_TYPE_UNSUPPORTED = "fence_unsupported"
SCSI_NODE = "node1"
_DIGEST = "0" * 31
DEFAULT_DIGEST = _DIGEST + "0"
ALL_DIGEST = _DIGEST + "1"
NONPRIVATE_DIGEST = _DIGEST + "2"
NONRELOADABLE_DIGEST = _DIGEST + "3"
DIGEST_ATTR_VALUE_GOOD_FORMAT = f"stonith_id:stonith_type:{DEFAULT_DIGEST},"
DEV_1 = "/dev/sda"
DEV_2 = "/dev/sdb"
DEV_3 = "/dev/sdc"
DEV_4 = "/dev/sdd"
DEVICES_1 = ("/dev/sda",)
DEVICES_2 = ("/dev/sda", "/dev/sdb")
DEVICES_3 = ("/dev/sda", "/dev/sdb", "/dev/sdc")

DEFAULT_MONITOR = ("monitor", "60s", None, None)
DEFAULT_OPS = (DEFAULT_MONITOR,)
DEFAULT_LRM_START_OPS = (("0", DEFAULT_DIGEST, None, None),)
DEFAULT_LRM_MONITOR_OPS = (("60000", DEFAULT_DIGEST, None, None),)
DEFAULT_LRM_START_OPS_UPDATED = (("0", ALL_DIGEST, None, None),)
DEFAULT_LRM_MONITOR_OPS_UPDATED = (("60000", ALL_DIGEST, None, None),)
DEFAULT_PCMK_HOST_MAP = "node1:1;node2:2;node3:3"
DEFAULT_NODE_KEY_MAP = {"node1": "1", "node2": "2", "node3": "3"}


def _fixture_ops(resource_id, ops):
    return "\n".join(
        [
            (
                '<op id="{resource_id}-{name}-interval-{_interval}"'
                ' interval="{interval}" {timeout} name="{name}"/>'
            ).format(
                resource_id=resource_id,
                name=name,
                _interval=_interval if _interval else interval,
                interval=interval,
                timeout=f'timeout="{timeout}"' if timeout else "",
            )
            for name, interval, timeout, _interval in ops
        ]
    )


def _fixture_devices_nvpair(resource_id, devices):
    if devices is None:
        return ""
    return (
        '<nvpair id="{resource_id}-instance_attributes-devices" name="devices"'
        ' value="{devices}"/>'
    ).format(resource_id=resource_id, devices=",".join(sorted(devices)))


def fixture_scsi(
    stonith_id=STONITH_ID_SCSI,
    stonith_type=STONITH_TYPE_SCSI,
    devices=DEVICES_1,
    resource_ops=DEFAULT_OPS,
    host_map=DEFAULT_PCMK_HOST_MAP,
):
    return """
        <resources>
            <primitive class="stonith" id="{stonith_id}" type="{stonith_type}">
                <instance_attributes id="{stonith_id}-instance_attributes">
                    {devices}
                    <nvpair id="{stonith_id}-instance_attributes-pcmk_host_check" name="pcmk_host_check" value="static-list"/>
                    <nvpair id="{stonith_id}-instance_attributes-pcmk_host_list" name="pcmk_host_list" value="node1 node2 node3"/>
                    {host_map}
                    <nvpair id="{stonith_id}-instance_attributes-pcmk_reboot_action" name="pcmk_reboot_action" value="off"/>
                </instance_attributes>
                <meta_attributes id="{stonith_id}-meta_attributes">
                    <nvpair id="{stonith_id}-meta_attributes-provides" name="provides" value="unfencing"/>
                </meta_attributes>
                <operations>
                    {operations}
                </operations>
            </primitive>
            <primitive class="ocf" id="dummy" provider="pacemaker" type="Dummy"/>
        </resources>
    """.format(
        stonith_id=stonith_id,
        stonith_type=stonith_type,
        devices=_fixture_devices_nvpair(stonith_id, devices),
        operations=_fixture_ops(stonith_id, resource_ops),
        host_map=(
            (
                f'<nvpair id="{stonith_id}-instance_attributes-pcmk_host_map" '
                f'name="pcmk_host_map" value="{host_map}"/>'
            )
            if host_map is not None
            else ""
        ),
    )


def _fixture_lrm_rsc_ops(op_type, resource_id, lrm_ops):
    return [
        (
            '<lrm_rsc_op id="{resource_id}_{op_type_id}_{ms}" operation="{op_type}" '
            'interval="{ms}" {_all} {secure} {restart}/>'
        ).format(
            op_type_id="last" if op_type == "start" else op_type,
            op_type=op_type,
            resource_id=resource_id,
            ms=ms,
            _all=f'op-digest="{_all}"' if _all else "",
            secure=f'op-secure-digest="{secure}"' if secure else "",
            restart=f'op-restart-digest="{restart}"' if restart else "",
        )
        for ms, _all, secure, restart in lrm_ops
    ]


def _fixture_lrm_rsc_monitor_ops(resource_id, lrm_monitor_ops):
    return _fixture_lrm_rsc_ops("monitor", resource_id, lrm_monitor_ops)


def _fixture_lrm_rsc_start_ops(resource_id, lrm_start_ops):
    return _fixture_lrm_rsc_ops("start", resource_id, lrm_start_ops)


def _fixture_status_lrm_ops(resource_id, resource_type, lrm_ops):
    return f"""
        <lrm id="1">
            <lrm_resources>
                <lrm_resource id="{resource_id}" type="{resource_type}" class="stonith">
                    {lrm_ops}
                </lrm_resource>
            </lrm_resources>
        </lrm>
    """


def _fixture_digest_nvpair(node_id, digest_name, digest_value):
    return (
        f'<nvpair id="status-{node_id}-.{digest_name}" name="#{digest_name}" '
        f'value="{digest_value}"/>'
    )


def _fixture_transient_attributes(node_id, digests_nvpairs):
    return f"""
        <transient_attributes id="{node_id}">
            <instance_attributes id="status-{node_id}">
                <nvpair id="status-{node_id}-.feature-set" name="#feature-set" value="3.16.2"/>
                <nvpair id="status-{node_id}-.node-unfenced" name="#node-unfenced" value="1679319764"/>
                {digests_nvpairs}
            </instance_attributes>
        </transient_attributes>
    """


def _fixture_node_state(node_id, lrm_ops=None, transient_attrs=None):
    if transient_attrs is None:
        transient_attrs = ""
    if lrm_ops is None:
        lrm_ops = ""
    return f"""
        <node_state id="{node_id}" uname="node{node_id}">
            {lrm_ops}
            {transient_attrs}
        </node_state>
    """


def _fixture_status(
    resource_id,
    resource_type,
    lrm_start_ops=DEFAULT_LRM_START_OPS,
    lrm_monitor_ops=DEFAULT_LRM_MONITOR_OPS,
    digests_attrs_list=None,
):
    lrm_ops = _fixture_status_lrm_ops(
        resource_id,
        resource_type,
        "\n".join(
            _fixture_lrm_rsc_start_ops(resource_id, lrm_start_ops)
            + _fixture_lrm_rsc_monitor_ops(resource_id, lrm_monitor_ops)
        ),
    )
    node_states_list = []
    if not digests_attrs_list:
        node_states_list.append(
            _fixture_node_state("1", lrm_ops, transient_attrs=None)
        )
    else:
        for node_id, digests_attrs in enumerate(digests_attrs_list, start=1):
            transient_attrs = _fixture_transient_attributes(
                node_id,
                "\n".join(
                    _fixture_digest_nvpair(node_id, name, value)
                    for name, value in digests_attrs
                ),
            )
            node_state = _fixture_node_state(
                node_id,
                lrm_ops=lrm_ops if node_id == 1 else None,
                transient_attrs=transient_attrs,
            )
            node_states_list.append(node_state)
    node_states = "\n".join(node_states_list)
    return f"""
        <status>
            {node_states}
        </status>
    """


def fixture_digests_xml(resource_id, node_name, devices="", nonprivate=True):
    nonprivate_xml = (
        f"""
        <digest type="nonprivate" hash="{NONPRIVATE_DIGEST}">
            <parameters devices="{devices}"/>
        </digest>
        """
        if nonprivate
        else ""
    )

    return f"""
        <pacemaker-result api-version="2.9" request="crm_resource --digests --resource {resource_id} --node {node_name} --output-as xml devices={devices}">
            <digests resource="{resource_id}" node="{node_name}" task="stop" interval="0ms">
                <digest type="all" hash="{ALL_DIGEST}">
                    <parameters devices="{devices}" pcmk_host_check="static-list" pcmk_host_list="node1 node2 node3" pcmk_reboot_action="off"/>
                </digest>
                {nonprivate_xml}
            </digests>
            <status code="0" message="OK"/>
        </pacemaker-result>
    """


def fixture_crm_mon_res_running(
    resource_id, resource_agent, nodes_running_on=1
):
    role = "Started" if nodes_running_on else "Stopped"
    nodes = "\n".join(
        f'<node name="node{i}" id="{i}" cached="true"/>'
        for i in range(1, nodes_running_on + 1)
    )
    return f"""
        <resources>
            <resource id="{resource_id}" resource_agent="{resource_agent}"
                role="{role}" nodes_running_on="{nodes_running_on}">
                {nodes}
            </resource>
        </resources>
    """


FIXTURE_CRM_MON_NODES = """
    <nodes>
        <node name="node1" id="1" is_dc="true" resources_running="1"/>
        <node name="node2" id="2"/>
        <node name="node3" id="3"/>
    </nodes>
"""


FIXTURE_CRM_MON_RES_STOPPED = f"""
    <resource id="{STONITH_ID_SCSI}" resource_agent="stonith:fence_scsi" role="Stopped" nodes_running_on="0"/>
"""


class CommandSetMixin:
    def command(self, **kwargs):
        return lambda: stonith.update_scsi_devices(
            self.env_assist.get_env(),
            self.stonith_id,
            kwargs.get("devices_updated", DEVICES_2),
            force_flags=kwargs.get("force_flags", ()),
        )


class CommandAddRemoveMixin:
    def command(self, **kwargs):
        return lambda: stonith.update_scsi_devices_add_remove(
            self.env_assist.get_env(),
            self.stonith_id,
            kwargs.get("devices_add", [DEV_2]),
            kwargs.get("devices_remove", ()),
            force_flags=kwargs.get("force_flags", ()),
        )


class MpathMixin:
    command_url = "api/v1/scsi-unfence-node-mpath/v1"
    stonith_id = STONITH_ID_MPATH
    stonith_type = STONITH_TYPE_MPATH

    def unfence_config(
        self,
        original_devices=(),
        updated_devices=(),
        node_labels=None,
        communication_list=None,
    ):
        self.config.http.scsi.unfence_node_mpath(
            DEFAULT_NODE_KEY_MAP,
            original_devices=original_devices,
            updated_devices=updated_devices,
            node_labels=node_labels,
            communication_list=communication_list,
        )

    @staticmethod
    def get_raw_data(node):
        return dict(
            key=DEFAULT_NODE_KEY_MAP[node],
            original_devices=DEVICES_1,
            updated_devices=DEVICES_2,
        )


class ScsiMixin:
    command_url = "api/v1/scsi-unfence-node/v2"
    stonith_id = STONITH_ID_SCSI
    stonith_type = STONITH_TYPE_SCSI

    def unfence_config(
        self,
        original_devices=(),
        updated_devices=(),
        node_labels=None,
        communication_list=None,
    ):
        self.config.http.scsi.unfence_node(
            original_devices=original_devices,
            updated_devices=updated_devices,
            node_labels=node_labels,
            communication_list=communication_list,
        )

    @staticmethod
    def get_raw_data(node):
        return dict(
            node=node, original_devices=DEVICES_1, updated_devices=DEVICES_2
        )


class UpdateScsiDevicesMixin:
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

        self.existing_nodes = ["node1", "node2", "node3"]
        self.existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes)

    def config_cib(  # noqa: PLR0913
        self,
        *,
        devices_before=DEVICES_1,
        devices_updated=DEVICES_2,
        resource_ops=DEFAULT_OPS,
        lrm_monitor_ops=DEFAULT_LRM_MONITOR_OPS,
        lrm_start_ops=DEFAULT_LRM_START_OPS,
        host_map=DEFAULT_PCMK_HOST_MAP,
        nodes_running_on=1,
        start_digests=True,
        monitor_digests=True,
        digests_attrs_list=None,
        crm_digests_xml=None,
    ):
        # pylint: disable=too-many-arguments
        # pylint: disable=too-many-locals
        devices_value = ",".join(sorted(devices_updated))
        self.config.runner.cib.load(
            resources=fixture_scsi(
                stonith_id=self.stonith_id,
                stonith_type=self.stonith_type,
                devices=devices_before,
                resource_ops=resource_ops,
                host_map=host_map,
            ),
            status=_fixture_status(
                self.stonith_id,
                self.stonith_type,
                lrm_start_ops=lrm_start_ops,
                lrm_monitor_ops=lrm_monitor_ops,
                digests_attrs_list=digests_attrs_list,
            ),
        )
        self.config.runner.pcmk.is_resource_digests_supported()
        self.config.runner.pcmk.load_state(
            resources=fixture_crm_mon_res_running(
                self.stonith_id,
                f"stonith:{self.stonith_type}",
                nodes_running_on=nodes_running_on,
            ),
            nodes=FIXTURE_CRM_MON_NODES,
        )
        devices_opt = "devices={}".format(devices_value)

        if crm_digests_xml is None:
            crm_digests_xml = fixture_digests_xml(
                self.stonith_id, SCSI_NODE, devices=devices_value
            )
        if start_digests:
            self.config.runner.pcmk.resource_digests(
                self.stonith_id,
                SCSI_NODE,
                name="start.op.digests",
                stdout=crm_digests_xml,
                args=[devices_opt],
            )
        if monitor_digests:
            for num, op in enumerate(resource_ops, 1):
                name, interval, timeout, _ = op
                if name != "monitor":
                    continue
                args = [devices_opt]
                args.append(
                    "CRM_meta_interval={}".format(
                        1000 * timeout_to_seconds(interval)
                    )
                )
                if timeout:
                    args.append(
                        "CRM_meta_timeout={}".format(
                            1000 * timeout_to_seconds(timeout)
                        )
                    )
                self.config.runner.pcmk.resource_digests(
                    self.stonith_id,
                    SCSI_NODE,
                    name=f"{name}-{num}.op.digests",
                    stdout=crm_digests_xml,
                    args=args,
                )

    def assert_command_success(  # noqa: PLR0913
        self,
        *,
        devices_before=DEVICES_1,
        devices_updated=DEVICES_2,
        devices_add=None,
        devices_remove=None,
        unfence=None,
        resource_ops=DEFAULT_OPS,
        lrm_monitor_ops=DEFAULT_LRM_MONITOR_OPS,
        lrm_start_ops=DEFAULT_LRM_START_OPS,
        lrm_monitor_ops_updated=DEFAULT_LRM_MONITOR_OPS_UPDATED,
        lrm_start_ops_updated=DEFAULT_LRM_START_OPS_UPDATED,
        digests_attrs_list=None,
        digests_attrs_list_updated=None,
    ):
        # pylint: disable=too-many-arguments
        self.config_cib(
            devices_before=devices_before,
            devices_updated=devices_updated,
            resource_ops=resource_ops,
            lrm_monitor_ops=lrm_monitor_ops,
            lrm_start_ops=lrm_start_ops,
            digests_attrs_list=digests_attrs_list,
        )
        if unfence:
            self.config.corosync_conf.load_content(
                corosync_conf_fixture(
                    self.existing_corosync_nodes,
                    get_two_node(len(self.existing_corosync_nodes)),
                )
            )
            self.config.http.corosync.get_corosync_online_targets(
                node_labels=self.existing_nodes
            )
            self.unfence_config(
                original_devices=devices_before,
                updated_devices=devices_updated,
                node_labels=self.existing_nodes,
            )
        self.config.env.push_cib(
            resources=fixture_scsi(
                stonith_id=self.stonith_id,
                stonith_type=self.stonith_type,
                devices=devices_updated,
                resource_ops=resource_ops,
            ),
            status=_fixture_status(
                self.stonith_id,
                self.stonith_type,
                lrm_start_ops=lrm_start_ops_updated,
                lrm_monitor_ops=lrm_monitor_ops_updated,
                digests_attrs_list=digests_attrs_list_updated,
            ),
        )
        kwargs = dict(devices_updated=devices_updated)
        if devices_add is not None:
            kwargs["devices_add"] = devices_add
        if devices_remove is not None:
            kwargs["devices_remove"] = devices_remove
        self.command(**kwargs)()
        self.env_assist.assert_reports([])

    def digest_attr_value_single(self, digest, last_comma=True):
        comma = "," if last_comma else ""
        return f"{self.stonith_id}:{self.stonith_type}:{digest}{comma}"

    def digest_attr_value_multiple(self, digest, last_comma=True):
        if self.stonith_type == STONITH_TYPE_SCSI:
            value = f"{STONITH_ID_MPATH}:{STONITH_TYPE_MPATH}:{DEFAULT_DIGEST},"
        else:
            value = f"{STONITH_ID_SCSI}:{STONITH_TYPE_SCSI}:{DEFAULT_DIGEST},"

        return f"{value}{self.digest_attr_value_single(digest, last_comma=last_comma)}"


class UpdateScsiDevicesFailuresMixin(UpdateScsiDevicesMixin):
    def test_pcmk_doesnt_support_digests(self):
        self.config.runner.cib.load(
            resources=fixture_scsi(
                stonith_id=self.stonith_id, stonith_type=self.stonith_type
            )
        )
        self.config.runner.pcmk.is_resource_digests_supported(
            is_supported=False
        )
        self.env_assist.assert_raise_library_error(
            self.command(),
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_OF_SCSI_DEVICES_NOT_SUPPORTED,
                )
            ],
            expected_in_processor=False,
        )

    def test_nonexistent_id(self):
        """
        lower level tested in
        pcs_test.tier0.lib.cib.test_stonith.ValidateStonithRestartlessUpdate
        """
        self.config.runner.cib.load(
            resources=fixture_scsi(
                stonith_id="not-searched-id",
                stonith_type=self.stonith_type,
            )
        )
        self.config.runner.pcmk.is_resource_digests_supported()
        self.env_assist.assert_raise_library_error(self.command())
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_NOT_FOUND,
                    id=self.stonith_id,
                    expected_types=["primitive"],
                    context_type="cib",
                    context_id="",
                )
            ]
        )

    def test_not_supported_resource_type(self):
        """
        lower level tested in
        pcs_test.tier0.lib.cib.test_stonith.ValidateStonithRestartlessUpdate
        """
        self.config.runner.cib.load(
            resources=fixture_scsi(
                stonith_id=self.stonith_id,
                stonith_type=STONITH_TYPE_UNSUPPORTED,
            )
        )
        self.config.runner.pcmk.is_resource_digests_supported()
        self.env_assist.assert_raise_library_error(
            self.command(devices_add=[DEV_2], devices_remove=[DEV_1])
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_UNSUPPORTED_AGENT,
                    resource_id=self.stonith_id,
                    resource_type=STONITH_TYPE_UNSUPPORTED,
                    supported_stonith_types=["fence_scsi", "fence_mpath"],
                )
            ]
        )

    def test_stonith_resource_is_not_running(self):
        self.config_cib(
            nodes_running_on=0, start_digests=False, monitor_digests=False
        )
        self.env_assist.assert_raise_library_error(
            self.command(),
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM,
                    reason=f"resource '{self.stonith_id}' is not running on any node",
                    reason_type=reports.const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_NOT_RUNNING,
                )
            ],
            expected_in_processor=False,
        )

    def test_stonith_resource_is_running_on_more_than_one_node(self):
        self.config_cib(
            nodes_running_on=2, start_digests=False, monitor_digests=False
        )
        self.env_assist.assert_raise_library_error(
            self.command(),
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM,
                    reason=(
                        f"resource '{self.stonith_id}' is running on more than "
                        "1 node"
                    ),
                    reason_type=reports.const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_OTHER,
                )
            ],
            expected_in_processor=False,
        )

    def test_no_lrm_start_op(self):
        self.config_cib(lrm_start_ops=(), monitor_digests=False)
        self.env_assist.assert_raise_library_error(
            self.command(),
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM,
                    reason=(
                        "lrm_rsc_op element for start operation was not found"
                    ),
                    reason_type=reports.const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_OTHER,
                )
            ],
            expected_in_processor=False,
        )

    def test_lrm_op_missing_digest_attributes(self):
        self.config_cib(
            resource_ops=(),
            lrm_start_ops=(("0", None, None, None),),
            lrm_monitor_ops=(),
        )
        self.env_assist.assert_raise_library_error(
            self.command(),
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM,
                    reason="no digests attributes in lrm_rsc_op element",
                    reason_type=reports.const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_OTHER,
                )
            ],
            expected_in_processor=False,
        )

    def test_crm_resource_digests_missing(self):
        self.config_cib(
            lrm_start_ops=(("0", None, None, "somedigest"),),
            monitor_digests=False,
        )
        self.env_assist.assert_raise_library_error(
            self.command(),
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM,
                    reason=(
                        "necessary digest for 'op-restart-digest' attribute is "
                        "missing"
                    ),
                    reason_type=reports.const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_OTHER,
                )
            ],
            expected_in_processor=False,
        )

    def test_crm_resource_digests_missing_for_transient_digests_attrs(self):
        self.config_cib(
            digests_attrs_list=[
                [
                    (
                        "digests-secure",
                        self.digest_attr_value_single(ALL_DIGEST),
                    ),
                ],
            ],
            crm_digests_xml=fixture_digests_xml(
                self.stonith_id, SCSI_NODE, devices="", nonprivate=False
            ),
        )
        self.env_assist.assert_raise_library_error(
            self.command(),
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM,
                    reason=(
                        "necessary digest for '#digests-secure' attribute is "
                        "missing"
                    ),
                    reason_type=reports.const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_OTHER,
                )
            ],
            expected_in_processor=False,
        )

    def test_multiple_digests_attributes(self):
        self.config_cib(
            digests_attrs_list=[
                2
                * [
                    (
                        "digests-all",
                        self.digest_attr_value_single(DEFAULT_DIGEST),
                    ),
                ],
            ],
        )
        self.env_assist.assert_raise_library_error(
            self.command(),
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM,
                    reason=("multiple digests attributes: '#digests-all'"),
                    reason_type=reports.const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_OTHER,
                )
            ],
            expected_in_processor=False,
        )

    def test_monitor_ops_and_lrm_monitor_ops_do_not_match(self):
        self.config_cib(
            resource_ops=(
                ("monitor", "30s", "10s", None),
                ("monitor", "30s", "20s", "31"),
                ("monitor", "60s", None, None),
            ),
            monitor_digests=False,
        )
        self.env_assist.assert_raise_library_error(
            self.command(),
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM,
                    reason=(
                        "number of lrm_rsc_op and op elements for monitor "
                        "operation differs"
                    ),
                    reason_type=reports.const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_OTHER,
                )
            ],
            expected_in_processor=False,
        )

    def test_lrm_monitor_ops_not_found(self):
        self.config_cib(
            resource_ops=(("monitor", "30s", None, None),),
            monitor_digests=False,
        )
        self.env_assist.assert_raise_library_error(
            self.command(),
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM,
                    reason=(
                        "monitor lrm_rsc_op element for resource "
                        f"'{self.stonith_id}', node '{SCSI_NODE}' and interval "
                        "'30000' not found"
                    ),
                    reason_type=reports.const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_OTHER,
                )
            ],
            expected_in_processor=False,
        )

    def test_node_missing_name_and_missing_auth_token(self):
        self.config_cib()
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(
                self.existing_corosync_nodes
                + [[("ring0_addr", "custom_node"), ("nodeid", "5")]],
            )
        )
        self.config.env.set_known_nodes(self.existing_nodes[:-1])
        self.env_assist.assert_raise_library_error(self.command())
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=True,
                ),
                fixture.error(
                    reports.codes.HOST_NOT_FOUND,
                    host_list=[self.existing_nodes[-1]],
                ),
            ]
        )

    def test_unfence_failure_unable_to_connect(self):
        self.config_cib()
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(self.existing_corosync_nodes)
        )
        self.config.http.corosync.get_corosync_online_targets(
            node_labels=self.existing_nodes
        )
        communication_list = [
            dict(label=node, raw_data=json.dumps(self.get_raw_data(node)))
            for node in self.existing_nodes
        ]
        communication_list[0]["was_connected"] = False
        communication_list[0]["error_msg"] = "errA"
        communication_list[1]["output"] = json.dumps(
            dto.to_dict(
                communication.dto.InternalCommunicationResultDto(
                    status=communication.const.COM_STATUS_ERROR,
                    status_msg="error",
                    report_list=[
                        reports.ReportItem.error(
                            reports.messages.StonithUnfencingFailed("errB")
                        ).to_dto()
                    ],
                    data=None,
                )
            )
        )
        self.unfence_config(communication_list=communication_list)
        self.env_assist.assert_raise_library_error(self.command())
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.existing_nodes[0],
                    command=self.command_url,
                    reason="errA",
                ),
                fixture.error(
                    reports.codes.STONITH_UNFENCING_FAILED,
                    reason="errB",
                    context=reports.dto.ReportItemContextDto(
                        node=self.existing_nodes[1],
                    ),
                ),
            ]
        )

    def test_corosync_targets_unable_to_connect(self):
        self.config_cib()
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(self.existing_corosync_nodes)
        )
        self.config.http.corosync.get_corosync_online_targets(
            communication_list=[
                dict(
                    label=self.existing_nodes[0],
                    output=corosync_running_check_response(True),
                ),
            ]
            + [
                dict(
                    label=node,
                    was_connected=False,
                    errno=7,
                    error_msg="an error",
                )
                for node in self.existing_nodes[1:]
            ]
        )
        self.env_assist.assert_raise_library_error(self.command())
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                    node=node,
                    command="remote/status",
                    reason="an error",
                )
                for node in self.existing_nodes[1:]
            ]
        )

    def test_corosync_targets_skip_offline_unfence_node_running_corosync(
        self,
    ):
        self.config_cib()
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(self.existing_corosync_nodes)
        )
        self.config.http.corosync.get_corosync_online_targets(
            communication_list=[
                dict(
                    label=self.existing_nodes[0],
                    output=corosync_running_check_response(True),
                ),
                dict(
                    label=self.existing_nodes[1],
                    output=corosync_running_check_response(False),
                ),
                dict(
                    label=self.existing_nodes[2],
                    was_connected=False,
                    errno=7,
                    error_msg="an error",
                ),
            ]
        )
        communication_list = [
            dict(
                label=self.existing_nodes[0],
                raw_data=json.dumps(self.get_raw_data(self.existing_nodes[0])),
            ),
        ]
        self.unfence_config(communication_list=communication_list)
        self.config.env.push_cib(
            resources=fixture_scsi(
                stonith_id=self.stonith_id,
                stonith_type=self.stonith_type,
                devices=DEVICES_2,
            ),
            status=_fixture_status(
                self.stonith_id,
                self.stonith_type,
                lrm_start_ops=DEFAULT_LRM_START_OPS_UPDATED,
                lrm_monitor_ops=DEFAULT_LRM_MONITOR_OPS_UPDATED,
            ),
        )
        self.command(force_flags=[reports.codes.SKIP_OFFLINE_NODES])()
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.existing_nodes[2],
                    command="remote/status",
                    reason="an error",
                ),
            ]
        )

    def test_corosync_targets_unable_to_perform_unfencing_operation(
        self,
    ):
        self.config_cib()
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(self.existing_corosync_nodes)
        )
        self.config.http.corosync.get_corosync_online_targets(
            communication_list=[
                dict(
                    label=self.existing_nodes[0],
                    was_connected=False,
                    errno=7,
                    error_msg="an error",
                ),
                dict(
                    label=self.existing_nodes[1],
                    was_connected=False,
                    errno=7,
                    error_msg="an error",
                ),
                dict(
                    label=self.existing_nodes[2],
                    output=corosync_running_check_response(False),
                ),
            ]
        )
        self.unfence_config(communication_list=[])
        self.env_assist.assert_raise_library_error(
            self.command(force_flags=[reports.codes.SKIP_OFFLINE_NODES])
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=node,
                    command="remote/status",
                    reason="an error",
                )
                for node in self.existing_nodes[0:2]
            ]
            + [
                fixture.error(
                    reports.codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE,
                ),
            ]
        )

    def test_unfence_failure_unknown_command(self):
        self.config_cib()
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(self.existing_corosync_nodes)
        )
        self.config.http.corosync.get_corosync_online_targets(
            node_labels=self.existing_nodes
        )
        communication_list = [
            dict(
                label=node,
                raw_data=json.dumps(self.get_raw_data(node)),
            )
            for node in self.existing_nodes
        ]
        communication_list[2]["response_code"] = 404
        communication_list[2]["output"] = json.dumps(
            dto.to_dict(
                communication.dto.InternalCommunicationResultDto(
                    status=communication.const.COM_STATUS_UNKNOWN_CMD,
                    status_msg=("Unknown command '/api/v1/unknown/v2'"),
                    report_list=[],
                    data=None,
                )
            )
        )
        self.unfence_config(communication_list=communication_list)
        self.env_assist.assert_raise_library_error(self.command())
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.PCSD_VERSION_TOO_OLD,
                    node=self.existing_nodes[2],
                ),
            ]
        )

    def test_unfence_failure_agent_script_failed(self):
        self.config_cib()
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(self.existing_corosync_nodes)
        )
        self.config.http.corosync.get_corosync_online_targets(
            node_labels=self.existing_nodes
        )
        communication_list = [
            dict(
                label=node,
                raw_data=json.dumps(self.get_raw_data(node)),
            )
            for node in self.existing_nodes
        ]
        communication_list[1]["output"] = json.dumps(
            dto.to_dict(
                communication.dto.InternalCommunicationResultDto(
                    status=communication.const.COM_STATUS_ERROR,
                    status_msg="error",
                    report_list=[
                        reports.ReportItem.error(
                            reports.messages.StonithUnfencingFailed("errB")
                        ).to_dto()
                    ],
                    data=None,
                )
            )
        )
        self.unfence_config(communication_list=communication_list)
        self.env_assist.assert_raise_library_error(self.command())
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_UNFENCING_FAILED,
                    reason="errB",
                    context=reports.dto.ReportItemContextDto(
                        node=self.existing_nodes[1],
                    ),
                ),
            ]
        )

    def test_transient_digests_attrs_bad_value_format(self):
        bad_format = f"{DIGEST_ATTR_VALUE_GOOD_FORMAT}id:type,"
        self.config_cib(
            digests_attrs_list=[
                [
                    ("digests-all", DIGEST_ATTR_VALUE_GOOD_FORMAT),
                    ("digests-secure", bad_format),
                ]
            ]
        )
        self.env_assist.assert_raise_library_error(
            self.command(),
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM,
                    reason=f"invalid digest attribute value: '{bad_format}'",
                    reason_type=reports.const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_OTHER,
                )
            ],
            expected_in_processor=False,
        )


class UpdateScsiDevicesSetBase(UpdateScsiDevicesMixin, CommandSetMixin):
    def test_update_1_to_1_devices(self):
        self.assert_command_success(
            devices_before=DEVICES_1,
            devices_updated=DEVICES_1,
        )

    def test_update_2_to_2_devices(self):
        self.assert_command_success(
            devices_before=DEVICES_2,
            devices_updated=DEVICES_2,
        )

    def test_update_1_to_2_devices(self):
        self.assert_command_success(unfence=[DEV_2])

    def test_update_1_to_3_devices(self):
        self.assert_command_success(
            devices_before=DEVICES_1,
            devices_updated=DEVICES_3,
            unfence=[DEV_2, DEV_3],
        )

    def test_update_3_to_1_devices(self):
        self.assert_command_success(
            devices_before=DEVICES_3,
            devices_updated=DEVICES_1,
        )

    def test_update_3_to_2_devices(self):
        self.assert_command_success(
            devices_before=DEVICES_3,
            devices_updated=DEVICES_2,
        )

    def test_update_add_2_to_2_remove_1(self):
        self.assert_command_success(
            devices_before=[DEV_1, DEV_2],
            devices_updated=[DEV_2, DEV_3, DEV_4],
            unfence=[DEV_3, DEV_4],
        )


class UpdateScsiDevicesAddRemoveBase(
    UpdateScsiDevicesMixin, CommandAddRemoveMixin
):
    def test_add_1_to_1(self):
        self.assert_command_success(
            devices_before=[DEV_1],
            devices_updated=[DEV_1, DEV_2],
            devices_add=[DEV_2],
            devices_remove=[],
            unfence=[DEV_2],
        )

    def test_add_2_to_1(self):
        self.assert_command_success(
            devices_before=[DEV_1],
            devices_updated=[DEV_1, DEV_2, DEV_3],
            devices_add=[DEV_2, DEV_3],
            devices_remove=[],
            unfence=[DEV_2, DEV_3],
        )

    def test_add_2_to_2_and_remove_1(self):
        self.assert_command_success(
            devices_before=[DEV_1, DEV_2],
            devices_updated=[DEV_2, DEV_3, DEV_4],
            devices_add=[DEV_3, DEV_4],
            devices_remove=[DEV_1],
            unfence=[DEV_3, DEV_4],
        )

    def test_remove_1_from_2(self):
        self.assert_command_success(
            devices_before=[DEV_1, DEV_2],
            devices_updated=[DEV_2],
            devices_add=[],
            devices_remove=[DEV_1],
        )

    def test_remove_2_from_3(self):
        self.assert_command_success(
            devices_before=[DEV_1, DEV_2, DEV_3],
            devices_updated=[DEV_3],
            devices_add=[],
            devices_remove=[DEV_2, DEV_1],
        )

    def test_remove_2_from_3_add_1(self):
        self.assert_command_success(
            devices_before=[DEV_1, DEV_2, DEV_3],
            devices_updated=[DEV_3, DEV_4],
            devices_add=[DEV_4],
            devices_remove=[DEV_2, DEV_1],
            unfence=[DEV_4],
        )

    def test_add_1_remove_1(self):
        self.assert_command_success(
            devices_before=[DEV_1, DEV_2],
            devices_updated=[DEV_2, DEV_3],
            devices_add=[DEV_3],
            devices_remove=[DEV_1],
            unfence=[DEV_3],
        )

    def test_add_2_remove_2(self):
        self.assert_command_success(
            devices_before=[DEV_1, DEV_2],
            devices_updated=[DEV_3, DEV_4],
            devices_add=[DEV_3, DEV_4],
            devices_remove=[DEV_1, DEV_2],
            unfence=[DEV_3, DEV_4],
        )


class UpdateScsiDevicesSetFailuresBaseMixin(
    UpdateScsiDevicesFailuresMixin, CommandSetMixin
):
    def test_devices_cannot_be_empty(self):
        self.config.runner.cib.load(
            resources=fixture_scsi(
                stonith_id=self.stonith_id, stonith_type=self.stonith_type
            )
        )
        self.config.runner.pcmk.is_resource_digests_supported()
        self.env_assist.assert_raise_library_error(
            self.command(devices_updated=())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="devices",
                    option_value="",
                    allowed_values=None,
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ]
        )


class UpdateScsiDevicesAddRemoveFailuresBaseMixin(
    UpdateScsiDevicesFailuresMixin, CommandAddRemoveMixin
):
    def test_add_remove_are_empty(self):
        """
        lower level tested in
        pcs_test/tier0/lib/test_validate.ValidateAddRemoveItems
        """
        self.config.runner.cib.load(
            resources=fixture_scsi(
                stonith_id=self.stonith_id, stonith_type=self.stonith_type
            )
        )
        self.config.runner.pcmk.is_resource_digests_supported()
        self.env_assist.assert_raise_library_error(
            self.command(devices_add=(), devices_remove=())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_ITEMS_NOT_SPECIFIED,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE,
                    item_type="device",
                    container_id=self.stonith_id,
                )
            ]
        )


class MpathFailuresMixin:
    def assert_failure(self, host_map, missing_nodes=None):
        self.config_cib(host_map=host_map)
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(
                self.existing_corosync_nodes,
                get_two_node(len(self.existing_corosync_nodes)),
            )
        )
        self.config.http.corosync.get_corosync_online_targets(
            node_labels=self.existing_nodes
        )
        if missing_nodes is None:
            missing_nodes = []
        if not host_map:
            host_map = None
        self.env_assist.assert_raise_library_error(
            self.command(),
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_MISSING_MPATH_KEYS,
                    pcmk_host_map_value=host_map,
                    missing_nodes=sorted(missing_nodes),
                )
            ],
            expected_in_processor=False,
        )

    def test_host_map_missing(self):
        self.assert_failure(None, self.existing_nodes)

    def test_host_map_empty(self):
        self.assert_failure("", self.existing_nodes)

    def test_missing_keys_for_nodes(self):
        self.assert_failure("node1:1;node2=", ["node2", "node3"])


class UpdateScsiDevicesDigestsBase(UpdateScsiDevicesMixin):
    def test_default_monitor(self):
        self.assert_command_success(unfence=[DEV_2])

    def test_no_monitor_ops(self):
        self.assert_command_success(
            unfence=[DEV_2],
            resource_ops=(),
            lrm_monitor_ops=(),
            lrm_monitor_ops_updated=(),
        )

    def test_1_monitor_with_timeout(self):
        self.assert_command_success(
            unfence=[DEV_2],
            resource_ops=(("monitor", "30s", "10s", None),),
            lrm_monitor_ops=(("30000", DEFAULT_DIGEST, None, None),),
            lrm_monitor_ops_updated=(("30000", ALL_DIGEST, None, None),),
        )

    def test_2_monitor_ops_with_timeouts(self):
        self.assert_command_success(
            unfence=[DEV_2],
            resource_ops=(
                ("monitor", "30s", "10s", None),
                ("monitor", "40s", "20s", None),
            ),
            lrm_monitor_ops=(
                ("30000", DEFAULT_DIGEST, None, None),
                ("40000", DEFAULT_DIGEST, None, None),
            ),
            lrm_monitor_ops_updated=(
                ("30000", ALL_DIGEST, None, None),
                ("40000", ALL_DIGEST, None, None),
            ),
        )

    def test_2_monitor_ops_with_one_timeout(self):
        self.assert_command_success(
            unfence=[DEV_2],
            resource_ops=(
                ("monitor", "30s", "10s", None),
                ("monitor", "60s", None, None),
            ),
            lrm_monitor_ops=(
                ("30000", DEFAULT_DIGEST, None, None),
                ("60000", DEFAULT_DIGEST, None, None),
            ),
            lrm_monitor_ops_updated=(
                ("30000", ALL_DIGEST, None, None),
                ("60000", ALL_DIGEST, None, None),
            ),
        )

    def test_various_start_ops_one_lrm_start_op(self):
        self.assert_command_success(
            unfence=[DEV_2],
            resource_ops=(
                ("monitor", "60s", None, None),
                ("start", "0s", "40s", None),
                ("start", "0s", "30s", "1"),
                ("start", "10s", "5s", None),
                ("start", "20s", None, None),
            ),
        )

    def test_1_nonrecurring_start_op_with_timeout(self):
        self.assert_command_success(
            unfence=[DEV_2],
            resource_ops=(
                ("monitor", "60s", None, None),
                ("start", "0s", "40s", None),
            ),
        )

    def _digests_attrs_before(self, last_comma=True):
        return [
            (
                "digests-all",
                self.digest_attr_value_single(DEFAULT_DIGEST, last_comma),
            ),
            (
                "digests-secure",
                self.digest_attr_value_single(DEFAULT_DIGEST, last_comma),
            ),
        ]

    def _digests_attrs_after(self, last_comma=True):
        return [
            (
                "digests-all",
                self.digest_attr_value_single(ALL_DIGEST, last_comma),
            ),
            (
                "digests-secure",
                self.digest_attr_value_single(NONPRIVATE_DIGEST, last_comma),
            ),
        ]

    def _digests_attrs_before_multi(self, last_comma=True):
        return [
            (
                "digests-all",
                self.digest_attr_value_multiple(DEFAULT_DIGEST, last_comma),
            ),
            (
                "digests-secure",
                self.digest_attr_value_multiple(DEFAULT_DIGEST, last_comma),
            ),
        ]

    def _digests_attrs_after_multi(self, last_comma=True):
        return [
            (
                "digests-all",
                self.digest_attr_value_multiple(ALL_DIGEST, last_comma),
            ),
            (
                "digests-secure",
                self.digest_attr_value_multiple(NONPRIVATE_DIGEST, last_comma),
            ),
        ]

    def test_transient_digests_attrs_all_nodes(self):
        self.assert_command_success(
            unfence=[DEV_2],
            digests_attrs_list=len(self.existing_nodes)
            * [self._digests_attrs_before()],
            digests_attrs_list_updated=len(self.existing_nodes)
            * [self._digests_attrs_after()],
        )

    def test_transient_digests_attrs_not_on_all_nodes(self):
        self.assert_command_success(
            unfence=[DEV_2],
            digests_attrs_list=[self._digests_attrs_before()],
            digests_attrs_list_updated=[self._digests_attrs_after()],
        )

    def test_transient_digests_attrs_all_nodes_multi_value(self):
        self.assert_command_success(
            unfence=[DEV_2],
            digests_attrs_list=len(self.existing_nodes)
            * [self._digests_attrs_before_multi()],
            digests_attrs_list_updated=len(self.existing_nodes)
            * [self._digests_attrs_after_multi()],
        )

    def test_transient_digests_attrs_not_on_all_nodes_multi_value(self):
        self.assert_command_success(
            unfence=[DEV_2],
            digests_attrs_list=[self._digests_attrs_before()],
            digests_attrs_list_updated=[self._digests_attrs_after()],
        )

    def test_transient_digests_attrs_not_all_digest_types(self):
        self.assert_command_success(
            unfence=[DEV_2],
            digests_attrs_list=len(self.existing_nodes)
            * [self._digests_attrs_before()[0:1]],
            digests_attrs_list_updated=len(self.existing_nodes)
            * [self._digests_attrs_after()[0:1]],
        )

    def test_transient_digests_attrs_without_digests_attrs(self):
        self.assert_command_success(
            unfence=[DEV_2],
            digests_attrs_list=len(self.existing_nodes) * [[]],
            digests_attrs_list_updated=len(self.existing_nodes) * [[]],
        )

    def test_transient_digests_attrs_without_last_comma(self):
        self.assert_command_success(
            unfence=[DEV_2],
            digests_attrs_list=[self._digests_attrs_before(last_comma=False)],
            digests_attrs_list_updated=[
                self._digests_attrs_after(last_comma=False)
            ],
        )

    def test_transient_digests_attrs_without_last_comma_multi_value(self):
        self.assert_command_success(
            unfence=[DEV_2],
            digests_attrs_list=[
                self._digests_attrs_before_multi(last_comma=False)
            ],
            digests_attrs_list_updated=[
                self._digests_attrs_after_multi(last_comma=False)
            ],
        )

    def test_transient_digests_attrs_no_digest_for_our_stonith_id(self):
        digests_attrs_list = len(self.existing_nodes) * [
            [
                ("digests-all", DIGEST_ATTR_VALUE_GOOD_FORMAT),
                ("digests-secure", DIGEST_ATTR_VALUE_GOOD_FORMAT),
            ]
        ]
        self.assert_command_success(
            unfence=[DEV_2],
            digests_attrs_list=digests_attrs_list,
            digests_attrs_list_updated=digests_attrs_list,
        )

    def test_transient_digests_attrs_digests_with_empty_value(self):
        digests_attrs_list = len(self.existing_nodes) * [
            [("digests-all", ""), ("digests-secure", "")]
        ]
        self.assert_command_success(
            unfence=[DEV_2],
            digests_attrs_list=digests_attrs_list,
            digests_attrs_list_updated=digests_attrs_list,
        )


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestUpdateScsiDevicesSetMpath(
    UpdateScsiDevicesSetBase, MpathMixin, TestCase
):
    pass


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestUpdateScsiDevicesSetScsi(
    UpdateScsiDevicesSetBase, ScsiMixin, TestCase
):
    pass


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestUpdateScsiDevicesAddRemoveMpath(
    UpdateScsiDevicesAddRemoveBase, MpathMixin, TestCase
):
    pass


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestUpdateScsiDevicesAddRemoveScsi(
    UpdateScsiDevicesAddRemoveBase, ScsiMixin, TestCase
):
    pass


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestUpdateScsiDevicesFailuresMpath(
    UpdateScsiDevicesSetFailuresBaseMixin,
    MpathFailuresMixin,
    MpathMixin,
    TestCase,
):
    pass


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestUpdateScsiDevicesFailuresScsi(
    UpdateScsiDevicesSetFailuresBaseMixin, ScsiMixin, TestCase
):
    pass


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestUpdateScsiDevicesAddRemoveFailuresMpath(
    UpdateScsiDevicesAddRemoveFailuresBaseMixin,
    MpathMixin,
    MpathFailuresMixin,
    TestCase,
):
    pass


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestUpdateScsiDevicesAddRemoveFailuresScsi(
    UpdateScsiDevicesAddRemoveFailuresBaseMixin, ScsiMixin, TestCase
):
    pass


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestUpdateScsiDevicesDigestsSetScsi(
    UpdateScsiDevicesDigestsBase, ScsiMixin, CommandSetMixin, TestCase
):
    pass


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestUpdateScsiDevicesDigestsAddRemoveScsi(
    UpdateScsiDevicesDigestsBase, ScsiMixin, CommandAddRemoveMixin, TestCase
):
    pass


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestUpdateScsiDevicesDigestsSetMpath(
    UpdateScsiDevicesDigestsBase, MpathMixin, CommandSetMixin, TestCase
):
    pass


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestUpdateScsiDevicesDigestsAddRemoveMpath(
    UpdateScsiDevicesDigestsBase, MpathMixin, CommandAddRemoveMixin, TestCase
):
    pass
