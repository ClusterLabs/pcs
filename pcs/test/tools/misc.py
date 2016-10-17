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
from pcs.test.tools.pcs_unittest import mock


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
        raise AssertionError(
            "strings not equal:\n{0}".format(prepare_diff(b, a))
        )

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

def create_patcher(target_prefix):
    """
    Return function for patching tests with preconfigured target prefix
    string target_prefix is prefix for patched names. Typicaly tested module
    like for example "pcs.lib.commands.booth". Between target_prefix and target
    is "." (dot)
    """
    def patch(target, *args, **kwargs):
        return mock.patch(
            "{0}.{1}".format(target_prefix, target), *args, **kwargs
        )
    return patch

def outdent(text):
    line_list = text.splitlines()
    smallest_indentation = min([
        len(line) - len(line.lstrip(" "))
        for line in line_list if line
    ])
    return "\n".join([line[smallest_indentation:] for line in line_list])
