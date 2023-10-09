def _list2reason(test, exc_list):
    if exc_list and exc_list[-1][0] is test:
        return exc_list[-1][1]
    return None


def test_failed(test):
    # Borrowed from
    # https://stackoverflow.com/questions/4414234/getting-pythons-unittest-results-in-a-teardown-method/39606065#39606065
    # for Python versions 3.4 to 3.11
    # pylint: disable=protected-access
    if hasattr(test._outcome, "errors"):
        # Python 3.4 - 3.10 (These 2 methods have no side effects)
        result = test.defaultTestResult()
        test._feedErrorsToResult(result, test._outcome.errors)
    else:
        # Python 3.11+
        result = test._outcome.result
        if not hasattr(result, "errors") or not hasattr(result, "failures"):
            # test probably run by python concurrencytest module and therefore
            # we cannot get test results in a teardown method in Python 3.11+
            return None

    return _list2reason(test, result.errors) or _list2reason(
        test, result.failures
    )
