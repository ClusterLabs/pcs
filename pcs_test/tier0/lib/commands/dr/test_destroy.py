import json
from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from pcs import settings
from pcs.common import (
    file_type_codes,
    report_codes,
)
from pcs.common.file import RawFileError
from pcs.lib.commands import dr


DR_CONF = "pcs disaster-recovery config"
REASON = "error msg"


def generate_nodes(nodes_num, prefix=""):
    return [f"{prefix}node{i}" for i in range(1, nodes_num + 1)]


class CheckLive(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def assert_live_required(self, forbidden_options):
        self.env_assist.assert_raise_library_error(
            lambda: dr.destroy(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=forbidden_options
                )
            ],
            expected_in_processor=False
        )

    def test_mock_corosync(self):
        self.config.env.set_corosync_conf_data("corosync conf data")
        self.assert_live_required([file_type_codes.COROSYNC_CONF])

    def test_mock_cib(self):
        self.config.env.set_cib_data("<cib />")
        self.assert_live_required([file_type_codes.CIB])

    def test_mock(self):
        self.config.env.set_corosync_conf_data("corosync conf data")
        self.config.env.set_cib_data("<cib />")
        self.assert_live_required([
            file_type_codes.CIB,
            file_type_codes.COROSYNC_CONF,
        ])


class FixtureMixin:
    def _fixture_load_configs(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
            content="""
                {{
                    "local": {{
                        "role": "PRIMARY"
                    }},
                    "remote_sites": [
                        {{
                            "nodes": [{nodes}],
                            "role": "RECOVERY"
                        }}
                    ]
                }}
            """.format(
                nodes=", ".join([
                    json.dumps(dict(name=node))
                    for node in self.remote_nodes
                ])
            )
        )
        self.config.corosync_conf.load(node_name_list=self.local_nodes)

    def _success_reports(self):
        return [
            fixture.info(
                report_codes.FILES_REMOVE_FROM_NODES_STARTED,
                file_list=[DR_CONF],
                node_list=self.remote_nodes + self.local_nodes,
            )
        ] + [
            fixture.info(
                report_codes.FILE_REMOVE_FROM_NODE_SUCCESS,
                file_description=DR_CONF,
                node=node,
            ) for node in (self.remote_nodes + self.local_nodes)
        ]


class Success(FixtureMixin, TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.local_nodes = generate_nodes(5)
        self.remote_nodes = generate_nodes(3, prefix="remote-")
        self.config.env.set_known_nodes(self.local_nodes + self.remote_nodes)

    def test_minimal(self):
        self._fixture_load_configs()
        self.config.http.files.remove_files(
            node_labels=self.remote_nodes + self.local_nodes,
            pcs_disaster_recovery_conf=True,
        )
        dr.destroy(self.env_assist.get_env())
        self.env_assist.assert_reports(self._success_reports())


class FatalConfigIssue(FixtureMixin, TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.local_nodes = generate_nodes(5)
        self.remote_nodes = generate_nodes(3, prefix="remote-")

    def test_config_missing(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
            exists=False,
        )

        self.env_assist.assert_raise_library_error(
            lambda: dr.destroy(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.DR_CONFIG_DOES_NOT_EXIST,
            ),
        ])

    def test_config_read_error(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
            exception_msg=REASON,
        )

        self.env_assist.assert_raise_library_error(
            lambda: dr.destroy(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.FILE_IO_ERROR,
                file_type_code=file_type_codes.PCS_DR_CONFIG,
                file_path=settings.pcsd_dr_config_location,
                operation=RawFileError.ACTION_READ,
                reason=REASON,
            ),
        ])

    def test_config_parse_error(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_DR_CONFIG,
            settings.pcsd_dr_config_location,
            content="bad content",
        )

        self.env_assist.assert_raise_library_error(
            lambda: dr.destroy(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.PARSE_ERROR_JSON_FILE,
                file_type_code=file_type_codes.PCS_DR_CONFIG,
                file_path=settings.pcsd_dr_config_location,
                line_number=1,
                column_number=1,
                position=0,
                reason="Expecting value",
                full_msg="Expecting value: line 1 column 1 (char 0)",
            ),
        ])

    def test_corosync_conf_read_error(self):
        self._fixture_load_configs()
        self.config.corosync_conf.load_content(
            "", exception_msg=REASON, instead="corosync_conf.load"
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.destroy(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes.UNABLE_TO_READ_COROSYNC_CONFIG,
                    path=settings.corosync_conf_file,
                    reason=REASON,
                ),
            ],
            expected_in_processor=False
        )

    def test_corosync_conf_parse_error(self):
        self._fixture_load_configs()
        self.config.corosync_conf.load_content(
            "wrong {\n  corosync", instead="corosync_conf.load"
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.destroy(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes
                    .PARSE_ERROR_COROSYNC_CONF_LINE_IS_NOT_SECTION_NOR_KEY_VALUE
                ),
            ],
            expected_in_processor=False
        )


