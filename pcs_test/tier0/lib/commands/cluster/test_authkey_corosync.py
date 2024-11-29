import json
from unittest import (
    TestCase,
    mock,
)

from pcs.common import reports
from pcs.lib.commands import cluster
from pcs.settings import corosync_authkey_bytes

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from .common import (
    corosync_conf_fixture,
    get_two_node,
    node_fixture,
)

TEST_AUTHKEY_DEFAULT_SIZE = corosync_authkey_bytes * b"a"
TEST_AUTHKEY_LONGER_THAN_DEFAULT = corosync_authkey_bytes * 2 * b"a"
TEST_AUTHKEY_SHORTER_THAN_DEFAULT = corosync_authkey_bytes // 2 * b"a"


def _get_file_distribution_started_report(nodes):
    return [
        fixture.info(
            reports.codes.FILES_DISTRIBUTION_STARTED,
            file_list=["corosync authkey"],
            node_list=nodes,
        ),
    ]


def _get_file_distribution_success_reports(nodes):
    return [
        fixture.info(
            reports.codes.FILE_DISTRIBUTION_SUCCESS,
            node=node,
            file_description="corosync authkey",
        )
        for node in nodes
    ]


def _get_all_successful_reports(nodes):
    return (
        _get_file_distribution_started_report(nodes)
        + _get_file_distribution_success_reports(nodes)
        + [
            fixture.info(
                reports.codes.COROSYNC_CONFIG_RELOADED,
                node=nodes[0],
            ),
        ]
    )


class CorosyncAuthkeyVariants(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes = ["node1", "node2", "node3"]
        self.existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes)
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(
                self.existing_corosync_nodes,
                get_two_node(len(self.existing_corosync_nodes)),
            )
        )

    @mock.patch(
        "pcs.lib.commands.cluster.generate_binary_key",
        lambda random_bytes_count: TEST_AUTHKEY_DEFAULT_SIZE,
    )
    def test_no_key(self):
        self.config.http.host.check_auth(node_labels=self.existing_nodes)
        self.config.http.files.put_files(
            node_labels=self.existing_nodes,
            corosync_authkey=TEST_AUTHKEY_DEFAULT_SIZE,
        )
        self.config.http.corosync.reload_corosync_conf(
            node_labels=self.existing_nodes[:1],
        )
        cluster.corosync_authkey_change(
            self.env_assist.get_env(), corosync_authkey=None, force_flags=[]
        )
        self.env_assist.assert_reports(
            _get_all_successful_reports(self.existing_nodes)
        )

    def test_key_default_length(self):
        self.config.http.host.check_auth(node_labels=self.existing_nodes)
        self.config.http.files.put_files(
            node_labels=self.existing_nodes,
            corosync_authkey=TEST_AUTHKEY_DEFAULT_SIZE,
        )
        self.config.http.corosync.reload_corosync_conf(
            node_labels=self.existing_nodes[:1],
        )
        cluster.corosync_authkey_change(
            self.env_assist.get_env(),
            corosync_authkey=TEST_AUTHKEY_DEFAULT_SIZE,
            force_flags=[],
        )
        self.env_assist.assert_reports(
            _get_all_successful_reports(self.existing_nodes)
        )

    def test_key_not_default_length(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster.corosync_authkey_change(
                self.env_assist.get_env(),
                corosync_authkey=TEST_AUTHKEY_LONGER_THAN_DEFAULT,
                force_flags=[],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COROSYNC_AUTHKEY_WRONG_LENGTH,
                    force_code=reports.codes.FORCE,
                    actual_length=len(TEST_AUTHKEY_LONGER_THAN_DEFAULT),
                    min_length=corosync_authkey_bytes,
                    max_length=corosync_authkey_bytes,
                ),
            ]
        )

    def test_key_not_default_length_forced(self):
        self.config.http.host.check_auth(node_labels=self.existing_nodes)
        self.config.http.files.put_files(
            node_labels=self.existing_nodes,
            corosync_authkey=TEST_AUTHKEY_SHORTER_THAN_DEFAULT,
        )
        self.config.http.corosync.reload_corosync_conf(
            node_labels=self.existing_nodes[:1],
        )
        cluster.corosync_authkey_change(
            self.env_assist.get_env(),
            corosync_authkey=TEST_AUTHKEY_SHORTER_THAN_DEFAULT,
            force_flags=[reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.COROSYNC_AUTHKEY_WRONG_LENGTH,
                    actual_length=len(TEST_AUTHKEY_SHORTER_THAN_DEFAULT),
                    min_length=corosync_authkey_bytes,
                    max_length=corosync_authkey_bytes,
                ),
            ]
            + _get_all_successful_reports(self.existing_nodes)
        )


