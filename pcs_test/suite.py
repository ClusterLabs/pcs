# ruff: noqa: PLC0415 `import` should be at the top-level of a file
import os
import sys
import time
import unittest
from importlib import import_module
from multiprocessing import Pool
from threading import Thread
from typing import Callable, Optional, Union

PACKAGE_DIR = os.path.realpath(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


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


def tests_from_suite(
    test_candidate: Union[unittest.TestCase, unittest.TestSuite],
) -> list[str]:
    if isinstance(test_candidate, unittest.TestCase):
        return [test_candidate.id()]
    test_id_list = []
    for test in test_candidate:
        test_id_list.extend(tests_from_suite(test))
    return test_id_list


def autodiscover_tests(tier: Optional[int] = None) -> unittest.TestSuite:
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
    explicitly_enumerated_tests: list[str],
    exclude_enumerated_tests: bool = False,
    tier: Optional[int] = None,
) -> list[str]:
    if not explicitly_enumerated_tests:
        return tests_from_suite(autodiscover_tests(tier=tier))
    if exclude_enumerated_tests:
        return [
            test_name
            for test_name in tests_from_suite(autodiscover_tests(tier=tier))
            if test_name not in explicitly_enumerated_tests
        ]

    return tests_from_suite(
        unittest.defaultTestLoader.loadTestsFromNames(
            sorted(set(explicitly_enumerated_tests))
        )
    )


def tier1_fixtures_needed(test_list: list[str]) -> set[str]:
    fixture_modules = {
        "pcs_test.tier1.legacy.test_constraints",
        "pcs_test.tier1.legacy.test_resource",
        "pcs_test.tier1.legacy.test_stonith",
    }
    fixtures_needed = set()
    for test_name in test_list:
        for module in fixture_modules:
            if test_name.startswith(module):
                fixtures_needed.add(module)
        if fixture_modules == fixtures_needed:
            break
    return fixtures_needed


def run_tier1_fixtures(
    modules: set[str], run_concurrently: bool = True
) -> Callable[[], None]:
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


def parallel_run(tests: list[str], result_class, verbosity: int) -> bool:
    # pylint: disable=import-outside-toplevel
    from pcs_test.tools.parallel_test_runner import (
        ParallelTestManager,
        aggregate_test_results,
    )

    manager = ParallelTestManager(result_class, verbosity=verbosity)

    with Pool() as pool:
        start_time = time.perf_counter()
        results = pool.map(
            manager.run_test, tests, 10 if len(tests) > 99 else 1
        )
        end_time = time.perf_counter()

    test_result = aggregate_test_results(results)

    test_result.print_summary(
        end_time - start_time,
        vanilla="--vanilla" in sys.argv,
        last_slash="--last-slash" in sys.argv,
    )
    return test_result.was_successful


def non_parallel_run(tests: list[str], result_class, verbosity: int) -> bool:
    test_runner = unittest.TextTestRunner(
        verbosity=verbosity,
        resultclass=result_class,
    )
    tests_to_run = unittest.defaultTestLoader.loadTestsFromNames(tests)
    test_result = test_runner.run(tests_to_run)

    return test_result.wasSuccessful()


def main() -> None:
    # pylint: disable=import-outside-toplevel
    # pylint: disable=too-many-locals
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
        print("\n".join(sorted(discovered_tests)))
        print("{0} tests found".format(len(discovered_tests)))
        sys.exit()

    run_concurrently = "--no-parallel" not in sys.argv and not measure_test_time
    tier1_fixtures_cleanup = run_tier1_fixtures(
        tier1_fixtures_needed(discovered_tests),
        run_concurrently=run_concurrently,
    )

    from pcs_test.tools.parallel_test_runner import VanillaTextTestResult

    ResultClass = VanillaTextTestResult
    if "--vanilla" not in sys.argv:
        from pcs_test.tools.color_text_runner import get_text_test_result_class

        ResultClass = get_text_test_result_class(
            slash_last_fail_in_overview=("--last-slash" in sys.argv),
            traditional_verbose=("--traditional-verbose" in sys.argv),
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

    verbosity = 2 if "-v" in sys.argv else 1
    if run_concurrently:
        test_success = parallel_run(discovered_tests, ResultClass, verbosity)
    else:
        test_success = non_parallel_run(
            discovered_tests, ResultClass, verbosity
        )
    tier1_fixtures_cleanup()
    if not test_success:
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
