from pcs.common.file import (
    FileAlreadyExists,
    RawFileError,
    RawFileInterface,
)

CALL_TYPE_RAW_FILE_EXISTS = "CALL_TYPE_RAW_FILE_EXISTS"
CALL_TYPE_RAW_FILE_READ = "CALL_TYPE_RAW_FILE_READ"
CALL_TYPE_RAW_FILE_REMOVE = "CALL_TYPE_RAW_FILE_REMOVE"
CALL_TYPE_RAW_FILE_WRITE = "CALL_TYPE_RAW_FILE_WRITE"


class RawFileCall:
    def __init__(self, file_type_code, path):
        self.file_type_code = file_type_code
        self.path = path

    def _repr(self, method):
        return "<RawFile.{_method}> file_type_code={ftc} path={path}".format(
            _method=method, ftc=self.file_type_code, path=self.path
        )


class RawFileExistsCall(RawFileCall):
    type = CALL_TYPE_RAW_FILE_EXISTS

    def __init__(self, file_type_code, path, exists=True):
        super().__init__(file_type_code, path)
        self.exists = exists

    def __repr__(self):
        return super()._repr("exists")


class RawFileReadCall(RawFileCall):
    type = CALL_TYPE_RAW_FILE_READ

    def __init__(self, file_type_code, path, content=None, exception_msg=None):
        if content is None and exception_msg is None:
            raise RuntimeError(
                "Both 'content' and 'exception_msg' cannot be None"
            )
        if content is not None and exception_msg is not None:
            raise RuntimeError(
                "Both 'content' and 'exception_msg' cannot be set"
            )
        super().__init__(file_type_code, path)
        self.content = content
        self.exception_msg = exception_msg

    def __repr__(self):
        return super()._repr("read")


class RawFileWriteCall(RawFileCall):
    type = CALL_TYPE_RAW_FILE_WRITE

    def __init__(
        self,
        file_type_code,
        path,
        file_data,
        can_overwrite=False,
        already_exists=False,
        exception_msg=None,
        exception_action=None,
    ):
        super().__init__(file_type_code, path)
        self.file_data = file_data
        self.can_overwrite = can_overwrite
        self.already_exists = already_exists
        self.exception_msg = exception_msg
        self.exception_action = exception_action

    def __repr__(self):
        return super()._repr("write")


class RawFileRemoveCall(RawFileCall):
    type = CALL_TYPE_RAW_FILE_REMOVE

    def __init__(
        self,
        file_type_code,
        path,
        fail_if_file_not_found=True,
        exception_msg=None,
        file_not_found_exception=False,
    ):
        super().__init__(file_type_code, path)
        self.fail_if_file_not_found = fail_if_file_not_found
        self.exception_msg = exception_msg
        self.file_not_found_exception = file_not_found_exception

    def __repr__(self):
        return super()._repr("remove")


def _check_file_type_code_and_path(
    method, real_metadata, call_index, expected_call
):
    if real_metadata.file_type_code != expected_call.file_type_code:
        raise AssertionError(
            (
                "Trying to call RawFile.{method} (call no. {index}) "
                "with RawFile constructed for '{real_ftc}' but it is "
                "expected it to be constructed for '{expected_ftc}'"
            ).format(
                expected_ftc=expected_call.file_type_code,
                index=call_index,
                method=method,
                real_ftc=real_metadata.file_type_code,
            )
        )

    if real_metadata.path != expected_call.path:
        raise AssertionError(
            (
                "Trying to call RawFile.{method} (call no. {index}) "
                "for '{real_ftc}', real path is '{real_path}' but "
                "expected path is '{expected_path}'"
            ).format(
                expected_path=expected_call.path,
                index=call_index,
                method=method,
                real_ftc=real_metadata.file_type_code,
                real_path=real_metadata.path,
            )
        )


def get_raw_file_mock(call_queue):
    class RawFileMock(RawFileInterface):
        def exists(self):
            call_index, expected_call = call_queue.take(
                CALL_TYPE_RAW_FILE_EXISTS
            )
            _check_file_type_code_and_path(
                "exists", self.metadata, call_index, expected_call
            )
            return expected_call.exists

        def read(self):
            call_index, expected_call = call_queue.take(CALL_TYPE_RAW_FILE_READ)
            _check_file_type_code_and_path(
                "read", self.metadata, call_index, expected_call
            )
            if expected_call.exception_msg:
                raise RawFileError(
                    self.metadata,
                    RawFileError.ACTION_READ,
                    expected_call.exception_msg,
                )
            return expected_call.content

        def write(self, file_data, can_overwrite=False):
            call_index, expected_call = call_queue.take(
                CALL_TYPE_RAW_FILE_WRITE
            )
            _check_file_type_code_and_path(
                "write", self.metadata, call_index, expected_call
            )

            if file_data != expected_call.file_data:
                raise AssertionError(
                    (
                        "Trying to call RawFile.write (call no. {index}) "
                        "for '{real_ftc}', real written data is '{real_data}' "
                        "but expected data is '{expected_data}'"
                    ).format(
                        expected_data=expected_call.file_data,
                        index=call_index,
                        real_ftc=self.metadata.file_type_code,
                        real_data=file_data,
                    )
                )

            if can_overwrite != expected_call.can_overwrite:
                raise AssertionError(
                    (
                        "Trying to call RawFile.write (call no. {index}) "
                        "for '{real_ftc}', real can_overwrite is '{real_can}' "
                        "but expected can_overwrite is '{expected_can}'"
                    ).format(
                        expected_can=expected_call.can_overwrite,
                        index=call_index,
                        real_ftc=self.metadata.file_type_code,
                        real_can=can_overwrite,
                    )
                )

            if expected_call.already_exists:
                raise FileAlreadyExists(self.metadata)
            if expected_call.exception_msg:
                raise RawFileError(
                    self.metadata,
                    (
                        expected_call.exception_action
                        if expected_call.exception_action
                        else RawFileError.ACTION_WRITE
                    ),
                    expected_call.exception_msg,
                )

        def remove(self, fail_if_file_not_found=True):
            call_index, expected_call = call_queue.take(
                CALL_TYPE_RAW_FILE_REMOVE
            )
            _check_file_type_code_and_path(
                "remove", self.metadata, call_index, expected_call
            )

            if fail_if_file_not_found != expected_call.fail_if_file_not_found:
                raise AssertionError(
                    (
                        "Trying to call RawFile.remove (call no. {index}) "
                        "for '{real_ftc}', real fail_if_file_not_found is "
                        "'{real_fail}' but expected fail_if_file_not_found is "
                        "'{expected_fail}'"
                    ).format(
                        expected_fail=expected_call.fail_if_file_not_found,
                        index=call_index,
                        real_ftc=self.metadata.file_type_code,
                        real_fail=fail_if_file_not_found,
                    )
                )

            exception_msg = expected_call.exception_msg
            if (
                expected_call.file_not_found_exception
                and fail_if_file_not_found
            ):
                exception_msg = "No such file or directory"
            if exception_msg:
                raise RawFileError(
                    self.metadata,
                    RawFileError.ACTION_REMOVE,
                    exception_msg,
                )

        def backup(self):
            # TODO implement
            raise NotImplementedError()

    return RawFileMock