class CommunicationIssue(FixtureMixin, TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.local_nodes = generate_nodes(5)
        self.remote_nodes = generate_nodes(3, prefix="remote-")

    def test_unknown_node(self):
        self.config.env.set_known_nodes(
            self.local_nodes[1:] + self.remote_nodes[1:]
        )
        self._fixture_load_configs()
        self.env_assist.assert_raise_library_error(
            lambda: dr.destroy(self.env_assist.get_env())
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.HOST_NOT_FOUND,
                host_list=self.local_nodes[:1] + self.remote_nodes[:1],
                force_code=report_codes.SKIP_OFFLINE_NODES,
            ),
        ])

    def test_unknown_node_force(self):
        existing_nodes = self.remote_nodes[1:] + self.local_nodes[1:]
        self.config.env.set_known_nodes(existing_nodes)
        self._fixture_load_configs()
        self.config.http.files.remove_files(
            node_labels=existing_nodes,
            pcs_disaster_recovery_conf=True,
        )
        dr.destroy(
            self.env_assist.get_env(),
            force_flags=[report_codes.SKIP_OFFLINE_NODES],
        )
        self.env_assist.assert_reports([
            fixture.warn(
                report_codes.HOST_NOT_FOUND,
                host_list=self.local_nodes[:1] + self.remote_nodes[:1],
            ),
        ] + [
            fixture.info(
                report_codes.FILES_REMOVE_FROM_NODES_STARTED,
                file_list=[DR_CONF],
                node_list=existing_nodes,
            )
        ] + [
            fixture.info(
                report_codes.FILE_REMOVE_FROM_NODE_SUCCESS,
                file_description=DR_CONF,
                node=node,
            ) for node in existing_nodes
        ])

    def test_node_issues(self):
        self.config.env.set_known_nodes(self.local_nodes + self.remote_nodes)
        self._fixture_load_configs()
        self.config.http.files.remove_files(
            pcs_disaster_recovery_conf=True,
            communication_list=[
                dict(label=node) for node in self.remote_nodes
            ] + [
                dict(
                    label=self.local_nodes[0],
                    was_connected=False,
                    error_msg=REASON,
                ),
                dict(
                    label=self.local_nodes[1],
                    output="invalid data",
                ),
                dict(
                    label=self.local_nodes[2],
                    output=json.dumps(dict(files={
                        DR_CONF: dict(
                            code="unexpected",
                            message=REASON,
                        ),
                    })),
                ),
            ] + [
                dict(label=node) for node in self.local_nodes[3:]
            ]
        )

        self.env_assist.assert_raise_library_error(
            lambda: dr.destroy(self.env_assist.get_env())
        )
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.FILES_REMOVE_FROM_NODES_STARTED,
                file_list=[DR_CONF],
                node_list=self.remote_nodes + self.local_nodes,
            ),
            fixture.error(
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                command="remote/remove_file",
                node=self.local_nodes[0],
                reason=REASON,
            ),
            fixture.error(
                report_codes.INVALID_RESPONSE_FORMAT,
                node=self.local_nodes[1],
            ),
            fixture.error(
                report_codes.FILE_REMOVE_FROM_NODE_ERROR,
                file_description=DR_CONF,
                reason=REASON,
                node=self.local_nodes[2],
            ),
        ] + [
            fixture.info(
                report_codes.FILE_REMOVE_FROM_NODE_SUCCESS,
                file_description=DR_CONF,
                node=node,
            ) for node in self.local_nodes[3:] + self.remote_nodes
        ])