@mock.patch(
    "pcs.lib.commands.cluster.generate_binary_key",
    lambda random_bytes_count: TEST_AUTHKEY_DEFAULT_SIZE,
)
class FailureGetOnlineTargets(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes = ["node1", "node2", "node3"]
        self.existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]
        self.successful_nodes = self.existing_nodes[1:]
        self.unsuccessful_nodes = self.existing_nodes[0:1]
        self.config.env.set_known_nodes(self.existing_nodes)
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(
                self.existing_corosync_nodes,
                get_two_node(len(self.existing_corosync_nodes)),
            )
        )

    def test_node_offline(self):
        self.config.http.host.check_auth(
            communication_list=[
                dict(
                    label=self.existing_nodes[0],
                    was_connected=False,
                    errno=7,
                    error_msg="error msg",
                )
            ]
            + [dict(label=node) for node in self.existing_nodes[1:]],
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.corosync_authkey_change(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                    node=self.existing_nodes[0],
                    reason="error msg",
                    command="remote/check_auth",
                )
            ]
        )

    def test_node_error_not_forcable(self):
        self.config.http.host.check_auth(
            communication_list=[
                dict(
                    label=self.existing_nodes[0],
                    response_code=400,
                    output="error msg",
                )
            ]
            + [dict(label=node) for node in self.existing_nodes[1:]],
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.corosync_authkey_change(
                self.env_assist.get_env(), force_flags=[reports.codes.FORCE]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.existing_nodes[0],
                    command="remote/check_auth",
                    reason="error msg",
                ),
            ]
        )

    def test_node_offline_forced(self):
        self.config.http.host.check_auth(
            communication_list=[
                dict(
                    label=self.existing_nodes[0],
                    was_connected=False,
                    errno=7,
                    error_msg="error msg",
                )
            ]
            + [dict(label=node) for node in self.existing_nodes[1:]],
        )
        self.config.http.files.put_files(
            node_labels=self.existing_nodes[1:],
            corosync_authkey=TEST_AUTHKEY_DEFAULT_SIZE,
        )
        self.config.http.corosync.reload_corosync_conf(
            node_labels=self.existing_nodes[1:2],
        )
        cluster.corosync_authkey_change(
            self.env_assist.get_env(),
            force_flags=[reports.codes.SKIP_OFFLINE_NODES],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.OMITTING_NODE, node=self.existing_nodes[0]
                ),
                fixture.info(
                    reports.codes.FILES_DISTRIBUTION_STARTED,
                    file_list=["corosync authkey"],
                    node_list=self.existing_nodes[1:],
                ),
                fixture.info(
                    reports.codes.FILE_DISTRIBUTION_SUCCESS,
                    node=self.existing_nodes[1],
                    file_description="corosync authkey",
                ),
                fixture.info(
                    reports.codes.FILE_DISTRIBUTION_SUCCESS,
                    node=self.existing_nodes[2],
                    file_description="corosync authkey",
                ),
                fixture.info(
                    reports.codes.COROSYNC_CONFIG_RELOADED,
                    node=self.existing_nodes[1],
                ),
            ]
        )

    def test_nodes_all_offline(self):
        self.config.http.host.check_auth(
            communication_list=[
                dict(
                    label=node,
                    was_connected=False,
                    errno=7,
                    error_msg="error msg",
                )
                for node in self.existing_nodes
            ]
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.corosync_authkey_change(
                self.env_assist.get_env(),
                force_flags=[reports.codes.SKIP_OFFLINE_NODES],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(reports.codes.OMITTING_NODE, node=node)
                for node in self.existing_nodes
            ]
            + [
                fixture.error(
                    reports.codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE
                )
            ]
        )


