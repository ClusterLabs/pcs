#!/usr/bin/env python3
import importlib
import os
import sys
import unittest

try:
    from testtools import ConcurrentTestSuite
    import concurrencytest

    can_concurrency = True
except ImportError:
    can_concurrency = False


# pylint: disable=redefined-outer-name, unused-argument, invalid-name
# pylint: disable=ungrouped-imports

if "BUNDLED_LIB_LOCATION" in os.environ:
    sys.path.insert(0, os.environ["BUNDLED_LIB_LOCATION"])

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if "--installed" in sys.argv:
    sys.path.append(PACKAGE_DIR)

    from pcs import settings

    if settings.pcs_bundled_pacakges_dir not in sys.path:
        sys.path.insert(0, settings.pcs_bundled_pacakges_dir)

    from pcs_test.tools import pcs_runner

    pcs_runner.test_installed = True
else:
    sys.path.insert(0, PACKAGE_DIR)


def prepare_test_name(test_name):
    """
    Sometimes we have test easy accessible with fs path format like:
    "pcs_test/tier0/test_node"
    but loader need it in module path format like:
    "pcs_test.tier0.test_node"
    so is practical accept fs path format and prepare it for loader

    Sometimes name could include the .py extension:
    "pcs_test/tier0/test_node.py"
    in such cause is extension removed
    """
    candidate = test_name.replace("/", ".")
    py_extension = ".py"
    if not candidate.endswith(py_extension):
        return candidate
    try:
        importlib.import_module(candidate)
        return candidate
    except ImportError:
        return candidate[: -len(py_extension)]


def tests_from_suite(test_candidate):
    if isinstance(test_candidate, unittest.TestCase):
        return [test_candidate.id()]
    test_id_list = []
    for test in test_candidate:
        test_id_list.extend(tests_from_suite(test))
    return test_id_list


def autodiscover_tests(tier=None):
    # ...Find all the test modules by recursing into subdirectories from the
    # specified start directory...
    # ...All test modules must be importable from the top level of the project.
    # If the start directory is not the top level directory then the top level
    # directory must be specified separately...
    # So test are loaded from PACKAGE_DIR/pcs but their names starts with "pcs."
    test_dir = os.path.join(PACKAGE_DIR, "pcs_test")
    if tier is not None:
        test_dir = os.path.join(test_dir, f"tier{tier}")
    return unittest.TestLoader().discover(
        start_dir=test_dir,
        pattern="test_*.py",
        top_level_dir=PACKAGE_DIR,
    )


def discover_tests(
    explicitly_enumerated_tests, exclude_enumerated_tests=False, tier=None
):
    if not explicitly_enumerated_tests:
        return autodiscover_tests(tier=tier)
    if exclude_enumerated_tests:
        return unittest.TestLoader().loadTestsFromNames(
            [
                test_name
                for test_name in tests_from_suite(autodiscover_tests(tier=tier))
                if test_name not in explicitly_enumerated_tests
            ]
        )
    return unittest.TestLoader().loadTestsFromNames(explicitly_enumerated_tests)


run_concurrently = can_concurrency and "--no-parallel" not in sys.argv

explicitly_enumerated_tests = [
    prepare_test_name(arg)
    for arg in sys.argv[1:]
    if arg
    not in (
        "-v",
        "--all-but",
        "--fast-info",  # show a traceback immediatelly after the test fails
        "--last-slash",
        "--list",
        "--no-parallel",
        "--traceback-highlight",
        "--traditional-verbose",
        "--vanilla",
        "--installed",
        "--tier0",
        "--tier1",
    )
]

tier = None
if "--tier0" in sys.argv:
    tier = 0
elif "--tier1" in sys.argv:
    tier = 1

discovered_tests = discover_tests(
    explicitly_enumerated_tests, "--all-but" in sys.argv, tier=tier
)
if "--list" in sys.argv:
    test_list = tests_from_suite(discovered_tests)
    print("\n".join(sorted(test_list)))
    print("{0} tests found".format(len(test_list)))
    sys.exit()

tests_to_run = discovered_tests
if run_concurrently:
    tests_to_run = ConcurrentTestSuite(
        discovered_tests,
        concurrencytest.fork_for_tests(),
    )


use_improved_result_class = (
    sys.stdout.isatty() and sys.stderr.isatty() and "--vanilla" not in sys.argv
)

resultclass = unittest.TextTestResult
if use_improved_result_class:
    from pcs_test.tools.color_text_runner import get_text_test_result_class

    resultclass = get_text_test_result_class(
        slash_last_fail_in_overview=("--last-slash" in sys.argv),
        traditional_verbose=(
            "--traditional-verbose" in sys.argv
            or
            # temporary workaround - our verbose writer is not compatible with
            # running tests in parallel, use our traditional writer
            (run_concurrently and "-v" in sys.argv)
        ),
        traceback_highlight=("--traceback-highlight" in sys.argv),
        fast_info=("--fast-info" in sys.argv),
    )

testRunner = unittest.TextTestRunner(
    verbosity=2 if "-v" in sys.argv else 1, resultclass=resultclass
)
test_result = testRunner.run(tests_to_run)
if not test_result.wasSuccessful():
    sys.exit(1)

# assume that we are in pcs root dir
#
# run all tests:
# ./pcs_test/suite.py
#
# run with printing name of runned test:
# pcs_test/suite.py -v
#
# run specific test:
# IMPORTANT: in 2.6 module.class.method doesn't work but module.class works fine
# pcs_test/suite.py pcs_test.tier0.test_acl.ACLTest -v
# pcs_test/suite.py pcs_test.tier0.test_acl.ACLTest.testAutoUpgradeofCIB
#
# run all test except some:
# pcs_test/suite.py pcs_test.tier0.test_acl.ACLTest --all-but
#
# for remove extra features even if sys.stdout is attached to terminal
# pcs_test/suite.py --vanilla
