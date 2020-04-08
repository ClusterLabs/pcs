import json
from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from pcs import settings
from pcs.common import file_type_codes
from pcs.common.reports import codes as report_codes
from pcs.lib.dr.config.facade import DrRole
from pcs.lib.commands import dr

DR_CFG_DESC = "disaster-recovery config"

COROSYNC_CONF_TEMPLATE = """\
totem {{
    version: 2
    cluster_name: cluster_name
}}

nodelist {{
{node_list}}}
"""

NODE_TEMPLATE_NO_NAME = """\
    node {{
        ring0_addr: {node}
        nodeid: {id}
    }}
"""

NODE_TEMPLATE = """\
    node {{
        ring0_addr: {node}
        name: {node}
        nodeid: {id}
    }}
"""


def export_cfg(cfg_struct):
    return json.dumps(cfg_struct, indent=4, sort_keys=True).encode("utf-8")

def dr_cfg_fixture(local_role, remote_role, nodes):
    return export_cfg(dict(
        local=dict(
            role=local_role.value,
        ),
        remote_sites=[
            dict(
                role=remote_role.value,
                nodes=[dict(name=node) for node in nodes],
            ),
        ]
    ))

def corosync_conf_fixture(node_list):
    return COROSYNC_CONF_TEMPLATE.format(
        node_list="\n".join(node_list_fixture(node_list)),
    )

def node_list_fixture(node_list):
    return [
        NODE_TEMPLATE.format(node=node, id=i)
        for i, node in enumerate(node_list, start=1)
    ]


def generate_nodes(nodes_num, prefix=""):
    return [f"{prefix}node{i}" for i in range(1, nodes_num + 1)]


class CheckLive(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def assert_live_required(self, forbidden_options):
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), "node"),
            [
                fixture.error(
                    report_codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=forbidden_options
                )
            ],
            expected_in_processor=False
        )

    def test_mock_corosync(self):
        self.config.env.set_corosync_conf_data(
            corosync_conf_fixture(generate_nodes(3))
        )
        self.assert_live_required([file_type_codes.COROSYNC_CONF])

    def test_mock_cib(self):
        self.config.env.set_cib_data("<cib />")
        self.assert_live_required([file_type_codes.CIB])

    def test_mock(self):
        self.config.env.set_corosync_conf_data(
            corosync_conf_fixture(generate_nodes(3))
        )
        self.config.env.set_cib_data("<cib />")
        self.assert_live_required([
            file_type_codes.CIB,
            file_type_codes.COROSYNC_CONF,
        ])


class SetRecoverySiteSuccess(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def _test_minimal(self, local_cluster_size, recovery_cluster_size):
        local_nodes = generate_nodes(local_cluster_size)
        remote_nodes = generate_nodes(recovery_cluster_size, prefix="recovery-")
        orig_node = remote_nodes[-1]
        cfg = self.config
        cfg.env.set_known_nodes(local_nodes + remote_nodes)
        cfg.raw_file.exists(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
            exists=False,
        )
        cfg.corosync_conf.load_content(corosync_conf_fixture(local_nodes))
        cfg.http.corosync.get_corosync_conf(
            corosync_conf_fixture(remote_nodes), node_labels=[orig_node]
        )
        cfg.http.files.put_files(
            node_labels=remote_nodes,
            pcs_disaster_recovery_conf=dr_cfg_fixture(
                DrRole.RECOVERY, DrRole.PRIMARY, local_nodes
            ),
            name="distribute_remote",
        )
        cfg.http.files.put_files(
            node_labels=local_nodes,
            pcs_disaster_recovery_conf=dr_cfg_fixture(
                DrRole.PRIMARY, DrRole.RECOVERY, remote_nodes
            ),
            name="distribute_local",
        )
        dr.set_recovery_site(self.env_assist.get_env(), orig_node)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.FILES_DISTRIBUTION_STARTED,
                    file_list=[DR_CFG_DESC],
                    node_list=remote_nodes,
                )
            ] + [
                fixture.info(
                    report_codes.FILE_DISTRIBUTION_SUCCESS,
                    file_description=DR_CFG_DESC,
                    node=node,
                ) for node in remote_nodes
            ] + [
                fixture.info(
                    report_codes.FILES_DISTRIBUTION_STARTED,
                    file_list=[DR_CFG_DESC],
                    node_list=local_nodes,
                )
            ] + [
                fixture.info(
                    report_codes.FILE_DISTRIBUTION_SUCCESS,
                    file_description=DR_CFG_DESC,
                    node=node,
                ) for node in local_nodes
            ]
        )

    def test_minimal_local_1_remote_1(self):
        self._test_minimal(1, 1)

    def test_minimal_local_1_remote_2(self):
        self._test_minimal(1, 2)

    def test_minimal_local_1_remote_3(self):
        self._test_minimal(1, 3)

    def test_minimal_local_2_remote_1(self):
        self._test_minimal(2, 1)

    def test_minimal_local_2_remote_2(self):
        self._test_minimal(2, 2)

    def test_minimal_local_2_remote_3(self):
        self._test_minimal(2, 3)

    def test_minimal_local_3_remote_1(self):
        self._test_minimal(3, 1)

    def test_minimal_local_3_remote_2(self):
        self._test_minimal(3, 2)

    def test_minimal_local_3_remote_3(self):
        self._test_minimal(3, 3)