@mock.patch(
    "pcs.lib.commands.cluster.generate_binary_key",
    lambda random_bytes_count: TEST_AUTHKEY_DEFAULT_SIZE,
)
class FailureReloadCorosyncConf(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes = ["node1", "node2", "node3"]
        self.existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes)
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(
                self.existing_corosync_nodes,
                get_two_node(len(self.existing_corosync_nodes)),
            )
        )
        self.config.http.host.check_auth(node_labels=self.existing_nodes)
        self.config.http.files.put_files(
            node_labels=self.existing_nodes,
            corosync_authkey=TEST_AUTHKEY_DEFAULT_SIZE,
        )

    def test_few_failed(self):
        self.config.http.corosync.reload_corosync_conf(
            communication_list=[
                [
                    dict(
                        label=self.existing_nodes[0],
                        response_code=400,
                        output="error msg",
                    ),
                ],
                [
                    dict(
                        label=self.existing_nodes[1],
                        was_connected=False,
                        error_msg="error msg",
                    ),
                ],
                [dict(label=self.existing_nodes[2])],
            ],
        )
        cluster.corosync_authkey_change(self.env_assist.get_env())
        self.env_assist.assert_reports(
            _get_all_successful_reports(self.existing_nodes)[:-1]
            + [
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.existing_nodes[0],
                    command="remote/reload_corosync_conf",
                    reason="error msg",
                ),
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.existing_nodes[1],
                    command="remote/reload_corosync_conf",
                    reason="error msg",
                ),
                fixture.info(
                    reports.codes.COROSYNC_CONFIG_RELOADED,
                    node=self.existing_nodes[2],
                ),
            ]
        )

    def test_all_failed(self):
        self.config.http.corosync.reload_corosync_conf(
            communication_list=[
                [
                    dict(
                        label=self.existing_nodes[0],
                        output="not a json",
                    ),
                ],
                [
                    dict(
                        label=self.existing_nodes[1],
                        was_connected=False,
                        errno=7,
                        error_msg="error msg",
                    ),
                ],
                [
                    dict(
                        label=self.existing_nodes[2],
                        output=json.dumps(
                            dict(code="failed", message="error msg")
                        ),
                    )
                ],
            ],
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.corosync_authkey_change(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            _get_all_successful_reports(self.existing_nodes)[:-1]
            + [
                fixture.warn(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node=self.existing_nodes[0],
                ),
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.existing_nodes[1],
                    command="remote/reload_corosync_conf",
                    reason="error msg",
                ),
                fixture.warn(
                    reports.codes.COROSYNC_CONFIG_RELOAD_ERROR,
                    node=self.existing_nodes[2],
                    reason="error msg",
                ),
                fixture.error(
                    reports.codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE,
                ),
            ]
        )

    def test_failed_and_corosync_not_running(self):
        self.config.http.corosync.reload_corosync_conf(
            communication_list=[
                [
                    dict(
                        label=self.existing_nodes[0],
                        output=json.dumps(dict(code="not_running", message="")),
                    ),
                ],
                [
                    dict(
                        label=self.existing_nodes[1],
                        output=json.dumps(
                            dict(code="failed", message="error msg")
                        ),
                    )
                ],
                [dict(label=self.existing_nodes[2])],
            ],
        )
        cluster.corosync_authkey_change(self.env_assist.get_env())
        self.env_assist.assert_reports(
            _get_all_successful_reports(self.existing_nodes)[:-1]
            + [
                fixture.warn(
                    reports.codes.COROSYNC_CONFIG_RELOAD_NOT_POSSIBLE,
                    node="node1",
                ),
                fixture.warn(
                    reports.codes.COROSYNC_CONFIG_RELOAD_ERROR,
                    node=self.existing_nodes[1],
                    reason="error msg",
                ),
                fixture.info(
                    reports.codes.COROSYNC_CONFIG_RELOADED,
                    node=self.existing_nodes[2],
                ),
            ]
        )

    def test_all_corosync_not_running(self):
        self.config.http.corosync.reload_corosync_conf(
            communication_list=[
                [
                    dict(
                        label=node,
                        output=json.dumps(dict(code="not_running", message="")),
                    )
                ]
                for node in self.existing_nodes
            ],
        )
        cluster.corosync_authkey_change(self.env_assist.get_env())
        self.env_assist.assert_reports(
            _get_all_successful_reports(self.existing_nodes)[:-1]
            + [
                fixture.warn(
                    reports.codes.COROSYNC_CONFIG_RELOAD_NOT_POSSIBLE,
                    node=node,
                )
                for node in self.existing_nodes
            ]
        )


