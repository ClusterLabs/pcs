from __future__ import (
    absolute_import,
    division,
    print_function,
)

import json

from pcs.common import report_codes
from pcs.lib.commands.sbd import disable_sbd
from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.pcs_unittest import TestCase


class DisableSbd(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_base(self):
        (self.config
            .runner.corosync.version()
            .corosync_conf.load(
                node_name_list=["node-1", "node-2"],
            )
            .http.add_communication(
                "check_auth",
                [
                    dict(
                        label="node-1",
                        output=json.dumps({"notauthorized": "true"}),
                        response_code=401,
                    ),
                    dict(
                        label="node-2",
                        output=json.dumps({"success": "true"}),
                        response_code=200,
                    ),
                ],
                action="remote/check_auth",
                param_list=[('check_auth_only', 1)]
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: disable_sbd(self.env_assist.get_env()),
            [],
        )

        self.env_assist.assert_reports([
            fixture.error(
                report_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
                node="node-1",
                reason="HTTP error: 401",
                command="remote/check_auth",
            )
        ])
