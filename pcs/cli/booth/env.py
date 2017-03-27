from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.common import console_report
from pcs.common.env_file_role_codes import BOOTH_CONFIG, BOOTH_KEY
from pcs.lib.errors import LibraryEnvError
from pcs.cli.common import env_file


def middleware_config(name, config_path, key_path):
    if config_path and not key_path:
        raise console_report.error(
            "With --booth-conf must be specified --booth-key as well"
        )

    if key_path and not config_path:
        raise console_report.error(
            "With --booth-key must be specified --booth-conf as well"
        )

    is_mocked_environment = config_path and key_path

    def create_booth_env():
        if not is_mocked_environment:
            return {"name": name}
        return {
            "name": name,
            "config_file": env_file.read(config_path),
            "key_file": env_file.read(key_path, is_binary=True),
            "key_path": key_path,
        }

    def flush(modified_env):
        if not is_mocked_environment:
            return
        if not modified_env:
            #TODO now this would not happen
            #for more information see comment in
            #pcs.cli.common.lib_wrapper.lib_env_to_cli_env
            raise console_report.error("Error during library communication")

        env_file.process_no_existing_file_expectation(
            "booth config file",
            modified_env["config_file"],
            config_path
        )
        env_file.process_no_existing_file_expectation(
            "booth key file",
            modified_env["key_file"],
            key_path
        )
        env_file.write(modified_env["key_file"], key_path)
        env_file.write(modified_env["config_file"], config_path)

    def apply(next_in_line, env, *args, **kwargs):
        env.booth = create_booth_env()
        try:
            result_of_next = next_in_line(env, *args, **kwargs)
        except LibraryEnvError as e:
            missing_file = env_file.MissingFileCandidateInfo

            env_file.evaluate_for_missing_files(e, [
                missing_file(BOOTH_CONFIG, "Booth config file", config_path),
                missing_file(BOOTH_KEY, "Booth key file", key_path),
            ])
            raise e
        flush(env.booth["modified_env"])
        return result_of_next

    return apply
