import sys
#In package unittest there is no module mock before python 3.3. In python 3
#module mock is not imported by * because module mock is not imported in
#unittest/__init__.py
major, minor = sys.version_info[:2]
if major == 2 and minor == 6:
    #we use features that are missing before 2.7 (like test skipping,
    #assertRaises as context manager...) so we need unittest2
    from unittest2 import *
    import mock
else:
    from unittest import *
    try:
        import unittest.mock as mock
    except ImportError:
        import mock
del major, minor, sys

#backport of assert_not_called (new in version 3.5)
if not hasattr(mock.Mock, "assert_not_called"):
    def __assert_not_called(self, *args, **kwargs):
        if self.call_count != 0:
            msg = ("Expected '%s' to not have been called. Called %s times." %
                   (self._mock_name or 'mock', self.call_count))
            raise AssertionError(msg)
    mock.Mock.assert_not_called = __assert_not_called
