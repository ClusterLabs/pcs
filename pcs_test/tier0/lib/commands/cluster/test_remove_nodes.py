# pylint: disable=too-many-lines
# pylint: disable=no-member
import json
import re
from functools import partial
from textwrap import dedent
from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common.reports import codes as report_codes
from pcs.lib.commands import cluster

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import outdent

QDEVICE_HOST = "qdevice.host"
CLUSTER_NAME = "myCluster"


def _corosync_options_fixture(option_list, indent_level=2):
    indent = indent_level * 4 * " "
    return "".join(
        [f"{indent}{option}: {value}\n" for option, value in option_list]
    )


def _get_two_node(nodes_num):
    if nodes_num == 2:
        return [("two_node", "1")]
    return []


def corosync_conf_fixture(
    node_list=(), quorum_options=(), qdevice_net=False, qdevice_tie_breaker=None
):
    nodes = []
    for node in node_list:
        nodes.append(
            dedent(
                """\
                node {{
            {options}    }}
            """
            ).format(options=_corosync_options_fixture(node))
        )
    device = ""
    if qdevice_net:
        if qdevice_tie_breaker:
            qd_tie_breaker = f"\n            tie_breaker: {qdevice_tie_breaker}"
        else:
            qd_tie_breaker = ""
        device = outdent(
            """
                device {{
                    model: net

                    net {{
                        host: {QDEVICE_HOST}{qd_tie_breaker}
                    }}
                }}
            """
        ).format(
            QDEVICE_HOST=QDEVICE_HOST,
            qd_tie_breaker=qd_tie_breaker,
        )
    return dedent(
        """\
        totem {{
            version: 2
            cluster_name: {cluster_name}
            transport: knet
        }}

        nodelist {{
        {nodes}}}

        quorum {{
            provider: corosync_votequorum
        {quorum}{device}}}

        logging {{
            to_logfile: yes
            logfile: {logfile}
            to_syslog: yes
        }}
        """
    ).format(
        cluster_name=CLUSTER_NAME,
        nodes="\n".join(nodes),
        quorum=_corosync_options_fixture(quorum_options, indent_level=1),
        device=device,
        logfile=settings.corosync_log_file,
    )


def corosync_node_fixture(node_id, node, addrs):
    return [(f"ring{i}_addr", addr) for i, addr in enumerate(addrs)] + [
        ("name", node),
        ("nodeid", str(node_id)),
    ]


def node_fixture(node, node_id, addr_sufix=""):
    return corosync_node_fixture(node_id, node, [f"{node}{addr_sufix}"])


class LocalConfig:
    def __init__(self, call_collection, wrap_helper, config):
        del wrap_helper, call_collection
        self.config = config
        self.expected_reports = []

    def set_expected_reports_list(self, expected_reports):
        self.expected_reports = expected_reports

    def distribute_and_reload_corosync_conf(
        self, corosync_conf_content, node_list
    ):
        local_prefix = "local.distribute_and_reload_corosync_conf."
        (
            self.config.http.corosync.set_corosync_conf(
                corosync_conf_content,
                node_labels=node_list,
                name=f"{local_prefix}http.corosync.set_corosync_conf",
            ).http.corosync.reload_corosync_conf(
                node_labels=node_list[:1],
                name=f"{local_prefix}http.corosync.reload_corosync_conf",
            )
        )
        self.expected_reports.extend(
            [fixture.info(report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED)]
            + [
                fixture.info(
                    report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                )
                for node in node_list
            ]
            + [
                fixture.info(
                    report_codes.COROSYNC_CONFIG_RELOADED,
                    node=node_list[0],
                )
            ]
        )

    def destroy_cluster(self, node_list):
        local_prefix = "local.destroy_cluster."
        self.config.http.host.cluster_destroy(
            node_labels=node_list,
            name=f"{local_prefix}http.host.cluster_destroy",
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    report_codes.CLUSTER_DESTROY_STARTED,
                    host_name_list=node_list,
                )
            ]
            + [
                fixture.info(
                    report_codes.CLUSTER_DESTROY_SUCCESS,
                    node=node,
                )
                for node in node_list
            ]
        )


get_env_tools = partial(get_env_tools, local_extensions={"local": LocalConfig})


class SuccessMinimal(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes = []
        self.nodes_to_remove = []
        self.nodes_to_stay = []
        self.expected_reports = []
        self.config.local.set_expected_reports_list(self.expected_reports)

    def set_up(self, staying_num, removing_num):
        self.existing_nodes = [
            f"node{i}" for i in range(staying_num + removing_num)
        ]
        self.nodes_to_remove = self.existing_nodes[-removing_num:]
        self.nodes_to_stay = self.existing_nodes[:-removing_num]
        existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes)
        sbd_installed_check = "is_sbd_installed"
        (
            self.config.corosync_conf.load_content(
                corosync_conf_fixture(
                    existing_corosync_nodes,
                    _get_two_node(len(self.existing_nodes)),
                )
            )
            .http.host.check_auth(node_labels=self.existing_nodes)
            # SBD not installed
            .services.is_installed(
                "sbd", return_value=False, name=sbd_installed_check
            )
            .http.host.get_quorum_status(
                self.existing_nodes,
                node_labels=self.nodes_to_remove[:1],
            )
            .local.destroy_cluster(self.nodes_to_remove)
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    existing_corosync_nodes[:-removing_num],
                    _get_two_node(staying_num),
                ),
                self.nodes_to_stay,
            )
            .http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=self.nodes_to_stay,
            )
        )
        if len(self.nodes_to_stay) % 2 != 0:
            self.config.calls.remove(sbd_installed_check)

    def test_2_staying_1_removed(self):
        self.set_up(2, 1)
        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)
        self.env_assist.assert_reports(self.expected_reports)

    def test_3_staying_1_removed(self):
        self.set_up(3, 1)
        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)
        self.env_assist.assert_reports(self.expected_reports)

    def test_4_staying_1_removed(self):
        self.set_up(4, 1)
        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)
        self.env_assist.assert_reports(self.expected_reports)

    def test_3_staying_2_removed(self):
        self.set_up(3, 2)
        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)
        self.env_assist.assert_reports(self.expected_reports)

    def test_4_staying_2_removed(self):
        self.set_up(4, 2)
        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)
        self.env_assist.assert_reports(self.expected_reports)

    def test_4_staying_3_removed(self):
        self.set_up(4, 3)
        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)
        self.env_assist.assert_reports(self.expected_reports)

    def test_1_staying_1_removed_forced(self):
        self.set_up(1, 1)
        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST)]
        )

    def test_1_staying_2_removed_forced(self):
        self.set_up(1, 2)
        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST)]
        )

    def test_1_staying_3_removed_forced(self):
        self.set_up(1, 3)
        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST)]
        )

    def test_2_staying_2_removed_forced(self):
        self.set_up(2, 2)
        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST)]
        )

    def test_2_staying_3_removed_forced(self):
        self.set_up(2, 3)
        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST)]
        )

    def test_3_staying_3_removed_forced(self):
        self.set_up(3, 3)
        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST)]
        )


