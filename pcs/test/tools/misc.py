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
from pcs.common.tools import is_string
from pcs.test.tools.pcs_unittest import (
    mock,
    skipUnless,
)


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

def cmp3(a, b):
    # python3 doesn't have the cmp function, this is an official workaround
    # https://docs.python.org/3.0/whatsnew/3.0.html#ordering-comparisons
    return (a > b) - (a < b)

def compare_version(a, b):
    if a[0] == b[0]:
        if a[1] == b[1]:
            return cmp3(a[2], b[2])
        return cmp3(a[1], b[1])
    return cmp3(a[0], b[0])

def is_minimum_pacemaker_version(cmajor, cminor, crev):
    output, dummy_retval = utils.run(["crm_mon", "--version"])
    pacemaker_version = output.split("\n")[0]
    r = re.compile(r"Pacemaker (\d+)\.(\d+)\.(\d+)")
    m = r.match(pacemaker_version)
    major = int(m.group(1))
    minor = int(m.group(2))
    rev = int(m.group(3))
    return compare_version((major, minor, rev), (cmajor, cminor, crev)) > -1

def is_minimum_pacemaker_features(cmajor, cminor, crev):
    output, dummy_retval = utils.run(["pacemakerd", "--features"])
    features_version = output.split("\n")[1]
    r = re.compile(r"Supporting v(\d+)\.(\d+)\.(\d+):")
    m = r.search(features_version)
    major = int(m.group(1))
    minor = int(m.group(2))
    rev = int(m.group(3))
    return compare_version((major, minor, rev), (cmajor, cminor, crev)) > -1

def skip_unless_pacemaker_version(version_tuple, feature):
    return skipUnless(
        is_minimum_pacemaker_version(*version_tuple),
        "Pacemaker version is too old (must be >= {version}) to test {feature}"
            .format(
                version=".".join([str(x) for x in version_tuple]),
                feature=feature
            )
    )

def skip_unless_pacemaker_features(version_tuple, feature):
    return skipUnless(
        is_minimum_pacemaker_features(*version_tuple),
        "Pacemaker must support feature set version {version} to test {feature}"
            .format(
                version=".".join([str(x) for x in version_tuple]),
                feature=feature
            )
    )

skip_unless_pacemaker_supports_bundle = skip_unless_pacemaker_features(
    (3, 0, 12),
    "bundle resources"
)

def skip_unless_pacemaker_supports_systemd():
    output, dummy_retval = utils.run(["pacemakerd", "--features"])
    return skipUnless(
        "systemd" in output,
        "Pacemaker does not support systemd resources"
    )

def create_patcher(target_prefix_or_module):
    """
    Return function for patching tests with preconfigured target prefix
    string|module target_prefix_or_module could be:
        * a prefix for patched names. Typicaly tested module:
            "pcs.lib.commands.booth"
        * a (imported) module: pcs.lib.cib
        Between prefix and target is "." (dot)
    """
    prefix = target_prefix_or_module
    if not is_string(target_prefix_or_module):
        prefix = target_prefix_or_module.__name__

    def patch(target, *args, **kwargs):
        return mock.patch("{0}.{1}".format(prefix, target), *args, **kwargs)
    return patch

def outdent(text):
    line_list = text.splitlines()
    smallest_indentation = min([
        len(line) - len(line.lstrip(" "))
        for line in line_list if line
    ])
    return "\n".join([line[smallest_indentation:] for line in line_list])

def create_setup_patch_mixin(module_specification_or_patcher):
    """
    Configure and return SetupPatchMixin

    SetupPatchMixin add method 'setup_patch' to a test case.

    Method setup_patch takes name that should be patched in destination module
    (see module_specification_or_patcher). Method provide cleanup after test.
    It is expected to be used in 'setUp' method but should work inside test as
    well.

    string|callable module_specification_or_patcher can be
       * callable patcher created via create_patcher:
         create_patcher("pcs.lib.cib")
       * name of module: "pcs.lib.cib"
       * (imported) module: pcs.lib.cib
         Note that this must be not a callable (can be done via
         sys.modules[__name__] = something_callable. If is a callable use name
         of the module instead.
    """
    if callable(module_specification_or_patcher):
        patch_module = module_specification_or_patcher
    else:
        patch_module = create_patcher(module_specification_or_patcher)

    class SetupPatchMixin(object):
        def setup_patch(self, target_suffix, *args, **kwargs):
            patcher = patch_module(target_suffix, *args, **kwargs)
            self.addCleanup(patcher.stop)
            return patcher.start()
    return SetupPatchMixin
