from unittest import TestCase

from pcs.daemon.app.api_v1 import API_V1_MAP
from pcs.daemon.async_tasks.worker.command_mapping import COMMAND_MAP


class ApiV1MapTest(TestCase):
    def test_all_commands_exist(self):
        missing_commands = set(API_V1_MAP.values()) - set(COMMAND_MAP.keys())
        self.assertEqual(
            0,
            len(missing_commands),
            f"Commands missing in COMMAND_MAP: {missing_commands}",
        )
