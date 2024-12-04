from pcs.cli.file import metadata
from pcs.cli.reports import output
from pcs.common import file as pcs_file
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.reports.item import ReportItem
from pcs.lib.errors import LibraryError


def middleware_config(config_path, key_path):
    if config_path and not key_path:
        raise output.error(
            "When --booth-conf is specified, "
            "--booth-key must be specified as well"
        )
    if key_path and not config_path:
        raise output.error(
            "When --booth-key is specified, "
            "--booth-conf must be specified as well"
        )
    is_mocked_environment = config_path and key_path

    config_file = None
    key_file = None
    if is_mocked_environment:
        config_file = pcs_file.RawFile(
            metadata.for_file_type(file_type_codes.BOOTH_CONFIG, config_path)
        )
        key_file = pcs_file.RawFile(
            metadata.for_file_type(file_type_codes.BOOTH_KEY, key_path)
        )

    def create_booth_env():
        try:
            config_data = (
                config_file.read()
                if config_file and config_file.exists()
                else None
            )
            key_data = (
                key_file.read() if key_file and key_file.exists() else None
            )
        # TODO write custom error handling, do not use pcs.lib specific code
        # and LibraryError
        except pcs_file.RawFileError as e:
            raise LibraryError(
                ReportItem.error(
                    reports.messages.FileIoError(
                        e.metadata.file_type_code,
                        e.action,
                        e.reason,
                        file_path=e.metadata.path,
                    )
                )
            ) from e
        return {
            "config_data": config_data,
            "key_data": key_data,
            "key_path": key_path,
        }

    def flush(modified_env):
        if not is_mocked_environment:
            return
        if not modified_env:
            # TODO now this would not happen
            # for more information see comment in
            # pcs.cli.common.lib_wrapper.lib_env_to_cli_env
            raise output.error("Error during library communication")
        try:
            if modified_env["key_file"]["content"] is not None:
                key_file.write(
                    modified_env["key_file"]["content"], can_overwrite=True
                )
            config_file.write(
                modified_env["config_file"]["content"], can_overwrite=True
            )
        # TODO write custom error handling, do not use pcs.lib specific code
        # and LibraryError
        except pcs_file.RawFileError as e:
            raise LibraryError(
                ReportItem.error(
                    reports.messages.FileIoError(
                        e.metadata.file_type_code,
                        e.action,
                        e.reason,
                        file_path=e.metadata.path,
                    )
                )
            ) from e

    def apply(next_in_line, env, *args, **kwargs):
        env.booth = create_booth_env() if is_mocked_environment else {}
        result_of_next = next_in_line(env, *args, **kwargs)
        if is_mocked_environment:
            flush(env.booth["modified_env"])
        return result_of_next

    return apply
