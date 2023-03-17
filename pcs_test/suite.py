import os
import sys
import time
import unittest
from importlib import import_module
from threading import Thread

try:
    import concurrencytest
    from testtools import ConcurrentTestSuite

    can_concurrency = True
except ImportError:
    can_concurrency = False


PACKAGE_DIR = os.path.realpath(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


# pylint: disable=redefined-outer-name


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
        import_module(candidate)
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


def tier1_fixtures_needed(test_list):
    fixture_modules = set(
        [
            "pcs_test.tier1.legacy.test_constraints",
            "pcs_test.tier1.legacy.test_resource",
            "pcs_test.tier1.legacy.test_stonith",
        ]
    )
    fixtures_needed = set()
    for test_name in tests_from_suite(test_list):
        for module in fixture_modules:
            if test_name.startswith(module):
                fixtures_needed.add(module)
        if fixture_modules == fixtures_needed:
            break
    return fixtures_needed


def run_tier1_fixtures(modules, run_concurrently=True):
    fixture_instances = []
    for mod in modules:
        tmp_mod = import_module(mod)
        fixture_instances.append(tmp_mod.CIB_FIXTURE)
        del tmp_mod

    print("Preparing tier1 fixtures...")
    for mod in modules:
        print(f"  * {mod}")
    time_start = time.time()
    if run_concurrently:
        thread_list = set()
        for instance in fixture_instances:
            thread = Thread(target=instance.set_up)
            thread.daemon = True
            thread.start()
            thread_list.add(thread)
        timeout_counter = 30  # 30 * 10s = 5min
        while thread_list:
            if timeout_counter < 0:
                raise AssertionError("Fixture threads seem to be stuck :(")
            thread = thread_list.pop()
            thread.join(timeout=10)
            sys.stdout.write(". ")
            sys.stdout.flush()
            timeout_counter -= 1
            if thread.is_alive():
                thread_list.add(thread)

    else:
        for instance in fixture_instances:
            instance.set_up()
    time_stop = time.time()
    time_taken = time_stop - time_start
    sys.stdout.write("Tier1 fixtures prepared in %.3fs\n" % (time_taken))
    sys.stdout.flush()

    def cleanup():
        print("Cleaning tier1 fixtures...", end=" ")
        for instance in fixture_instances:
            instance.clean_up()
        print("done")

    return cleanup


def main():
    # pylint: disable=import-outside-toplevel
    if "BUNDLED_LIB_LOCATION" in os.environ:
        sys.path.insert(0, os.environ["BUNDLED_LIB_LOCATION"])

    if "--installed" in sys.argv:
        sys.path.append(PACKAGE_DIR)

        from pcs import settings

        if settings.pcs_bundled_packages_dir not in sys.path:
            sys.path.insert(0, settings.pcs_bundled_packages_dir)

        from pcs_test.tools import pcs_runner

        pcs_runner.test_installed = True
    else:
        sys.path.insert(0, PACKAGE_DIR)
        from pcs import settings

        settings.pcs_data_dir = os.path.join(PACKAGE_DIR, "data")

    measure_test_time = "--time" in sys.argv
    run_concurrently = (
        can_concurrency
        and "--no-parallel" not in sys.argv
        and not measure_test_time
    )

    explicitly_enumerated_tests = [
        prepare_test_name(arg)
        for arg in sys.argv[1:]
        if arg
        not in (
            "-v",
            "--all-but",
            "--fast-info",  # show a traceback immediately after the test fails
            "--last-slash",
            "--list",
            "--no-parallel",
            "--traceback-highlight",
            "--traditional-verbose",
            "--vanilla",
            "--installed",
            "--tier0",
            "--tier1",
            "--time",
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
    tier1_fixtures_cleanup = run_tier1_fixtures(
        tier1_fixtures_needed(tests_to_run), run_concurrently=run_concurrently
    )
    if run_concurrently:
        tests_to_run = ConcurrentTestSuite(
            discovered_tests,
            concurrencytest.fork_for_tests(),
        )

    ResultClass = unittest.TextTestResult
    if "--vanilla" not in sys.argv:
        from pcs_test.tools.color_text_runner import get_text_test_result_class

        ResultClass = get_text_test_result_class(
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
            rich_format=(
                sys.stdout is not None
                and sys.stderr is not None
                and sys.stdout.isatty()
                and sys.stderr.isatty()
            ),
            measure_time=("--time" in sys.argv),
        )

    test_runner = unittest.TextTestRunner(
        verbosity=2 if "-v" in sys.argv else 1, resultclass=ResultClass
    )
    test_result = test_runner.run(tests_to_run)
    tier1_fixtures_cleanup()
    if not test_result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    main()


# assume that we are in pcs root dir
#
# run all tests:
# ./pcs_test/suite.py
#
# run and print tests' names:
# pcs_test/suite.py -v
#
# run specific test:
# IMPORTANT: in 2.6 module.class.method doesn't work but module.class works fine
# pcs_test/suite.py pcs_test.tier0.test_acl.ACLTest -v
# pcs_test/suite.py pcs_test.tier0.test_acl.ACLTest.testAutoUpgradeofCIB
#
# run all tests except some:
# pcs_test/suite.py pcs_test.tier0.test_acl.ACLTest --all-but
#
# remove extra features
# pcs_test/suite.py --vanilla