class NodeNamesMissing(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.expected_reports = []
        self.config.local.set_expected_reports_list(self.expected_reports)

        staying_num = 2
        removing_num = 1
        self.existing_nodes = [
            f"node{i}" for i in range(staying_num + removing_num)
        ]
        self.nodes_to_remove = self.existing_nodes[-removing_num:]
        self.nodes_to_stay = self.existing_nodes[:-removing_num]
        existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes)
        self.original_conf = corosync_conf_fixture(
            existing_corosync_nodes,
            _get_two_node(len(self.existing_nodes)),
        )
        self.expected_conf = corosync_conf_fixture(
            existing_corosync_nodes[:-removing_num], _get_two_node(staying_num)
        )

    def test_some_node_names_missing(self):
        original_conf = re.sub(r"\s+name: node0\n", "\n", self.original_conf)
        # make sure the name was removed
        self.assertNotEqual(original_conf, self.original_conf)

        (self.config.corosync_conf.load_content(original_conf))

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(), self.nodes_to_remove
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=True,
                ),
            ]
        )

    def test_all_node_names_missing(self):
        original_conf = re.sub(r"\s+name: .*\n", "\n", self.original_conf)
        # make sure the names were removed
        self.assertNotEqual(original_conf, self.original_conf)

        (self.config.corosync_conf.load_content(original_conf))

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(), self.nodes_to_remove
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=True,
                ),
                fixture.error(
                    report_codes.NODE_NOT_FOUND, node="node2", searched_types=[]
                ),
            ]
        )


class SuccessAtbRequired(TestCase):
    # This also tests a case when the cluster is not running on all nodes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes = []
        self.nodes_to_remove = []
        self.nodes_to_stay = []
        self.expected_reports = []
        self.config.local.set_expected_reports_list(self.expected_reports)

    def set_up(self, staying_num, removing_num):
        self.existing_nodes = [
            f"node{i}" for i in range(staying_num + removing_num)
        ]
        self.nodes_to_remove = self.existing_nodes[-removing_num:]
        self.nodes_to_stay = self.existing_nodes[:-removing_num]
        existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        sbd_config_data = dedent(
            """
            # This file has been generated by pcs.
            SBD_DELAY_START=no
            SBD_DEVICE=""
            SBD_OPTS="-n rh85-node1"
            SBD_PACEMAKER=yes
            SBD_STARTMODE=always
            SBD_WATCHDOG_DEV=/dev/watchdog
            SBD_WATCHDOG_TIMEOUT=5
        """
        )
        self.config.env.set_known_nodes(self.existing_nodes)
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(
                existing_corosync_nodes,
                _get_two_node(len(self.existing_nodes)),
            )
        )
        self.config.http.host.check_auth(node_labels=self.existing_nodes)
        self.config.services.is_installed("sbd", return_value=True)
        self.config.services.is_enabled("sbd", return_value=True)
        self.config.fs.exists(settings.sbd_config, return_value=True)
        self.config.fs.open(
            settings.sbd_config,
            mock.mock_open(read_data=sbd_config_data)(),
        )
        self.config.http.corosync.check_corosync_offline(
            node_labels=self.nodes_to_stay,
        )
        self.config.local.destroy_cluster(self.nodes_to_remove)
        self.config.http.corosync.set_corosync_conf(
            corosync_conf_fixture(
                existing_corosync_nodes[:-removing_num],
                [("auto_tie_breaker", "1")],
            ),
            node_labels=self.nodes_to_stay,
        )
        # corosync is not running
        self.config.http.corosync.reload_corosync_conf(
            communication_list=[
                [
                    dict(
                        label=node,
                        output=json.dumps(dict(code="not_running", message="")),
                    )
                ]
                for node in self.nodes_to_stay
            ]
        )
        self.config.http.pcmk.remove_nodes_from_cib(
            self.nodes_to_remove,
            node_labels=self.nodes_to_stay,
        )
        self.expected_reports.extend(
            [
                fixture.warn(
                    report_codes.COROSYNC_QUORUM_ATB_WILL_BE_ENABLED_DUE_TO_SBD
                ),
                fixture.info(report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
            ]
            + [
                fixture.info(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED,
                    node=node,
                )
                for node in self.nodes_to_stay
            ]
            + [fixture.info(report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED)]
            + [
                fixture.info(
                    report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                )
                for node in self.nodes_to_stay
            ]
            + [
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_RELOAD_NOT_POSSIBLE,
                    node=node,
                )
                for node in self.nodes_to_stay
            ]
        )

    def test_2_staying_1_removed(self):
        self.set_up(2, 1)
        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)
        self.env_assist.assert_reports(self.expected_reports)

    def test_2_staying_2_removed(self):
        self.set_up(2, 2)
        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)
        self.env_assist.assert_reports(self.expected_reports)

    def test_2_staying_3_removed(self):
        self.set_up(2, 3)
        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)
        self.env_assist.assert_reports(self.expected_reports)

    def test_4_staying_1_removed(self):
        self.set_up(4, 1)
        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)
        self.env_assist.assert_reports(self.expected_reports)

    def test_4_staying_2_removed(self):
        self.set_up(4, 2)
        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)
        self.env_assist.assert_reports(self.expected_reports)

    def test_4_staying_3_removed(self):
        self.set_up(4, 3)
        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)
        self.env_assist.assert_reports(self.expected_reports)

    def test_4_staying_4_removed(self):
        self.set_up(4, 4)
        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)
        self.env_assist.assert_reports(self.expected_reports)

    def test_4_staying_5_removed(self):
        self.set_up(4, 5)
        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)
        self.env_assist.assert_reports(self.expected_reports)


