from unittest import TestCase

from pcs import settings
from pcs.common import file_type_codes, reports
from pcs.lib.commands.cluster import config

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from .common import corosync_conf_fixture

_COROSYNC_CONF_CONTENT = corosync_conf_fixture()
_NODE_NAME = "node1"


class TestGetCorosyncConf(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_not_live_corosync_conf(self):
        self.config.env.set_corosync_conf_data(_COROSYNC_CONF_CONTENT)
        self.env_assist.assert_raise_library_error(
            lambda: config.get_corosync_conf(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[file_type_codes.COROSYNC_CONF],
                ),
            ]
        )

    def test_success(self):
        self.config.corosync_conf.load_content(_COROSYNC_CONF_CONTENT)
        result = config.get_corosync_conf(self.env_assist.get_env())
        self.assertEqual(result, _COROSYNC_CONF_CONTENT)

    def test_read_failure(self):
        except_msg = "read failed"
        self.config.corosync_conf.load_content("", exception_msg=except_msg)
        self.env_assist.assert_raise_library_error(
            lambda: config.get_corosync_conf(self.env_assist.get_env()),
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.COROSYNC_CONF,
                    operation="read",
                    reason=except_msg,
                    file_path=settings.corosync_conf_file,
                ),
            ],
            expected_in_processor=False,
        )


class TestGetCorosyncConfRemote(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success(self):
        self.config.env.set_known_nodes([_NODE_NAME])
        self.config.http.corosync.get_corosync_conf(
            corosync_conf=_COROSYNC_CONF_CONTENT,
            node_labels=[_NODE_NAME],
        )
        result = config.get_corosync_conf_remote(
            self.env_assist.get_env(), _NODE_NAME
        )
        self.assertEqual(result, _COROSYNC_CONF_CONTENT)

    def test_node_not_found(self):
        self.config.env.set_known_nodes([])
        self.env_assist.assert_raise_library_error(
            lambda: config.get_corosync_conf_remote(
                self.env_assist.get_env(), _NODE_NAME
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND,
                    host_list=[_NODE_NAME],
                ),
            ]
        )

    def test_remote_node_error(self):
        error_msg = "corosync.conf not available"
        self.config.env.set_known_nodes([_NODE_NAME])
        self.config.http.corosync.get_corosync_conf(
            communication_list=[
                [
                    dict(
                        label=_NODE_NAME,
                        response_code=400,
                        output=error_msg,
                    )
                ],
            ],
        )
        self.env_assist.assert_raise_library_error(
            lambda: config.get_corosync_conf_remote(
                self.env_assist.get_env(), _NODE_NAME
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=_NODE_NAME,
                    command="remote/get_corosync_conf",
                    reason=error_msg,
                ),
                fixture.error(
                    reports.codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE,
                ),
            ]
        )
