#!/usr/bin/env python
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import sys
import os.path

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
)))
sys.path.insert(0, PACKAGE_DIR)

from pcs.test.tools import pcs_unittest as unittest

def prepare_test_name(test_name):
    """
    Sometimes we have test easy accessible with fs path format like:
    "pcs/test/test_node"
    but loader need it in module path format like:
    "pcs.test.test_node"
    so is practical accept fs path format and prepare it for loader
    """
    return test_name.replace("/", ".")

def tests_from_suite(test_candidate):
    if isinstance(test_candidate, unittest.TestCase):
        return [test_candidate.id()]
    test_id_list = []
    for test in test_candidate:
        test_id_list.extend(tests_from_suite(test))
    return test_id_list

def autodiscover_tests():
    #...Find all the test modules by recursing into subdirectories from the
    #specified start directory...
    #...All test modules must be importable from the top level of the project.
    #If the start directory is not the top level directory then the top level
    #directory must be specified separately...
    #So test are loaded from PACKAGE_DIR/pcs but their names starts with "pcs."
    return unittest.TestLoader().discover(
        start_dir=os.path.join(PACKAGE_DIR, "pcs"),
        pattern='test_*.py',
        top_level_dir=PACKAGE_DIR,
    )

def discover_tests(explicitly_enumerated_tests, exclude_enumerated_tests=False):
    if not explicitly_enumerated_tests:
        return autodiscover_tests()
    if exclude_enumerated_tests:
        return unittest.TestLoader().loadTestsFromNames([
            test_name for test_name in tests_from_suite(autodiscover_tests())
            if test_name not in explicitly_enumerated_tests
        ])
    return unittest.TestLoader().loadTestsFromNames(explicitly_enumerated_tests)


explicitly_enumerated_tests = [
    prepare_test_name(arg) for arg in sys.argv[1:] if arg not in (
        "-v",
        "--vanilla",
        "--no-color", #deprecated, use --vanilla instead
        "--all-but",
        "--last-slash",
        "--traditional-verbose",
        "--traceback-highlight",
    )
]

if "--no-color" in sys.argv:
    print("DEPRECATED: --no-color is deprecated, use --vanilla instead")

use_improved_result_class = (
    sys.stdout.isatty()
    and
    sys.stderr.isatty()
    and (
        "--vanilla" not in sys.argv
        and
        "--no-color" not in sys.argv #deprecated, use --vanilla instead
    )
)

resultclass = unittest.TextTestResult
if use_improved_result_class:
    from pcs.test.tools.color_text_runner import get_text_test_result_class
    resultclass = get_text_test_result_class(
        slash_last_fail_in_overview=("--last-slash" in sys.argv),
        traditional_verbose=("--traditional-verbose" in sys.argv),
        traceback_highlight=("--traceback-highlight" in sys.argv),
    )

testRunner = unittest.TextTestRunner(
    verbosity=2 if "-v" in sys.argv else 1,
    resultclass=resultclass
)
test_result =  testRunner.run(
    discover_tests(explicitly_enumerated_tests, "--all-but" in sys.argv)
)
if not test_result.wasSuccessful():
    sys.exit(1)

# assume that we are in pcs root dir
#
# run all tests:
# ./pcs/test/suite.py
#
# run with printing name of runned test:
# pcs/test/suite.py -v
#
# run specific test:
# IMPORTANT: in 2.6 module.class.method doesn't work but module.class works fine
# pcs/test/suite.py pcs.test.test_acl.ACLTest -v
# pcs/test/suite.py pcs.test.test_acl.ACLTest.testAutoUpgradeofCIB
#
# run all test except some:
# pcs/test/suite.py pcs.test_acl.ACLTest --all-but
#
# for remove extra features even if sys.stdout is attached to terminal
# pcs/test/suite.py --vanilla