class FailureAtbRequired(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.expected_reports = []
        self.config.local.set_expected_reports_list(self.expected_reports)
        staying_num = 4
        removing_num = 2
        sbd_config_data = dedent(
            """
            # This file has been generated by pcs.
            SBD_DELAY_START=no
            SBD_DEVICE=""
            SBD_OPTS="-n rh85-node1"
            SBD_PACEMAKER=yes
            SBD_STARTMODE=always
            SBD_WATCHDOG_DEV=/dev/watchdog
            SBD_WATCHDOG_TIMEOUT=5
        """
        )
        self.existing_nodes = [
            f"node{i}" for i in range(staying_num + removing_num)
        ]
        self.nodes_to_remove = self.existing_nodes[-removing_num:]
        self.nodes_to_stay = self.existing_nodes[:-removing_num]
        existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes)
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(
                existing_corosync_nodes,
                _get_two_node(len(self.existing_nodes)),
            )
        )
        self.config.http.host.check_auth(node_labels=self.existing_nodes)
        self.config.services.is_installed("sbd", return_value=True)
        self.config.services.is_enabled("sbd", return_value=True)
        self.config.fs.exists(settings.sbd_config, return_value=True)
        self.config.fs.open(
            settings.sbd_config,
            mock.mock_open(read_data=sbd_config_data)(),
        )
        self.expected_reports.extend(
            [
                fixture.info(report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
            ]
        )

    def test_cluster_is_running_somewhere(self):
        self.config.http.corosync.check_corosync_offline(
            communication_list=[
                {"label": self.nodes_to_stay[0]},
                {
                    "label": self.nodes_to_stay[1],
                    "output": '{"corosync":true}',
                },
                {"label": self.nodes_to_stay[2]},
                {"label": self.nodes_to_stay[3]},
            ]
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED,
                    node=self.nodes_to_stay[0],
                ),
                fixture.error(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_RUNNING,
                    node=self.nodes_to_stay[1],
                ),
                fixture.info(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED,
                    node=self.nodes_to_stay[2],
                ),
                fixture.info(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED,
                    node=self.nodes_to_stay[3],
                ),
                fixture.error(
                    report_codes.COROSYNC_QUORUM_ATB_WILL_BE_ENABLED_DUE_TO_SBD_CLUSTER_IS_RUNNING
                ),
            ]
        )

    def test_cluster_is_running_everywhere(self):
        self.config.http.corosync.check_corosync_offline(
            communication_list=[
                {
                    "label": node,
                    "output": '{"corosync":true}',
                }
                for node in self.nodes_to_stay
            ]
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_RUNNING,
                    node=node,
                )
                for node in self.nodes_to_stay
            ]
            + [
                fixture.error(
                    report_codes.COROSYNC_QUORUM_ATB_WILL_BE_ENABLED_DUE_TO_SBD_CLUSTER_IS_RUNNING
                ),
            ]
        )

    def test_failed_on_some(self):
        err_output = "an error"
        self.config.http.corosync.check_corosync_offline(
            communication_list=[
                {"label": self.nodes_to_stay[0]},
                {
                    "label": self.nodes_to_stay[1],
                    "was_connected": False,
                    "errno": 1,
                    "error_msg": err_output,
                },
                {"label": self.nodes_to_stay[2]},
                {
                    "label": self.nodes_to_stay[3],
                    "output": "not json",
                },
            ]
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED,
                    node=node,
                )
                for node in [self.nodes_to_stay[0], self.nodes_to_stay[2]]
            ]
            + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.nodes_to_stay[1],
                    command="remote/status",
                    reason=err_output,
                ),
                fixture.error(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                    node=self.nodes_to_stay[1],
                    force_code=None,
                ),
                fixture.error(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                    node=self.nodes_to_stay[3],
                    force_code=None,
                ),
                fixture.warn(
                    report_codes.COROSYNC_QUORUM_ATB_WILL_BE_ENABLED_DUE_TO_SBD
                ),
            ]
        )

    def test_failed_all(self):
        err_output = "an error"
        self.config.http.corosync.check_corosync_offline(
            communication_list=[
                {
                    "label": node,
                    "was_connected": False,
                    "errno": 1,
                    "error_msg": err_output,
                }
                for node in self.nodes_to_stay
            ]
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=node,
                    command="remote/status",
                    reason=err_output,
                )
                for node in self.nodes_to_stay
            ]
            + [
                fixture.error(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                    node=node,
                )
                for node in self.nodes_to_stay
            ]
            + [
                fixture.warn(
                    report_codes.COROSYNC_QUORUM_ATB_WILL_BE_ENABLED_DUE_TO_SBD
                ),
            ]
        )


class QuorumCheck(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.expected_reports = []
        self.config.local.set_expected_reports_list(self.expected_reports)
        staying_num = 5
        removing_num = 4
        self.existing_nodes = [
            f"node{i}" for i in range(staying_num + removing_num)
        ]
        self.nodes_to_remove = self.existing_nodes[-removing_num:]
        self.nodes_to_stay = self.existing_nodes[:-removing_num]
        existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes)
        (
            self.config.corosync_conf.load_content(
                corosync_conf_fixture(
                    existing_corosync_nodes,
                    _get_two_node(len(self.existing_nodes)),
                )
            ).http.host.check_auth(node_labels=self.existing_nodes)
        )
        self.updated_corosync_conf_text = corosync_conf_fixture(
            existing_corosync_nodes[:-removing_num]
        )

    def test_some_nodes_not_responding(self):
        err_msg = "an error"
        (
            self.config.http.host.get_quorum_status(
                self.existing_nodes,
                communication_list=[
                    [
                        dict(
                            label=self.nodes_to_remove[0],
                            was_connected=False,
                            errno=1,
                            error_msg=err_msg,
                        )
                    ],
                    [
                        dict(
                            label=self.nodes_to_remove[1],
                            response_code=400,
                            output=err_msg,
                        )
                    ],
                    [
                        dict(
                            label=self.nodes_to_remove[2],
                            output="Cannot initialize CMAP service",
                        )
                    ],
                    [
                        dict(
                            label=self.nodes_to_remove[3],
                        )
                    ],
                ],
            )
            .local.destroy_cluster(self.nodes_to_remove)
            .local.distribute_and_reload_corosync_conf(
                self.updated_corosync_conf_text,
                self.nodes_to_stay,
            )
            .http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=self.nodes_to_stay,
            )
        )

        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.nodes_to_remove[0],
                    command="remote/get_quorum_info",
                    reason=err_msg,
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.nodes_to_remove[1],
                    command="remote/get_quorum_info",
                    reason=err_msg,
                ),
            ]
        )

    def test_all_nodes_not_responding(self):
        err_msg = "an error"
        (
            self.config.http.host.get_quorum_status(
                self.existing_nodes,
                communication_list=[
                    [
                        dict(
                            label=node,
                            was_connected=False,
                            errno=1,
                            error_msg=err_msg,
                        )
                    ]
                    for node in self.nodes_to_remove
                ],
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=node,
                    command="remote/get_quorum_info",
                    reason=err_msg,
                )
                for node in self.nodes_to_remove
            ]
            + [
                fixture.error(
                    report_codes.COROSYNC_QUORUM_LOSS_UNABLE_TO_CHECK,
                    force_code=report_codes.FORCE,
                )
            ]
        )

    def test_all_nodes_not_responding_forced(self):
        err_msg = "an error"
        (
            self.config.http.host.get_quorum_status(
                self.existing_nodes,
                communication_list=[
                    [
                        dict(
                            label=node,
                            was_connected=False,
                            errno=1,
                            error_msg=err_msg,
                        )
                    ]
                    for node in self.nodes_to_remove
                ],
            )
            .local.destroy_cluster(self.nodes_to_remove)
            .local.distribute_and_reload_corosync_conf(
                self.updated_corosync_conf_text,
                self.nodes_to_stay,
            )
            .http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=self.nodes_to_stay,
            )
        )

        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE],
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=node,
                    command="remote/get_quorum_info",
                    reason=err_msg,
                )
                for node in self.nodes_to_remove
            ]
            + [fixture.warn(report_codes.COROSYNC_QUORUM_LOSS_UNABLE_TO_CHECK)]
        )

    def test_all_nodes_not_running_cluster(self):
        (
            self.config.http.host.get_quorum_status(
                self.existing_nodes,
                communication_list=[
                    [
                        dict(
                            label=node,
                            output="Cannot initialize CMAP service",
                        )
                    ]
                    for node in self.nodes_to_remove
                ],
            )
            .local.destroy_cluster(self.nodes_to_remove)
            .local.distribute_and_reload_corosync_conf(
                self.updated_corosync_conf_text,
                self.nodes_to_stay,
            )
            .http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=self.nodes_to_stay,
            )
        )

        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)

        self.env_assist.assert_reports(self.expected_reports)