class FailureValidations(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.local_nodes = generate_nodes(4)

    def test_dr_cfg_exist(self):
        orig_node = "node"
        cfg = self.config
        cfg.env.set_known_nodes(self.local_nodes + [orig_node])
        cfg.raw_file.exists(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
            exists=True,
        )
        cfg.corosync_conf.load_content(corosync_conf_fixture(self.local_nodes))
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), orig_node),
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.DR_CONFIG_ALREADY_EXIST,
            )
        ])

    def test_local_nodes_name_missing(self):
        orig_node = "node"
        cfg = self.config
        cfg.env.set_known_nodes(self.local_nodes + [orig_node])
        cfg.raw_file.exists(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
            exists=False,
        )
        cfg.corosync_conf.load_content(
            COROSYNC_CONF_TEMPLATE.format(
                node_list="\n".join(
                    [
                        NODE_TEMPLATE_NO_NAME.format(
                            node=self.local_nodes[0], id=len(self.local_nodes)
                        )
                    ] + node_list_fixture(self.local_nodes[1:])
                )
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), orig_node),
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                fatal=True,
            )
        ])

    def test_node_part_of_local_cluster(self):
        orig_node = self.local_nodes[-1]
        cfg = self.config
        cfg.env.set_known_nodes(self.local_nodes + [orig_node])
        cfg.raw_file.exists(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
            exists=False,
        )
        cfg.corosync_conf.load_content(corosync_conf_fixture(self.local_nodes))
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), orig_node),
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.NODE_IN_LOCAL_CLUSTER,
                node=orig_node,
            )
        ])

    def test_tokens_missing_for_local_nodes(self):
        orig_node = "node"
        cfg = self.config
        cfg.env.set_known_nodes(self.local_nodes[:-1] + [orig_node])
        cfg.raw_file.exists(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
            exists=False,
        )
        cfg.corosync_conf.load_content(corosync_conf_fixture(self.local_nodes))
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), orig_node),
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.HOST_NOT_FOUND,
                host_list=self.local_nodes[-1:],
            )
        ])

    def test_token_missing_for_node(self):
        orig_node = "node"
        cfg = self.config
        cfg.env.set_known_nodes(self.local_nodes)
        cfg.raw_file.exists(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
            exists=False,
        )
        cfg.corosync_conf.load_content(corosync_conf_fixture(self.local_nodes))
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), orig_node),
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.HOST_NOT_FOUND,
                host_list=[orig_node],
            )
        ])

    def test_tokens_missing_for_remote_cluster(self):
        remote_nodes = generate_nodes(3, prefix="recovery-")
        orig_node = remote_nodes[0]
        cfg = self.config
        cfg.env.set_known_nodes(self.local_nodes + remote_nodes[:-1])
        cfg.raw_file.exists(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
            exists=False,
        )
        cfg.corosync_conf.load_content(corosync_conf_fixture(self.local_nodes))
        cfg.http.corosync.get_corosync_conf(
            corosync_conf_fixture(remote_nodes), node_labels=[orig_node]
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), orig_node),
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.HOST_NOT_FOUND,
                host_list=remote_nodes[-1:],
            )
        ])


REASON = "error msg"