@mock.patch(
    "pcs.lib.commands.cluster.generate_binary_key",
    lambda random_bytes_count: TEST_AUTHKEY_DEFAULT_SIZE,
)
class FailureDistributeCorosyncAuthkey(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes = ["node1", "node2", "node3"]
        self.existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]
        self.successful_nodes = self.existing_nodes[1:]
        self.unsuccessful_nodes = self.existing_nodes[0:1]
        self.config.env.set_known_nodes(self.existing_nodes)
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(
                self.existing_corosync_nodes,
                get_two_node(len(self.existing_corosync_nodes)),
            )
        )
        self.config.http.host.check_auth(node_labels=self.existing_nodes)

    def test_some_failure(self):
        self.config.http.files.put_files(
            corosync_authkey=TEST_AUTHKEY_DEFAULT_SIZE,
            communication_list=[
                dict(
                    label=node,
                    output=json.dumps(
                        dict(
                            files={
                                "corosync authkey": dict(
                                    code="unexpected", message="error msg"
                                ),
                            }
                        )
                    ),
                )
                for node in self.unsuccessful_nodes
            ]
            + [dict(label=node) for node in self.successful_nodes],
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.corosync_authkey_change(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            _get_file_distribution_started_report(self.existing_nodes)
            + _get_file_distribution_success_reports(self.successful_nodes)
            + [
                fixture.error(
                    reports.codes.FILE_DISTRIBUTION_ERROR,
                    node=node,
                    file_description="corosync authkey",
                    reason="error msg",
                )
                for node in self.unsuccessful_nodes
            ]
        )

    def test_node_not_responding(self):
        self.config.http.files.put_files(
            corosync_authkey=TEST_AUTHKEY_DEFAULT_SIZE,
            communication_list=[
                dict(
                    label=self.existing_nodes[0],
                    was_connected=False,
                    errno=7,
                    error_msg="error msg",
                )
            ]
            + [dict(label=node) for node in self.successful_nodes],
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.corosync_authkey_change(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            _get_file_distribution_started_report(self.existing_nodes)
            + _get_file_distribution_success_reports(self.successful_nodes)
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.existing_nodes[0],
                    command="remote/put_file",
                    reason="error msg",
                ),
            ]
        )

    def test_communication_failure(self):
        self.config.http.files.put_files(
            corosync_authkey=TEST_AUTHKEY_DEFAULT_SIZE,
            communication_list=[
                dict(
                    label=node,
                    output="error msg",
                    response_code=400,
                )
                for node in self.unsuccessful_nodes
            ]
            + [dict(label=node) for node in self.successful_nodes],
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.corosync_authkey_change(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            _get_file_distribution_started_report(self.existing_nodes)
            + _get_file_distribution_success_reports(self.successful_nodes)
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node,
                    command="remote/put_file",
                    reason="error msg",
                )
                for node in self.unsuccessful_nodes
            ]
        )

    def test_invalid_response_format(self):
        self.config.http.files.put_files(
            corosync_authkey=TEST_AUTHKEY_DEFAULT_SIZE,
            communication_list=[
                dict(
                    label=self.existing_nodes[0],
                    output="not a json",
                )
                for node in self.unsuccessful_nodes
            ]
            + [dict(label=node) for node in self.successful_nodes],
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.corosync_authkey_change(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            _get_file_distribution_started_report(self.existing_nodes)
            + _get_file_distribution_success_reports(self.successful_nodes)
            + [
                fixture.error(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node=node,
                )
                for node in self.unsuccessful_nodes
            ]
        )


class MissingNodeNamesInCorosync(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes = ["node1", "node2", "node3"]
        self.config.env.set_known_nodes(self.existing_nodes)

    @staticmethod
    def _get_corosync_nodes_options(node_list, skip_name_idx_list):
        result = []
        for index, node in enumerate(node_list):
            node_option_list = []
            node_option_list.append(("ring0_addr", node))
            if index not in skip_name_idx_list:
                node_option_list.append(("name", node))
            node_option_list.append(("nodeid", str(index + 1)))
            result.append(node_option_list)
        return result

    def assert_command(self, corosync_nodes_options):
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(
                corosync_nodes_options,
                get_two_node(len(self.existing_nodes)),
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.corosync_authkey_change(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=True,
                ),
            ]
        )

    def test_missing_name_of_a_node(self):
        self.assert_command(
            self._get_corosync_nodes_options(self.existing_nodes, [0])
        )

    def test_missing_name_of_all_nodes(self):
        self.assert_command(
            self._get_corosync_nodes_options(
                self.existing_nodes, range(0, len(self.existing_nodes))
            )
        )


class HostNotFound(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes = ["node1", "node2", "node3"]
        self.existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(
                self.existing_corosync_nodes,
                get_two_node(len(self.existing_corosync_nodes)),
            )
        )

    def test_some_nodes_unknown(self):
        self.config.env.set_known_nodes(self.existing_nodes[1:])
        self.env_assist.assert_raise_library_error(
            lambda: cluster.corosync_authkey_change(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND,
                    host_list=self.existing_nodes[:1],
                ),
            ]
        )

    def test_all_nodes_unknown(self):
        self.config.env.set_known_nodes([])
        self.env_assist.assert_raise_library_error(
            lambda: cluster.corosync_authkey_change(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND,
                    host_list=self.existing_nodes,
                ),
                fixture.error(reports.codes.NONE_HOST_FOUND),
            ]
        )
