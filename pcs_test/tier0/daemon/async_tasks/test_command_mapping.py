from unittest import TestCase

from pcs.daemon.async_tasks import command_mapping


class ApiV1MapTest(TestCase):
    def test_all_commands_exist(self):
        missing_commands = set(command_mapping.API_V1_MAP.values()) - set(
            command_mapping.COMMAND_MAP.keys()
        )
        self.assertEqual(
            0,
            len(missing_commands),
            f"Commands missing in COMMAND_MAP: {missing_commands}",
        )