class FailureRemoteCorocyncConf(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.local_nodes = generate_nodes(4)
        self.remote_nodes = generate_nodes(3, prefix="recovery-")
        self.node = self.remote_nodes[0]

        self.config.env.set_known_nodes(self.local_nodes + self.remote_nodes)
        self.config.raw_file.exists(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
            exists=False,
        )
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(self.local_nodes)
        )

    def test_network_issue(self):
        self.config.http.corosync.get_corosync_conf(
            communication_list=[
                dict(
                    label=self.node,
                    was_connected=False,
                    error_msg=REASON,
                )
            ]
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), self.node),
        )
        self.env_assist.assert_reports([
            fixture.warn(
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                node=self.node,
                command="remote/get_corosync_conf",
                reason=REASON,

            ),
            fixture.error(report_codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE)
        ])

    def test_file_does_not_exist(self):
        self.config.http.corosync.get_corosync_conf(
            communication_list=[
                dict(
                    label=self.node,
                    response_code=400,
                    output=REASON,
                )
            ]
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), self.node),
        )
        self.env_assist.assert_reports([
            fixture.warn(
                report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                node=self.node,
                command="remote/get_corosync_conf",
                reason=REASON,

            ),
            fixture.error(report_codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE)
        ])

    def test_node_names_missing(self):
        self.config.http.corosync.get_corosync_conf(
            COROSYNC_CONF_TEMPLATE.format(
                node_list="\n".join(
                    [
                        NODE_TEMPLATE_NO_NAME.format(
                            node=self.remote_nodes[-1],
                            id=len(self.remote_nodes),
                        )
                    ] + node_list_fixture(self.remote_nodes[:-1])
                )
            ),
            node_labels=[self.node],
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), self.node),
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                fatal=True,
            )
        ])


class FailureRemoteDrCfgDistribution(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.local_nodes = generate_nodes(4)
        self.remote_nodes = generate_nodes(3, prefix="recovery-")
        self.node = self.remote_nodes[0]
        self.failed_nodes = self.remote_nodes[-1:]
        successful_nodes = self.remote_nodes[:-1]

        self.config.env.set_known_nodes(self.local_nodes + self.remote_nodes)
        self.config.raw_file.exists(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
            exists=False,
        )
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(self.local_nodes)
        )
        self.config.http.corosync.get_corosync_conf(
            corosync_conf_fixture(self.remote_nodes), node_labels=[self.node]
        )

        self.success_communication = [
            dict(label=node) for node in successful_nodes
        ]
        self.expected_reports = [
            fixture.info(
                report_codes.FILES_DISTRIBUTION_STARTED,
                file_list=[DR_CFG_DESC],
                node_list=self.remote_nodes,
            )
        ] + [
            fixture.info(
                report_codes.FILE_DISTRIBUTION_SUCCESS,
                file_description=DR_CFG_DESC,
                node=node,
            ) for node in successful_nodes
        ]

    def test_write_failure(self):
        self.config.http.files.put_files(
            communication_list=self.success_communication + [
                dict(
                    label=node,
                    output=json.dumps(dict(files={
                        DR_CFG_DESC: dict(
                            code="unexpected",
                            message=REASON
                        ),
                    }))
                ) for node in self.failed_nodes
            ],
            pcs_disaster_recovery_conf=dr_cfg_fixture(
                DrRole.RECOVERY, DrRole.PRIMARY, self.local_nodes
            ),
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), self.node),
        )
        self.env_assist.assert_reports(
             self.expected_reports + [
                fixture.error(
                    report_codes.FILE_DISTRIBUTION_ERROR,
                    file_description=DR_CFG_DESC,
                    reason=REASON,
                    node=node,
                ) for node in self.failed_nodes
            ]
        )

    def test_network_failure(self):
        self.config.http.files.put_files(
            communication_list=self.success_communication + [
                dict(
                    label=node,
                    was_connected=False,
                    error_msg=REASON,
                ) for node in self.failed_nodes
            ],
            pcs_disaster_recovery_conf=dr_cfg_fixture(
                DrRole.RECOVERY, DrRole.PRIMARY, self.local_nodes
            ),
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), self.node),
        )
        self.env_assist.assert_reports(
             self.expected_reports + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    command="remote/put_file",
                    reason=REASON,
                    node=node,
                ) for node in self.failed_nodes
            ]
        )

    def test_communication_error(self):
        self.config.http.files.put_files(
            communication_list=self.success_communication + [
                dict(
                    label=node,
                    response_code=400,
                    output=REASON,
                ) for node in self.failed_nodes
            ],
            pcs_disaster_recovery_conf=dr_cfg_fixture(
                DrRole.RECOVERY, DrRole.PRIMARY, self.local_nodes
            ),
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), self.node),
        )
        self.env_assist.assert_reports(
             self.expected_reports + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    command="remote/put_file",
                    reason=REASON,
                    node=node,
                ) for node in self.failed_nodes
            ]
        )


