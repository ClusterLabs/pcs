import sys

# pylint: disable=unused-wildcard-import
# pylint: disable=wildcard-import
from pycurl import *  # noqa: F403

# This package defines constants which are not present in some older versions
# of pycurl but pcs needs to use them

required_constants = {
    "PROTOCOLS": 181,
    "PROTO_HTTPS": 2,
    "E_OPERATION_TIMEDOUT": 28,
    # these are types of debug messages
    # see https://curl.haxx.se/libcurl/c/CURLOPT_DEBUGFUNCTION.html
    "DEBUG_TEXT": 0,
    "DEBUG_HEADER_IN": 1,
    "DEBUG_HEADER_OUT": 2,
    "DEBUG_DATA_IN": 3,
    "DEBUG_DATA_OUT": 4,
    "DEBUG_SSL_DATA_IN": 5,
    "DEBUG_SSL_DATA_OUT": 6,
    "DEBUG_END": 7,
}

__current_module = sys.modules[__name__]

for constant, value in required_constants.items():
    if not hasattr(__current_module, constant):
        setattr(__current_module, constant, value)