class FailureQuorumLoss(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.expected_reports = []
        self.config.local.set_expected_reports_list(self.expected_reports)
        staying_num = 3
        removing_num = 3
        self.existing_nodes = [
            f"node{i}" for i in range(staying_num + removing_num)
        ]
        self.nodes_to_remove = self.existing_nodes[-removing_num:]
        self.nodes_to_stay = self.existing_nodes[:-removing_num]
        existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes)
        (
            self.config.corosync_conf.load_content(
                corosync_conf_fixture(
                    existing_corosync_nodes,
                    _get_two_node(len(self.existing_nodes)),
                )
            ).http.host.check_auth(node_labels=self.existing_nodes)
        )
        self.updated_corosync_conf_text = corosync_conf_fixture(
            existing_corosync_nodes[:-removing_num]
        )

    def test_unable_to_get_quorum_status(self):
        err_msg = "Failure"
        self.config.http.host.get_quorum_status(
            self.existing_nodes,
            communication_list=[
                [
                    dict(
                        label=self.nodes_to_remove[0],
                        was_connected=False,
                        errno=1,
                        error_msg=err_msg,
                    )
                ],
                [
                    dict(
                        label=self.nodes_to_remove[1],
                        response_code=400,
                        output=err_msg,
                    )
                ],
                [
                    dict(
                        label=self.nodes_to_remove[2],
                        output="not parsable output",
                    )
                ],
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.nodes_to_remove[0],
                    command="remote/get_quorum_info",
                    reason=err_msg,
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.nodes_to_remove[1],
                    command="remote/get_quorum_info",
                    reason=err_msg,
                ),
                fixture.warn(
                    report_codes.COROSYNC_QUORUM_GET_STATUS_ERROR,
                    reason=(
                        "Missing required section(s): 'node_list', 'quorate', "
                        "'quorum'"
                    ),
                    node=self.nodes_to_remove[2],
                ),
                fixture.error(
                    report_codes.COROSYNC_QUORUM_LOSS_UNABLE_TO_CHECK,
                    force_code=report_codes.FORCE,
                ),
            ]
        )

    def test_unable_to_get_quorum_status_force(self):
        err_msg = "Failure"
        (
            self.config.http.host.get_quorum_status(
                self.existing_nodes,
                communication_list=[
                    [
                        dict(
                            label=self.nodes_to_remove[0],
                            was_connected=False,
                            errno=1,
                            error_msg=err_msg,
                        )
                    ],
                    [
                        dict(
                            label=self.nodes_to_remove[1],
                            response_code=400,
                            output=err_msg,
                        )
                    ],
                    [
                        dict(
                            label=self.nodes_to_remove[2],
                            output="not parsable output",
                        )
                    ],
                ],
            )
            .local.destroy_cluster(self.nodes_to_remove)
            .local.distribute_and_reload_corosync_conf(
                self.updated_corosync_conf_text,
                self.nodes_to_stay,
            )
            .http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=self.nodes_to_stay,
            )
        )

        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE],
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.nodes_to_remove[0],
                    command="remote/get_quorum_info",
                    reason=err_msg,
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.nodes_to_remove[1],
                    command="remote/get_quorum_info",
                    reason=err_msg,
                ),
                fixture.warn(
                    report_codes.COROSYNC_QUORUM_GET_STATUS_ERROR,
                    reason=(
                        "Missing required section(s): 'node_list', 'quorate', "
                        "'quorum'"
                    ),
                    node=self.nodes_to_remove[2],
                ),
                fixture.warn(report_codes.COROSYNC_QUORUM_LOSS_UNABLE_TO_CHECK),
            ]
        )

    def test_unable_to_parse_quorum_status(self):
        self.config.http.host.get_quorum_status(
            self.existing_nodes,
            communication_list=[
                [
                    dict(
                        label=node,
                        output="not parsable output",
                    )
                ]
                for node in self.nodes_to_remove
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.COROSYNC_QUORUM_GET_STATUS_ERROR,
                    reason=(
                        "Missing required section(s): 'node_list', 'quorate', "
                        "'quorum'"
                    ),
                    node=node,
                )
                for node in self.nodes_to_remove
            ]
            + [
                fixture.error(
                    report_codes.COROSYNC_QUORUM_LOSS_UNABLE_TO_CHECK,
                    force_code=report_codes.FORCE,
                ),
            ]
        )

    def test_unable_to_parse_quorum_status_force(self):
        (
            self.config.http.host.get_quorum_status(
                self.existing_nodes,
                communication_list=[
                    [
                        dict(
                            label=node,
                            output="not parsable output",
                        )
                    ]
                    for node in self.nodes_to_remove
                ],
            )
            .local.destroy_cluster(self.nodes_to_remove)
            .local.distribute_and_reload_corosync_conf(
                self.updated_corosync_conf_text,
                self.nodes_to_stay,
            )
            .http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=self.nodes_to_stay,
            )
        )

        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE],
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.COROSYNC_QUORUM_GET_STATUS_ERROR,
                    reason=(
                        "Missing required section(s): 'node_list', 'quorate', "
                        "'quorum'"
                    ),
                    node=node,
                )
                for node in self.nodes_to_remove
            ]
            + [fixture.warn(report_codes.COROSYNC_QUORUM_LOSS_UNABLE_TO_CHECK)]
        )

    def test_quorum_will_be_lost_force(self):
        (
            self.config.http.host.get_quorum_status(
                self.existing_nodes, node_labels=self.nodes_to_remove[:1]
            )
            .local.destroy_cluster(self.nodes_to_remove)
            .local.distribute_and_reload_corosync_conf(
                self.updated_corosync_conf_text,
                self.nodes_to_stay,
            )
            .http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=self.nodes_to_stay,
            )
        )

        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE],
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST)]
        )

    def test_quorum_will_be_lost(self):
        self.config.http.host.get_quorum_status(
            self.existing_nodes, node_labels=self.nodes_to_remove[:1]
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.COROSYNC_QUORUM_WILL_BE_LOST,
                    force_code=report_codes.FORCE,
                ),
            ]
        )


class FailureRemoveFromCib(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.expected_reports = []
        self.config.local.set_expected_reports_list(self.expected_reports)
        self.reason = "some error"
        staying_num = 3
        removing_num = 2
        self.existing_nodes = [
            f"node{i}" for i in range(staying_num + removing_num)
        ]
        self.nodes_to_remove = self.existing_nodes[-removing_num:]
        self.nodes_to_stay = self.existing_nodes[:-removing_num]
        existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes)
        (
            self.config.corosync_conf.load_content(
                corosync_conf_fixture(
                    existing_corosync_nodes,
                    _get_two_node(len(self.existing_nodes)),
                )
            )
            .http.host.check_auth(node_labels=self.existing_nodes)
            .http.host.get_quorum_status(
                self.existing_nodes,
                node_labels=self.nodes_to_remove[:1],
            )
            .local.destroy_cluster(self.nodes_to_remove)
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    existing_corosync_nodes[:-removing_num],
                    _get_two_node(staying_num),
                ),
                self.nodes_to_stay,
            )
        )

    def test_communication_failure(self):
        (
            self.config.http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                communication_list=[
                    dict(
                        label=self.nodes_to_stay[0],
                        was_connected=False,
                        errno=1,
                        error_msg=self.reason,
                    ),
                    dict(
                        label=self.nodes_to_stay[1],
                        response_code=400,
                        output=self.reason,
                    ),
                    dict(
                        label=self.nodes_to_stay[2],
                    ),
                ],
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
            )
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.nodes_to_stay[0],
                    command="remote/remove_nodes_from_cib",
                    reason=self.reason,
                ),
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.nodes_to_stay[1],
                    command="remote/remove_nodes_from_cib",
                    reason=self.reason,
                ),
            ]
        )

    def test_failure(self):
        (
            self.config.http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                communication_list=[
                    dict(
                        label=self.nodes_to_stay[0],
                        output=json.dumps(
                            dict(
                                code="failed",
                                message=self.reason,
                            )
                        ),
                    ),
                    dict(
                        label=self.nodes_to_stay[1],
                        output="not json",
                    ),
                    dict(
                        label=self.nodes_to_stay[2],
                    ),
                ],
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
            )
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.NODE_REMOVE_IN_PACEMAKER_FAILED,
                    node=self.nodes_to_stay[0],
                    node_list_to_remove=self.nodes_to_remove,
                    reason=self.reason,
                ),
                fixture.error(
                    report_codes.INVALID_RESPONSE_FORMAT,
                    node=self.nodes_to_stay[1],
                ),
            ]
        )

    def test_all_failed(self):
        (
            self.config.http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                communication_list=[
                    dict(
                        label=node,
                        output=json.dumps(
                            dict(
                                code="failed",
                                message=self.reason,
                            )
                        ),
                    )
                    for node in self.nodes_to_stay
                ],
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
            )
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.NODE_REMOVE_IN_PACEMAKER_FAILED,
                    node=node,
                    node_list_to_remove=self.nodes_to_remove,
                    reason=self.reason,
                )
                for node in self.nodes_to_stay
            ]
        )


