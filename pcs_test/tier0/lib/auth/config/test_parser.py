import json
from dataclasses import asdict
from unittest import TestCase

from pcs.lib.auth.config.parser import (
    Parser,
    ParserError,
)
from pcs.lib.auth.config.types import TokenEntry
from pcs.lib.interface.config import ParserErrorException


def _token_fixture(token_id):
    return TokenEntry(
        token=f"token-{token_id}",
        username=f"username-{token_id}",
        creation_date=f"timestamp-{token_id}",
    )


class ParserTest(TestCase):
    def test_not_json(self):
        with self.assertRaises(ParserErrorException):
            Parser.parse("not json".encode())

    @staticmethod
    def _run_parse(data):
        return Parser.parse(json.dumps(data).encode())

    def test_root_obj_not_list(self):
        with self.assertRaises(ParserError):
            self._run_parse(dict(key="value"))

    def test_invalid_structure_of_an_item(self):
        with self.assertRaises(ParserError):
            self._run_parse(
                [
                    asdict(_token_fixture(1)),
                    dict(token="another one", creation_date=1),
                    asdict(_token_fixture(2)),
                ]
            )

    def test_valid_data(self):
        tokens = [_token_fixture(i) for i in range(4)]
        self.assertEqual(
            self._run_parse([asdict(token) for token in tokens]), tokens
        )
