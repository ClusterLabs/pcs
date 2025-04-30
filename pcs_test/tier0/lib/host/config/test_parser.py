import json
from unittest import TestCase

from pcs.common.host import Destination, PcsKnownHost
from pcs.lib.file.json import JsonParserException
from pcs.lib.host.config.exporter import Exporter as KnownHostsExporter
from pcs.lib.host.config.parser import InvalidFileStructureException
from pcs.lib.host.config.parser import Parser as KnownHostsParser
from pcs.lib.host.config.types import KnownHosts

from pcs_test.tools.misc import read_test_resource

_FIXTURE_KNOWN_HOSTS_RAW_TEXT = read_test_resource("known-hosts")

_FIXTURE_KNOWN_HOSTS_STRUCTURE = KnownHosts(
    format_version=1,
    data_version=5,
    known_hosts={
        "node1": PcsKnownHost(
            name="node1",
            token="abcde",
            dest_list=[
                Destination("10.0.1.1", 2224),
                Destination("10.0.2.1", 2225),
            ],
        ),
        "node2": PcsKnownHost(
            name="node2",
            token="fghij",
            dest_list=[
                Destination("10.0.1.2", 2234),
                Destination("10.0.2.2", 2235),
            ],
        ),
    },
)


class Parser(TestCase):
    def test_invalid_json(self):
        with self.assertRaises(JsonParserException):
            KnownHostsParser.parse("<xml/>".encode())

    def test_root_not_object(self):
        with self.assertRaises(InvalidFileStructureException):
            KnownHostsParser.parse("[]")

    def test_invalid_file_content(self):
        with self.assertRaises(InvalidFileStructureException):
            KnownHostsParser.parse(json.dumps({"format_version": 1}))

    def test_valid_minimal(self):
        result = KnownHostsParser.parse(
            json.dumps(
                {"format_version": 1, "data_version": 10, "known_hosts": {}}
            )
        )
        self.assertEqual(
            KnownHosts(format_version=1, data_version=10, known_hosts=dict()),
            result,
        )

    def test_valid(self):
        result = KnownHostsParser.parse(_FIXTURE_KNOWN_HOSTS_RAW_TEXT)
        self.assertEqual(_FIXTURE_KNOWN_HOSTS_STRUCTURE, result)


class Exporter(TestCase):
    def test_ok(self):
        result = KnownHostsExporter.export(_FIXTURE_KNOWN_HOSTS_STRUCTURE)
        self.assertEqual(
            json.loads(_FIXTURE_KNOWN_HOSTS_RAW_TEXT), json.loads(result)
        )