class FailureCorosyncReload(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.expected_reports = []
        self.config.local.set_expected_reports_list(self.expected_reports)
        self.cmd_url = "remote/reload_corosync_conf"
        self.err_msg = "An error"
        staying_num = 3
        removing_num = 2
        self.existing_nodes = [
            f"node{i}" for i in range(staying_num + removing_num)
        ]
        self.nodes_to_remove = self.existing_nodes[-removing_num:]
        self.nodes_to_stay = self.existing_nodes[:-removing_num]
        existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes)
        (
            self.config.corosync_conf.load_content(
                corosync_conf_fixture(
                    existing_corosync_nodes,
                    _get_two_node(len(self.existing_nodes)),
                )
            )
            .http.host.check_auth(node_labels=self.existing_nodes)
            .http.host.get_quorum_status(
                self.existing_nodes,
                node_labels=self.nodes_to_remove[:1],
            )
            .local.destroy_cluster(self.nodes_to_remove)
            .http.corosync.set_corosync_conf(
                corosync_conf_fixture(
                    existing_corosync_nodes[:-removing_num],
                    _get_two_node(staying_num),
                ),
                node_labels=self.nodes_to_stay,
            )
        )
        self.expected_reports.extend(
            [fixture.info(report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED)]
            + [
                fixture.info(
                    report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                )
                for node in self.nodes_to_stay
            ]
        )

    def test_few_failed(self):
        (
            self.config.http.corosync.reload_corosync_conf(
                communication_list=[
                    [
                        dict(
                            label=self.nodes_to_stay[0],
                            was_connected=False,
                            errno=7,
                            error_msg=self.err_msg,
                        )
                    ],
                    [
                        dict(
                            label=self.nodes_to_stay[1],
                            output=json.dumps(
                                dict(
                                    code="failed",
                                    message=self.err_msg,
                                )
                            ),
                        )
                    ],
                    [
                        dict(
                            label=self.nodes_to_stay[2],
                        )
                    ],
                ]
            ).http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=self.nodes_to_stay,
            )
        )

        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.nodes_to_stay[0],
                    command=self.cmd_url,
                    reason=self.err_msg,
                ),
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_RELOAD_ERROR,
                    node=self.nodes_to_stay[1],
                    reason=self.err_msg,
                ),
                fixture.info(
                    report_codes.COROSYNC_CONFIG_RELOADED,
                    node=self.nodes_to_stay[2],
                ),
            ]
        )

    def test_failed_and_corosync_not_running(self):
        (
            self.config.http.corosync.reload_corosync_conf(
                communication_list=[
                    [
                        dict(
                            label=self.nodes_to_stay[0],
                            # corosync not running
                            output=json.dumps(
                                dict(code="not_running", message="")
                            ),
                        )
                    ],
                    [
                        dict(
                            label=self.nodes_to_stay[1],
                            output=json.dumps(
                                dict(code="failed", message=self.err_msg)
                            ),
                        )
                    ],
                    [
                        dict(
                            label=self.nodes_to_stay[2],
                        )
                    ],
                ]
            ).http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=self.nodes_to_stay,
            )
        )

        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_RELOAD_NOT_POSSIBLE,
                    node=self.nodes_to_stay[0],
                ),
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_RELOAD_ERROR,
                    node=self.nodes_to_stay[1],
                    reason=self.err_msg,
                ),
                fixture.info(
                    report_codes.COROSYNC_CONFIG_RELOADED,
                    node=self.nodes_to_stay[2],
                ),
            ]
        )

    def test_all_corosync_not_running(self):
        (
            self.config.http.corosync.reload_corosync_conf(
                communication_list=[
                    [
                        dict(
                            label=node,
                            # corosync not running
                            output=json.dumps(
                                dict(code="not_running", message="")
                            ),
                        )
                    ]
                    for node in self.nodes_to_stay
                ]
            ).http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=self.nodes_to_stay,
            )
        )

        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_RELOAD_NOT_POSSIBLE,
                    node=node,
                )
                for node in self.nodes_to_stay
            ]
        )

    def test_all_failed(self):
        self.config.http.corosync.reload_corosync_conf(
            communication_list=[
                [
                    dict(
                        label=self.nodes_to_stay[0],
                        output=json.dumps(
                            dict(code="failed", message=self.err_msg)
                        ),
                    )
                ],
                [
                    dict(
                        label=self.nodes_to_stay[1],
                        output="not a json",
                    )
                ],
                [
                    dict(
                        label=self.nodes_to_stay[2],
                        response_code=400,
                        output=self.err_msg,
                    )
                ],
            ]
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_RELOAD_ERROR,
                    node=self.nodes_to_stay[0],
                    reason=self.err_msg,
                ),
                fixture.warn(
                    report_codes.INVALID_RESPONSE_FORMAT,
                    node=self.nodes_to_stay[1],
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.nodes_to_stay[2],
                    command=self.cmd_url,
                    reason=self.err_msg,
                ),
            ]
            + [
                fixture.error(
                    report_codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE,
                )
            ]
        )


class FailureCorosyncConfDistribution(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.expected_reports = []
        self.config.local.set_expected_reports_list(self.expected_reports)
        staying_num = 3
        removing_num = 2
        self.existing_nodes = [
            f"node{i}" for i in range(staying_num + removing_num)
        ]
        self.nodes_to_remove = self.existing_nodes[-removing_num:]
        self.nodes_to_stay = self.existing_nodes[:-removing_num]
        existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes)
        (
            self.config.corosync_conf.load_content(
                corosync_conf_fixture(
                    existing_corosync_nodes,
                    _get_two_node(len(self.existing_nodes)),
                )
            )
            .http.host.check_auth(node_labels=self.existing_nodes)
            .http.host.get_quorum_status(
                self.existing_nodes,
                node_labels=self.nodes_to_remove[:1],
            )
            .local.destroy_cluster(self.nodes_to_remove)
        )
        self.expected_reports.extend(
            [fixture.info(report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED)]
        )
        self.updated_corosync_conf_text = corosync_conf_fixture(
            existing_corosync_nodes[:-removing_num]
        )

    def test_failed_on_some(self):
        err_output = "an error"
        self.config.http.corosync.set_corosync_conf(
            self.updated_corosync_conf_text,
            communication_list=[
                {"label": self.nodes_to_stay[0]},
                {
                    "label": self.nodes_to_stay[1],
                    "was_connected": False,
                    "errno": 1,
                    "error_msg": err_output,
                },
                {"label": self.nodes_to_stay[2]},
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE, node=node
                )
                for node in [self.nodes_to_stay[0], self.nodes_to_stay[2]]
            ]
            + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.nodes_to_stay[1],
                    command="remote/set_corosync_conf",
                    reason=err_output,
                ),
                fixture.error(
                    report_codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                    node=self.nodes_to_stay[1],
                ),
            ]
        )

    def test_failed_all(self):
        err_output = "an error"
        self.config.http.corosync.set_corosync_conf(
            self.updated_corosync_conf_text,
            communication_list=[
                {
                    "label": node,
                    "was_connected": False,
                    "errno": 1,
                    "error_msg": err_output,
                }
                for node in self.nodes_to_stay
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=node,
                    command="remote/set_corosync_conf",
                    reason=err_output,
                )
                for node in self.nodes_to_stay
            ]
            + [
                fixture.error(
                    report_codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                    node=node,
                )
                for node in self.nodes_to_stay
            ]
        )


