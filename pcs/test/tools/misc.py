from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import difflib
import os.path
import re

from pcs import utils


testdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def prepare_diff(first, second):
    """
    Return a string containing a diff of first and second
    """
    return "".join(
        difflib.Differ().compare(first.splitlines(1), second.splitlines(1))
    )

def ac(a,b):
    """
    Compare the actual output 'a' and an expected output 'b', print diff b a
    """
    if a != b:
        print("")
        print(prepare_diff(b, a))
        assert False, [a]

def get_test_resource(name):
    """Return full path to a test resource file specified by name"""
    return os.path.join(testdir, "resources", name)

def is_minimum_pacemaker_version(cmajor, cminor, crev):
    output, dummy_retval = utils.run(["crm_mon", "--version"])
    pacemaker_version = output.split("\n")[0]
    r = re.compile(r"Pacemaker (\d+)\.(\d+)\.(\d+)")
    m = r.match(pacemaker_version)
    major = int(m.group(1))
    minor = int(m.group(2))
    rev = int(m.group(3))
    return (
        major > cmajor
        or
        (major == cmajor and minor > cminor)
        or
        (major == cmajor and minor == cminor and rev >= crev)
    )
