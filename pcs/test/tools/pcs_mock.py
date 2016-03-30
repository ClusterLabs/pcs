try:
    import unittest.mock as mock
except ImportError:
    import mock

if not hasattr(mock.Mock, "assert_not_called"):
    def __assert_not_called(self, *args, **kwargs):
        if self.call_count != 0:
            msg = ("Expected '%s' to not have been called. Called %s times." %
                   (self._mock_name or 'mock', self.call_count))
            raise AssertionError(msg)
    mock.Mock.assert_not_called = __assert_not_called