class FailureClusterDestroy(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.expected_reports = []
        self.config.local.set_expected_reports_list(self.expected_reports)
        staying_num = 5
        removing_num = 3
        self.existing_nodes = [
            f"node{i}" for i in range(staying_num + removing_num)
        ]
        self.nodes_to_remove = self.existing_nodes[-removing_num:]
        self.nodes_to_stay = self.existing_nodes[:-removing_num]
        existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes)
        (
            self.config.corosync_conf.load_content(
                corosync_conf_fixture(
                    existing_corosync_nodes,
                    _get_two_node(len(self.existing_nodes)),
                )
            )
            .http.host.check_auth(node_labels=self.existing_nodes)
            .http.host.get_quorum_status(
                self.existing_nodes,
                node_labels=self.nodes_to_remove[:1],
            )
        )
        self.updated_corosync_conf_text = corosync_conf_fixture(
            existing_corosync_nodes[:-removing_num]
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    report_codes.CLUSTER_DESTROY_STARTED,
                    host_name_list=self.nodes_to_remove,
                )
            ]
        )

    def test_failed_on_some(self):
        err_output = "an error"
        (
            self.config.http.host.cluster_destroy(
                communication_list=[
                    {"label": self.nodes_to_remove[0]},
                    {
                        "label": self.nodes_to_remove[1],
                        "was_connected": False,
                        "errno": 1,
                        "error_msg": err_output,
                    },
                    {"label": self.nodes_to_remove[2]},
                ]
            )
            .local.distribute_and_reload_corosync_conf(
                self.updated_corosync_conf_text,
                self.nodes_to_stay,
            )
            .http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=self.nodes_to_stay,
            )
        )

        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(report_codes.CLUSTER_DESTROY_SUCCESS, node=node)
                for node in [self.nodes_to_remove[0], self.nodes_to_remove[2]]
            ]
            + [
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.nodes_to_remove[1],
                    command="remote/cluster_destroy",
                    reason=err_output,
                ),
                fixture.warn(
                    report_codes.NODES_TO_REMOVE_UNREACHABLE,
                    node_list=[self.nodes_to_remove[1]],
                ),
            ]
        )

    def test_failed_all(self):
        err_output = "an error"
        (
            self.config.http.host.cluster_destroy(
                communication_list=[
                    {
                        "label": node,
                        "was_connected": False,
                        "errno": 1,
                        "error_msg": err_output,
                    }
                    for node in self.nodes_to_remove
                ]
            )
            .local.distribute_and_reload_corosync_conf(
                self.updated_corosync_conf_text,
                self.nodes_to_stay,
            )
            .http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=self.nodes_to_stay,
            )
        )

        cluster.remove_nodes(self.env_assist.get_env(), self.nodes_to_remove)

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=node,
                    command="remote/cluster_destroy",
                    reason=err_output,
                )
                for node in self.nodes_to_remove
            ]
            + [
                fixture.warn(
                    report_codes.NODES_TO_REMOVE_UNREACHABLE,
                    node_list=self.nodes_to_remove,
                )
            ]
        )


class FailureValidationCorosync(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes = [f"node{i}" for i in range(3)]
        self.existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes)
        (
            self.config.corosync_conf.load_content(
                corosync_conf_fixture(
                    self.existing_corosync_nodes,
                    _get_two_node(len(self.existing_nodes)),
                    qdevice_net=True,
                    qdevice_tie_breaker=1,
                )
            )
        )

    def test_corosync_validation(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(), self.existing_nodes + ["nodeX"]
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.NODE_NOT_FOUND, node="nodeX", searched_types=[]
                ),
                fixture.error(report_codes.CANNOT_REMOVE_ALL_CLUSTER_NODES),
                fixture.error(
                    report_codes.NODE_USED_AS_TIE_BREAKER,
                    node="node0",
                    node_id="1",
                ),
            ]
        )


