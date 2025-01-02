from pcs_test.tools.command_env.mock_raw_file import (
    RawFileExistsCall,
    RawFileReadCall,
    RawFileRemoveCall,
    RawFileWriteCall,
)


class RawFileConfig:
    def __init__(self, call_collection):
        self.__calls = call_collection

    def exists(
        self,
        file_type_code,
        path,
        exists=True,
        name="raw_file.exists",
        before=None,
        instead=None,
    ):
        """
        Create a call for checking a file existence

        string file_type_code -- item from pcs.common.file_type_codes
        string path -- expected file path
        bool exists -- the result of the existence check
        string name -- the key of the call
        string before -- the key of a call before which this call is to be
            placed
        string instead -- the key of a call instead of which this new call is to
            be placed
        """
        call = RawFileExistsCall(file_type_code, path, exists=exists)
        self.__calls.place(name, call, before, instead)

    def read(
        self,
        file_type_code,
        path,
        content=None,
        exception_msg=None,
        name="raw_file.read",
        before=None,
        instead=None,
    ):
        """
        Create a call for reading a file content

        string file_type_code -- item from pcs.common.file_type_codes
        string path -- expected file path
        bytes content -- the result of a successful reading
        string exception_msg -- resulting error in case of unsuccessful reading
        string name -- the key of the call
        string before -- the key of a call before which this call is to be
            placed
        string instead -- the key of a call instead of which this new call is to
            be placed
        """
        call = RawFileReadCall(
            file_type_code,
            path,
            content=content,
            exception_msg=exception_msg,
        )
        self.__calls.place(name, call, before, instead)

    def write(  # noqa: PLR0913
        self,
        file_type_code,
        path,
        file_data,
        *,
        can_overwrite=False,
        already_exists=False,
        exception_msg=None,
        exception_action=None,
        name="raw_file.write",
        before=None,
        instead=None,
    ):
        """
        Create a call for writing to a file

        string file_type_code -- item from pcs.common.file_type_codes
        string path -- expected file path
        bytes file_data -- expected data to be written
        bool already_exist -- result is that the file already exists
        string exception_msg -- resulting error in case of unsuccessful write
        string exception_action -- item of pcs.common.file.RawFileError
        string name -- the key of the call
        string before -- the key of a call before which this call is to be
            placed
        string instead -- the key of a call instead of which this new call is to
            be placed
        """
        # pylint: disable=too-many-arguments
        call = RawFileWriteCall(
            file_type_code,
            path,
            file_data,
            can_overwrite=can_overwrite,
            already_exists=already_exists,
            exception_msg=exception_msg,
            exception_action=exception_action,
        )
        self.__calls.place(name, call, before, instead)

    def remove(
        self,
        file_type_code,
        path,
        *,
        fail_if_file_not_found=True,
        exception_msg=None,
        file_not_found_exception=False,
        name="raw_file.remove",
        before=None,
        instead=None,
    ):
        """
        Create a call for removing a file

        string file_type_code -- item from pcs.common.file_type_codes
        string path -- expected file path
        bool fail_if_file_not_found -- should it fail when file not found?
        string exception_msg -- resulting error in case of unsuccessful removal
        bool file_not_found_exception -- raise an exception file was not found
        string name -- the key of the call
        string before -- the key of a call before which this call is to be
            placed
        string instead -- the key of a call instead of which this new call is to
            be placed
        """
        # pylint: disable=too-many-arguments
        call = RawFileRemoveCall(
            file_type_code,
            path,
            fail_if_file_not_found=fail_if_file_not_found,
            exception_msg=exception_msg,
            file_not_found_exception=file_not_found_exception,
        )
        self.__calls.place(name, call, before, instead)
