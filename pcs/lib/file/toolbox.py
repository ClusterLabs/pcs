from collections import namedtuple
import json

from pcs.common import file_type_codes as code


FileToolbox = namedtuple(
    "FileToolbox",
    [
        # File type code the toolbox belongs to
        "file_type_code",
        # Provides an easy access for reading and modifying data
        "facade",
        # Turns raw data into a structure which the facade is able to process
        "parser",
        # Turns a structure produced by the parser and the facade to raw data
        "exporter",
        # Checks that the structure is valid
        "validator",
        # Provides means for file syncing based on the file's version
        "version_controller",
    ]
)

def _json_parser(raw_bytes):
    # raises JSONDecodeError(ValueError) with nice attributes
    # TODO raise a custom exception common for all our parsers? We probably
    # should do that to unify various parsers' behavior: json, corosync, booth,
    # known-hosts...
    # json.loads handles bytes, it expects utf-8, 16 or 32 encoding
    return json.loads(raw_bytes)

def _json_exporter(structured_data):
    return json.dumps(structured_data).encode()

_toolboxes = {
    code.PCS_KNOWN_HOSTS: FileToolbox(
        file_type_code=code.PCS_KNOWN_HOSTS,
        facade=None, # TODO needed for 'auth' and 'deauth' commands
        parser=_json_parser,
        exporter=_json_exporter,
        validator=None, # TODO needed for files syncing
        version_controller=None, # TODO needed for files syncing
    )
}

def for_file_type(file_type_code):
    return _toolboxes[file_type_code]
