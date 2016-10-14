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

#backport of assert_not_called (new in version 3.5)
if not hasattr(mock.Mock, "assert_not_called"):
    def __assert_not_called(self, *args, **kwargs):
        if self.call_count != 0:
            msg = ("Expected '%s' to not have been called. Called %s times." %
                   (self._mock_name or 'mock', self.call_count))
            raise AssertionError(msg)
    mock.Mock.assert_not_called = __assert_not_called


if not hasattr(mock, "mock_open"):
    def create_mock_open(MagicMock, DEFAULT, inPy3k):
        """
        Backport mock_open for older mock versions.
        Backport is taken from mock package. Original code is slightly adapted:
         * code is covered by create_mock_open
         * MagicMock, DEFAULT, and inPy3k flag was originally module globals
         * file_spec was originally plain value (and in mock_open referenced as
           global) but we want keep namespace of this module as clean as
           possible so now is file_spec encapsulated.
        """
        file_spec = [None]

        def _iterate_read_data(read_data):
            # Helper for mock_open:
            # Retrieve lines from read_data via a generator so that separate
            # calls to readline, read, and readlines are properly interleaved
            data_as_list = ['{0}\n'.format(l) for l in read_data.split('\n')]

            if data_as_list[-1] == '\n':
                # If the last line ended in a newline, the list comprehension
                #will #have an extra entry that's just a newline.  Remove this.
                data_as_list = data_as_list[:-1]
            else:
                # If there wasn't an extra newline by itself, then the file
                # being emulated doesn't have a newline to end the last line
                # remove the newline that our naive format() added
                data_as_list[-1] = data_as_list[-1][:-1]

            for line in data_as_list:
                yield line

        def mock_open(mock=None, read_data=''):
            """
            A helper function to create a mock to replace the use of `open`. It
            works for `open` called directly or used as a context manager.

            The `mock` argument is the mock object to configure. If `None` (the
            default) then a `MagicMock` will be created for you, with the API
            limited to methods or attributes available on standard file
            handles.

            `read_data` is a string for the `read` methoddline`, and
            `readlines` of the file handle to return.  This is an empty string
            by default.
            """
            def _readlines_side_effect(*args, **kwargs):
                if handle.readlines.return_value is not None:
                    return handle.readlines.return_value
                return list(_state[0])

            def _read_side_effect(*args, **kwargs):
                if handle.read.return_value is not None:
                    return handle.read.return_value
                return ''.join(_state[0])

            def _readline_side_effect():
                if handle.readline.return_value is not None:
                    while True:
                        yield handle.readline.return_value
                for line in _state[0]:
                    yield line

            if file_spec[0] is None:
                # set on first use
                if inPy3k:
                    import _io
                    file_spec[0] = list(
                        set(dir(_io.TextIOWrapper))
                            .union(set(dir(_io.BytesIO)))
                    )
                else:
                    file_spec[0] = file

            if mock is None:
                mock = MagicMock(name='open', spec=open)

            handle = MagicMock(spec=file_spec[0])
            handle.__enter__.return_value = handle

            _state = [_iterate_read_data(read_data), None]

            handle.write.return_value = None
            handle.read.return_value = None
            handle.readline.return_value = None
            handle.readlines.return_value = None

            handle.read.side_effect = _read_side_effect
            _state[1] = _readline_side_effect()
            handle.readline.side_effect = _state[1]
            handle.readlines.side_effect = _readlines_side_effect

            def reset_data(*args, **kwargs):
                _state[0] = _iterate_read_data(read_data)
                if handle.readline.side_effect == _state[1]:
                    # Only reset the side effect if the user hasn't overridden
                    #it.
                    _state[1] = _readline_side_effect()
                    handle.readline.side_effect = _state[1]
                return DEFAULT

            mock.side_effect = reset_data
            mock.return_value = handle
            return mock
        return mock_open

    mock.mock_open = create_mock_open(
        mock.MagicMock,
        mock.DEFAULT,
        inPy3k=(major==3),
    )
    del create_mock_open

def ensure_raise_from_iterable_side_effect():
    """
    Adjust mock.Mock to raise when side_effect is iterable and efect item
    applied in the current call is exception (class or instance) and this
    exception is simply returned (in older version of mock).
    """
    def create_new_call(old_call, inPy3k):
        # pylint: disable=old-style-class
        class OldStyleClass:
            pass
        ClassTypes = (type,) if inPy3k else (type, type(OldStyleClass))

        def is_exception(obj):
            return isinstance(obj, BaseException) or (
                isinstance(obj, ClassTypes)
                and
                issubclass(obj, BaseException)
            )

        def new_call(_mock_self, *args, **kwargs):
            """
            Wrap original call.
            If side_effect is itterable and result is an exception then we
            raise this exception. Newer versions of mock it makes itself (so
            in this case exception is raised from old_call) but we need it
            for the old versions as well.
            """
            call_result = old_call(_mock_self, *args, **kwargs)
            try:
                iter(_mock_self.side_effect)
            except TypeError:
                return call_result

            if is_exception(call_result):
                raise call_result
            return call_result

        return new_call
    mock.Mock.__call__ = create_new_call(mock.Mock.__call__, inPy3k=(major==3))
ensure_raise_from_iterable_side_effect()

del major, minor, sys
