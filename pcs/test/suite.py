#!/usr/bin/env python

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import sys
import os.path

major, minor = sys.version_info[:2]
if major == 2 and minor == 6:
    import unittest2 as unittest
else:
    import unittest


PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
)))

def put_package_to_path():
    sys.path.insert(0, PACKAGE_DIR)

def discover_tests(test_name_list):
    loader = unittest.TestLoader()
    if test_name_list:
        return loader.loadTestsFromNames(test_name_list)
    return loader.discover(PACKAGE_DIR, pattern='test_*.py')

def run_tests(tests, verbose=False, color=False):
    resultclass = unittest.runner.TextTestResult
    if color:
        from pcs.test.tools.color_text_runner import ColorTextTestResult
        resultclass = ColorTextTestResult

    testRunner = unittest.runner.TextTestRunner(
        verbosity=2 if verbose else 1,
        resultclass=resultclass
    )
    testRunner.run(tests)

put_package_to_path()
tests = discover_tests([
    arg for arg in sys.argv[1:] if arg not in ('-v', '--color')
])
run_tests(
    tests,
    verbose='-v' in sys.argv,
    color="--color" in sys.argv,
)

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
# pcs/test/suite.py test_acl.ACLTest -v
# pcs/test/suite.py test_acl.ACLTest.testAutoUpgradeofCIB
#
# for colored test report
# pcs/test/suite.py --color