class FailureLocalDrCfgDistribution(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        local_nodes = generate_nodes(4)
        self.remote_nodes = generate_nodes(3, prefix="recovery-")
        self.node = self.remote_nodes[0]
        self.failed_nodes = local_nodes[-1:]
        successful_nodes = local_nodes[:-1]

        self.config.env.set_known_nodes(local_nodes + self.remote_nodes)
        self.config.raw_file.exists(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
            exists=False,
        )
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(local_nodes)
        )
        self.config.http.corosync.get_corosync_conf(
            corosync_conf_fixture(self.remote_nodes), node_labels=[self.node]
        )
        self.config.http.files.put_files(
            node_labels=self.remote_nodes,
            pcs_disaster_recovery_conf=dr_cfg_fixture(
                DrRole.RECOVERY, DrRole.PRIMARY, local_nodes
            ),
            name="distribute_remote",
        )

        self.success_communication = [
            dict(label=node) for node in successful_nodes
        ]
        self.expected_reports = [
            fixture.info(
                report_codes.FILES_DISTRIBUTION_STARTED,
                file_list=[DR_CFG_DESC],
                node_list=self.remote_nodes,
            )
        ] + [
            fixture.info(
                report_codes.FILE_DISTRIBUTION_SUCCESS,
                file_description=DR_CFG_DESC,
                node=node,
            ) for node in self.remote_nodes
        ] + [
            fixture.info(
                report_codes.FILES_DISTRIBUTION_STARTED,
                file_list=[DR_CFG_DESC],
                node_list=local_nodes,
            )
        ] + [
            fixture.info(
                report_codes.FILE_DISTRIBUTION_SUCCESS,
                file_description=DR_CFG_DESC,
                node=node,
            ) for node in successful_nodes
        ]

    def test_write_failure(self):
        self.config.http.files.put_files(
            communication_list=self.success_communication + [
                dict(
                    label=node,
                    output=json.dumps(dict(files={
                        DR_CFG_DESC: dict(
                            code="unexpected",
                            message=REASON
                        ),
                    }))
                ) for node in self.failed_nodes
            ],
            pcs_disaster_recovery_conf=dr_cfg_fixture(
                DrRole.PRIMARY, DrRole.RECOVERY, self.remote_nodes
            ),
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), self.node),
        )
        self.env_assist.assert_reports(
             self.expected_reports + [
                fixture.error(
                    report_codes.FILE_DISTRIBUTION_ERROR,
                    file_description=DR_CFG_DESC,
                    reason=REASON,
                    node=node,
                ) for node in self.failed_nodes
            ]
        )

    def test_network_failure(self):
        self.config.http.files.put_files(
            communication_list=self.success_communication + [
                dict(
                    label=node,
                    was_connected=False,
                    error_msg=REASON,
                ) for node in self.failed_nodes
            ],
            pcs_disaster_recovery_conf=dr_cfg_fixture(
                DrRole.PRIMARY, DrRole.RECOVERY, self.remote_nodes
            ),
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), self.node),
        )
        self.env_assist.assert_reports(
             self.expected_reports + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    command="remote/put_file",
                    reason=REASON,
                    node=node,
                ) for node in self.failed_nodes
            ]
        )

    def test_communication_error(self):
        self.config.http.files.put_files(
            communication_list=self.success_communication + [
                dict(
                    label=node,
                    response_code=400,
                    output=REASON,
                ) for node in self.failed_nodes
            ],
            pcs_disaster_recovery_conf=dr_cfg_fixture(
                DrRole.PRIMARY, DrRole.RECOVERY, self.remote_nodes
            ),
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.set_recovery_site(self.env_assist.get_env(), self.node),
        )
        self.env_assist.assert_reports(
             self.expected_reports + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    command="remote/put_file",
                    reason=REASON,
                    node=node,
                ) for node in self.failed_nodes
            ]
        )
