# ruff: noqa: PLC0415 `import` should be at the top-level of a file
import argparse
import multiprocessing as mp
import os
import sys
import time
import unittest
from importlib import import_module
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


def parallel_run(
    tests: list[str],
    result_class,
    verbosity: int,
    vanilla: bool,
    last_slash: bool,
) -> bool:
    from pcs_test.tools.parallel_test_runner import (
        ParallelTestManager,
        aggregate_test_results,
    )

    manager = ParallelTestManager(result_class, verbosity=verbosity)

    with mp.Pool() as pool:
        start_time = time.perf_counter()
        results = pool.map(
            manager.run_test, tests, 10 if len(tests) > 99 else 1
        )
        end_time = time.perf_counter()

    test_result = aggregate_test_results(results)

    test_result.print_summary(
        end_time - start_time,
        vanilla=vanilla,
        last_slash=last_slash,
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


def _parse_args() -> argparse.Namespace:
    arg_parser = argparse.ArgumentParser(
        prog="pcs_test/suite",
        description="Script for running pcs tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:

  Assume that we are in pcs root directory and want to run tests, then we can run:

    pcs_test/suite                           - run all tests
    pcs_test/suite test_module               - run tests from test_module
    pcs_test/suite module.TestClass          - run tests from module.TestClass
    pcs_test/suite module.Class.test_method  - run specified test method
    pcs_test/suite path/to/test_file.py      - run tests from test_file.py
    pcs_test/suite --all-but test_module \\
        module.TestClass \\
        module.Class.test_method \\
        path/to/test_file.py                 - run all tests except the specified ones

""",
        allow_abbrev=False,
    )
    arg_parser.add_argument(
        "tests",
        nargs="*",
        help="A list of any number of test modules, classes and test methods",
    )
    arg_parser.add_argument(
        "-v",
        "--verbose",
        dest="verbosity",
        action="store_const",
        default=1,
        const=2,
        help="Verbose output - print test names",
    )
    arg_parser.add_argument(
        "--traditional-verbose",
        action="store_true",
        help="Use traditional verbose output",
    )
    tier_group = arg_parser.add_mutually_exclusive_group()
    tier_group.add_argument(
        "--tier0",
        dest="tier",
        action="store_const",
        const=0,
        help="Run only tier 0 tests",
    )
    tier_group.add_argument(
        "--tier1",
        dest="tier",
        action="store_const",
        const=1,
        help="Run only tier 1 tests",
    )
    arg_parser.add_argument(
        "--all-but",
        action="store_true",
        help="Run all tests except the specified ones",
    )
    arg_parser.add_argument(
        "--fast-info",
        action="store_true",
        help="Show a traceback immediately after the test fails",
    )
    arg_parser.add_argument(
        "--last-slash",
        action="store_true",
        help="Add trailing backslash to last fail in overview",
    )
    arg_parser.add_argument(
        "--list",
        action="store_true",
        dest="list_tests",
        help="List discovered tests without running them",
    )
    arg_parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel test execution",
    )
    arg_parser.add_argument(
        "--traceback-highlight",
        action="store_true",
        help="Highlight tracebacks in output",
    )
    arg_parser.add_argument(
        "--vanilla",
        action="store_true",
        help="Remove extra features, use vanilla test runner",
    )
    arg_parser.add_argument(
        "--installed",
        action="store_true",
        help="Test against installed pcs instead of local source",
    )
    arg_parser.add_argument(
        "--time",
        action="store_true",
        dest="measure_time",
        help="Measure each test execution time",
    )
    return arg_parser.parse_args()


def main() -> None:
    args = _parse_args()

    # explicitly set start method for multiprocessing to "fork"
    # https://docs.python.org/3.14/whatsnew/3.14.html#incompatible-changes
    mp.set_start_method(method="fork")
    if "BUNDLED_LIB_LOCATION" in os.environ:
        sys.path.insert(0, os.environ["BUNDLED_LIB_LOCATION"])

    if args.installed:
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

    explicitly_enumerated_tests = [
        prepare_test_name(test) for test in args.tests
    ]

    discovered_tests = discover_tests(
        explicitly_enumerated_tests, args.all_but, tier=args.tier
    )
    if args.list_tests:
        print("\n".join(sorted(discovered_tests)))
        print("{0} tests found".format(len(discovered_tests)))
        sys.exit()

    run_concurrently = not args.no_parallel and not args.measure_time
    tier1_fixtures_cleanup = run_tier1_fixtures(
        tier1_fixtures_needed(discovered_tests),
        run_concurrently=run_concurrently,
    )

    from pcs_test.tools.parallel_test_runner import VanillaTextTestResult

    ResultClass = VanillaTextTestResult
    if not args.vanilla:
        from pcs_test.tools.color_text_runner import get_text_test_result_class

        ResultClass = get_text_test_result_class(
            slash_last_fail_in_overview=args.last_slash,
            traditional_verbose=args.traditional_verbose,
            traceback_highlight=args.traceback_highlight,
            fast_info=args.fast_info,
            rich_format=(
                sys.stdout is not None
                and sys.stderr is not None
                and sys.stdout.isatty()
                and sys.stderr.isatty()
            ),
            measure_time=args.measure_time,
        )

    if run_concurrently:
        test_success = parallel_run(
            discovered_tests,
            ResultClass,
            args.verbosity,
            args.vanilla,
            args.last_slash,
        )
    else:
        test_success = non_parallel_run(
            discovered_tests, ResultClass, args.verbosity
        )
    tier1_fixtures_cleanup()
    if not test_success:
        sys.exit(1)


if __name__ == "__main__":
    main()