class OfflineNodes(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.removing_num = 2
        self.staying_num = 2
        self.existing_nodes = [
            f"node{i}" for i in range(self.staying_num + self.removing_num)
        ]
        self.nodes_to_remove = self.existing_nodes[-self.removing_num :]
        self.nodes_to_stay = self.existing_nodes[: -self.removing_num]
        self.existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        self.expected_reports = []
        self.config.local.set_expected_reports_list(self.expected_reports)
        (
            self.config.corosync_conf.load_content(
                corosync_conf_fixture(
                    self.existing_corosync_nodes,
                    _get_two_node(len(self.existing_nodes)),
                )
            )
        )

    def test_all_remaining_offline(self):
        (
            self.config.env.set_known_nodes(
                self.existing_nodes
            ).http.host.check_auth(
                communication_list=[
                    {
                        "label": self.nodes_to_stay[0],
                        "was_connected": False,
                        "errno": 7,
                        "error_msg": "an error",
                    },
                    {
                        "label": self.nodes_to_stay[1],
                        "response_code": 400,
                        "output": "an error",
                    },
                    {
                        "label": self.nodes_to_remove[0],
                    },
                    {
                        "label": self.nodes_to_remove[1],
                    },
                ]
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(), self.nodes_to_remove
            ),
            [],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                    node=self.nodes_to_stay[0],
                    command="remote/check_auth",
                    reason="an error",
                ),
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.nodes_to_stay[1],
                    command="remote/check_auth",
                    reason="an error",
                ),
                fixture.error(
                    report_codes.UNABLE_TO_CONNECT_TO_ANY_REMAINING_NODE
                ),
            ]
        )

    def test_all_remaining_offline_forced(self):
        (
            self.config.env.set_known_nodes(
                self.existing_nodes
            ).http.host.check_auth(
                communication_list=[
                    {
                        "label": self.nodes_to_stay[0],
                        "was_connected": False,
                        "errno": 7,
                        "error_msg": "an error",
                    },
                    {
                        "label": self.nodes_to_stay[1],
                        "response_code": 400,
                        "output": "an error",
                    },
                    {
                        "label": self.nodes_to_remove[0],
                    },
                    {
                        "label": self.nodes_to_remove[1],
                    },
                ]
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
                force_flags=[report_codes.SKIP_OFFLINE_NODES],
            ),
            [],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.OMITTING_NODE,
                    node=self.nodes_to_stay[0],
                ),
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.nodes_to_stay[1],
                    command="remote/check_auth",
                    reason="an error",
                ),
                fixture.error(
                    report_codes.UNABLE_TO_CONNECT_TO_ANY_REMAINING_NODE
                ),
            ]
        )

    def test_some_remaining_offline(self):
        (
            self.config.env.set_known_nodes(self.existing_nodes)
            .http.host.check_auth(
                communication_list=[
                    {
                        "label": self.nodes_to_stay[0],
                        "was_connected": False,
                        "errno": 7,
                        "error_msg": "an error",
                    },
                    {
                        "label": self.nodes_to_stay[1],
                    },
                    {
                        "label": self.nodes_to_remove[0],
                    },
                    {
                        "label": self.nodes_to_remove[1],
                    },
                ]
            )
            # SBD not installed
            .services.is_installed(
                "sbd", return_value=False, name="is_sbd_installed"
            )
            .http.host.get_quorum_status(
                self.existing_nodes,
                node_labels=self.nodes_to_remove[:1],
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
                force_flags=[report_codes.FORCE],
            ),
            [],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                    node=self.nodes_to_stay[0],
                    command="remote/check_auth",
                    reason="an error",
                ),
                fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST),
            ]
        )

    def test_some_remaining_offline_forced(self):
        (
            self.config.env.set_known_nodes(self.existing_nodes)
            .http.host.check_auth(
                communication_list=[
                    {
                        "label": self.nodes_to_stay[0],
                        "was_connected": False,
                        "errno": 7,
                        "error_msg": "an error",
                    },
                    {
                        "label": self.nodes_to_stay[1],
                    },
                    {
                        "label": self.nodes_to_remove[0],
                    },
                    {
                        "label": self.nodes_to_remove[1],
                    },
                ]
            )
            # SBD not installed
            .services.is_installed(
                "sbd", return_value=False, name="is_sbd_installed"
            )
            .http.host.get_quorum_status(
                self.existing_nodes,
                node_labels=self.nodes_to_remove[:1],
            )
            .local.destroy_cluster(self.nodes_to_remove)
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes[: -self.removing_num],
                    _get_two_node(self.staying_num),
                ),
                [self.nodes_to_stay[1]],
            )
            .http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=[self.nodes_to_stay[1]],
            )
        )
        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE, report_codes.SKIP_OFFLINE_NODES],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.OMITTING_NODE,
                    node=self.nodes_to_stay[0],
                ),
                fixture.warn(
                    report_codes.UNABLE_TO_CONNECT_TO_ALL_REMAINING_NODE,
                    node_list=[self.nodes_to_stay[0]],
                ),
                fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST),
            ]
        )

    def test_removed_offline(self):
        (
            self.config.env.set_known_nodes(self.existing_nodes)
            .http.host.check_auth(
                communication_list=[
                    {
                        "label": self.nodes_to_stay[0],
                    },
                    {
                        "label": self.nodes_to_stay[1],
                    },
                    {
                        "label": self.nodes_to_remove[0],
                        "was_connected": False,
                        "errno": 7,
                        "error_msg": "an error",
                    },
                    {
                        "label": self.nodes_to_remove[1],
                        "response_code": 400,
                        "output": "an error",
                    },
                ]
            )
            # SBD not installed
            .services.is_installed(
                "sbd", return_value=False, name="is_sbd_installed"
            )
            .http.host.get_quorum_status(
                self.existing_nodes,
                communication_list=[
                    [
                        {
                            "label": self.nodes_to_remove[0],
                            "was_connected": False,
                            "errno": 7,
                            "error_msg": "an error",
                        }
                    ],
                    [
                        {
                            "label": self.nodes_to_remove[1],
                            "response_code": 400,
                            "output": "an error",
                        }
                    ],
                ],
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
                force_flags=[report_codes.FORCE],
            ),
            [],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                    node=self.nodes_to_remove[0],
                    command="remote/check_auth",
                    reason="an error",
                ),
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.nodes_to_remove[1],
                    command="remote/check_auth",
                    reason="an error",
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.nodes_to_remove[0],
                    command="remote/get_quorum_info",
                    reason="an error",
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.nodes_to_remove[1],
                    command="remote/get_quorum_info",
                    reason="an error",
                ),
                fixture.warn(report_codes.COROSYNC_QUORUM_LOSS_UNABLE_TO_CHECK),
            ]
        )

    def test_removed_offline_unforceable(self):
        (
            self.config.env.set_known_nodes(self.existing_nodes)
            .http.host.check_auth(
                communication_list=[
                    {
                        "label": self.nodes_to_stay[0],
                    },
                    {
                        "label": self.nodes_to_stay[1],
                    },
                    {
                        "label": self.nodes_to_remove[0],
                    },
                    {
                        "label": self.nodes_to_remove[1],
                        "response_code": 400,
                        "output": "an error",
                    },
                ]
            )
            # SBD not installed
            .services.is_installed(
                "sbd", return_value=False, name="is_sbd_installed"
            )
            .http.host.get_quorum_status(
                self.existing_nodes,
                node_labels=self.nodes_to_remove[:1],
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
                force_flags=[
                    report_codes.FORCE,
                    report_codes.SKIP_OFFLINE_NODES,
                ],
            ),
            [],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.nodes_to_remove[1],
                    command="remote/check_auth",
                    reason="an error",
                ),
                fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST),
            ]
        )

    def test_removed_offline_forced(self):
        (
            self.config.env.set_known_nodes(self.existing_nodes)
            .http.host.check_auth(
                communication_list=[
                    {
                        "label": self.nodes_to_stay[0],
                    },
                    {
                        "label": self.nodes_to_stay[1],
                    },
                    {
                        "label": self.nodes_to_remove[0],
                        "was_connected": False,
                        "errno": 7,
                        "error_msg": "an error",
                    },
                    {
                        "label": self.nodes_to_remove[1],
                    },
                ]
            )
            # SBD not installed
            .services.is_installed(
                "sbd",
                return_value=False,
                name="services.is_installed.sbd.False",
            )
            .http.host.get_quorum_status(
                self.existing_nodes,
                communication_list=[
                    [
                        {
                            "label": self.nodes_to_remove[0],
                            "was_connected": False,
                            "errno": 7,
                            "error_msg": "an error",
                        }
                    ],
                    [
                        {
                            "label": self.nodes_to_remove[1],
                        }
                    ],
                ],
            )
            .http.host.cluster_destroy(
                communication_list=[
                    {
                        "label": self.nodes_to_remove[0],
                        "was_connected": False,
                        "errno": 7,
                        "error_msg": "an error",
                    },
                    {
                        "label": self.nodes_to_remove[1],
                    },
                ]
            )
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes[: -self.removing_num],
                    _get_two_node(self.staying_num),
                ),
                self.nodes_to_stay,
            )
            .http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=self.nodes_to_stay,
            )
        )
        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE, report_codes.SKIP_OFFLINE_NODES],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.OMITTING_NODE,
                    node=self.nodes_to_remove[0],
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.nodes_to_remove[0],
                    command="remote/get_quorum_info",
                    reason="an error",
                ),
                fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST),
                fixture.info(
                    report_codes.CLUSTER_DESTROY_STARTED,
                    host_name_list=self.nodes_to_remove,
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.nodes_to_remove[0],
                    command="remote/cluster_destroy",
                    reason="an error",
                ),
                fixture.info(
                    report_codes.CLUSTER_DESTROY_SUCCESS,
                    node=self.nodes_to_remove[1],
                ),
                fixture.warn(
                    report_codes.NODES_TO_REMOVE_UNREACHABLE,
                    node_list=[self.nodes_to_remove[0]],
                ),
            ]
        )

    def test_all_remaining_unknown(self):
        (
            self.config.env.set_known_nodes(
                self.nodes_to_remove
            ).http.host.check_auth(node_labels=self.nodes_to_remove)
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(), self.nodes_to_remove
            ),
            [],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.HOST_NOT_FOUND,
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                    host_list=self.nodes_to_stay,
                ),
                fixture.error(
                    report_codes.UNABLE_TO_CONNECT_TO_ANY_REMAINING_NODE
                ),
            ]
        )

    def test_all_remaining_unknown_forced(self):
        (
            self.config.env.set_known_nodes(
                self.nodes_to_remove
            ).http.host.check_auth(node_labels=self.nodes_to_remove)
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
                force_flags=[report_codes.SKIP_OFFLINE_NODES],
            ),
            [],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.HOST_NOT_FOUND, host_list=self.nodes_to_stay
                ),
                fixture.error(
                    report_codes.UNABLE_TO_CONNECT_TO_ANY_REMAINING_NODE
                ),
            ]
        )

    def test_some_remaining_unknown(self):
        (
            self.config.env.set_known_nodes(
                self.nodes_to_remove + [self.nodes_to_stay[0]]
            )
            .http.host.check_auth(
                node_labels=([self.nodes_to_stay[0]] + self.nodes_to_remove)
            )
            # SBD not installed
            .services.is_installed(
                "sbd",
                return_value=False,
                name="services.is_installed.sbd.False",
            )
            .http.host.get_quorum_status(
                self.existing_nodes,
                node_labels=self.nodes_to_remove[:1],
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
                force_flags=[report_codes.FORCE],
            ),
            [],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.HOST_NOT_FOUND,
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                    host_list=[self.nodes_to_stay[1]],
                ),
                fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST),
            ]
        )

    def test_some_remaining_unknown_forced(self):
        (
            self.config.env.set_known_nodes(
                self.nodes_to_remove + [self.nodes_to_stay[0]]
            )
            .http.host.check_auth(
                node_labels=([self.nodes_to_stay[0]] + self.nodes_to_remove)
            )
            # SBD not installed
            .services.is_installed(
                "sbd",
                return_value=False,
                name="services.is_installed.sbd.False",
            )
            .http.host.get_quorum_status(
                self.existing_nodes,
                node_labels=self.nodes_to_remove[:1],
            )
            .local.destroy_cluster(self.nodes_to_remove)
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes[: -self.removing_num],
                    _get_two_node(self.staying_num),
                ),
                [self.nodes_to_stay[0]],
            )
            .http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove,
                node_labels=[self.nodes_to_stay[0]],
            )
        )
        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE, report_codes.SKIP_OFFLINE_NODES],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.HOST_NOT_FOUND,
                    host_list=[self.nodes_to_stay[1]],
                ),
                fixture.warn(
                    report_codes.UNABLE_TO_CONNECT_TO_ALL_REMAINING_NODE,
                    node_list=[self.nodes_to_stay[1]],
                ),
                fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST),
            ]
        )

    def test_all_removed_unknown(self):
        (
            self.config.env.set_known_nodes(self.nodes_to_stay)
            .http.host.check_auth(node_labels=(self.nodes_to_stay))
            # SBD not installed
            .services.is_installed(
                "sbd",
                return_value=False,
                name="services.is_installed.sbd.False",
            )
            .http.host.get_quorum_status(
                self.existing_nodes,
                node_labels=[],
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
                force_flags=[report_codes.FORCE],
            ),
            [],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.HOST_NOT_FOUND,
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                    host_list=self.nodes_to_remove,
                ),
                fixture.warn(report_codes.COROSYNC_QUORUM_LOSS_UNABLE_TO_CHECK),
            ]
        )

    def test_all_removed_unknown_forced(self):
        (
            self.config.env.set_known_nodes(self.nodes_to_stay)
            .http.host.check_auth(node_labels=(self.nodes_to_stay))
            # SBD not installed
            .services.is_installed(
                "sbd",
                return_value=False,
                name="services.is_installed.sbd.False",
            )
            .http.host.get_quorum_status(
                self.existing_nodes,
                node_labels=[],
            )
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes[: -self.removing_num],
                    _get_two_node(self.staying_num),
                ),
                self.nodes_to_stay,
            )
            .http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove, node_labels=self.nodes_to_stay
            )
        )
        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE, report_codes.SKIP_OFFLINE_NODES],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.HOST_NOT_FOUND, host_list=self.nodes_to_remove
                ),
                fixture.warn(report_codes.COROSYNC_QUORUM_LOSS_UNABLE_TO_CHECK),
                fixture.warn(
                    report_codes.NODES_TO_REMOVE_UNREACHABLE,
                    node_list=self.nodes_to_remove,
                ),
            ]
        )

    def test_some_removed_unknown(self):
        (
            self.config.env.set_known_nodes(
                self.nodes_to_stay + [self.nodes_to_remove[1]]
            )
            .http.host.check_auth(
                node_labels=(self.nodes_to_stay + [self.nodes_to_remove[1]])
            )
            # SBD not installed
            .services.is_installed(
                "sbd",
                return_value=False,
                name="services.is_installed.sbd.False",
            )
            .http.host.get_quorum_status(
                self.existing_nodes,
                node_labels=[self.nodes_to_remove[1]],
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes(
                self.env_assist.get_env(),
                self.nodes_to_remove,
                force_flags=[report_codes.FORCE],
            ),
            [],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    report_codes.HOST_NOT_FOUND,
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                    host_list=[self.nodes_to_remove[0]],
                ),
                fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST),
            ]
        )

    def test_some_removed_unknown_forced(self):
        (
            self.config.env.set_known_nodes(
                self.nodes_to_stay + [self.nodes_to_remove[0]]
            )
            .http.host.check_auth(
                node_labels=(self.nodes_to_stay + [self.nodes_to_remove[0]])
            )
            # SBD not installed
            .services.is_installed(
                "sbd",
                return_value=False,
                name="services.is_installed.sbd.False",
            )
            .http.host.get_quorum_status(
                self.existing_nodes,
                node_labels=self.nodes_to_remove[:1],
            )
            .local.destroy_cluster([self.nodes_to_remove[0]])
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes[: -self.removing_num],
                    _get_two_node(self.staying_num),
                ),
                self.nodes_to_stay,
            )
            .http.pcmk.remove_nodes_from_cib(
                self.nodes_to_remove, node_labels=self.nodes_to_stay
            )
        )
        cluster.remove_nodes(
            self.env_assist.get_env(),
            self.nodes_to_remove,
            force_flags=[report_codes.FORCE, report_codes.SKIP_OFFLINE_NODES],
        )
        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    report_codes.HOST_NOT_FOUND,
                    host_list=[self.nodes_to_remove[1]],
                ),
                fixture.warn(report_codes.COROSYNC_QUORUM_WILL_BE_LOST),
                fixture.warn(
                    report_codes.NODES_TO_REMOVE_UNREACHABLE,
                    node_list=[self.nodes_to_remove[1]],
                ),
            ]
        )
