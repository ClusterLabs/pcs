def _list2reason(test, exc_list):
    if exc_list and exc_list[-1][0] is test:
        return exc_list[-1][1]

def test_failed(test):
    # Borrowed from
    # https://stackoverflow.com/questions/4414234/getting-pythons-unittest-results-in-a-teardown-method/39606065#39606065
    # for Python versions 2.7 to 3.6
    if hasattr(test, '_outcome'):  # Python 3.4+
        # these 2 methods have no side effects
        result = test.defaultTestResult()
        test._feedErrorsToResult(result, test._outcome.errors)
    else:  # Python 3.2 - 3.3 or 3.0 - 3.1 and 2.7
        result = getattr(
            test,
            '_outcomeForDoCleanups', test._resultForDoCleanups
        )

    return (
        _list2reason(test, result.errors)
        or
        _list2reason(test, result.failures)
    )
