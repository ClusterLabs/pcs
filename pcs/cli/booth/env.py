from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os.path

from pcs.cli.common import console_report
from pcs.common import report_codes, env_file_role_codes as file_role_codes
from pcs.lib.errors import LibraryEnvError


def read_env_file(path):
    try:
        return {
            "content": open(path).read() if os.path.isfile(path) else None
        }
    except EnvironmentError as e:
        raise console_report.error(
            "Unable to read {0}: {1}".format(path, e.strerror)
        )

def write_env_file(env_file, file_path):
    try:
        f = open(file_path, "wb" if env_file.get("is_binary", False) else "w")
        f.write(env_file["content"])
        f.close()
    except EnvironmentError as e:
        raise console_report.error(
            "Unable to write {0}: {1}".format(file_path, e.strerror)
        )

def process_no_existing_file_expectation(file_role, env_file, file_path):
    if(
        env_file["no_existing_file_expected"]
        and
        os.path.exists(file_path)
    ):
        msg = "{0} {1} already exists".format(file_role, file_path)
        if not env_file["can_overwrite_existing_file"]:
            raise console_report.error(
                "{0}, use --force to override".format(msg)
            )
        console_report.warn(msg)

def is_missing_file_report(report, file_role_code):
    return (
        report.code == report_codes.FILE_DOES_NOT_EXIST
        and
        report.info["file_role"] == file_role_code
    )

def report_missing_file(file_role, file_path):
    console_report.error(
        "{0} '{1}' does not exist".format(file_role, file_path)
    )

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
            "config_file": read_env_file(config_path),
            "key_file": read_env_file(key_path),
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

        process_no_existing_file_expectation(
            "booth config file",
            modified_env["config_file"],
            config_path
        )
        process_no_existing_file_expectation(
            "booth key file",
            modified_env["key_file"],
            key_path
        )
        write_env_file(modified_env["key_file"], key_path)
        write_env_file(modified_env["config_file"], config_path)

    def apply(next_in_line, env, *args, **kwargs):
        env.booth = create_booth_env()
        try:
            result_of_next = next_in_line(env, *args, **kwargs)
        except LibraryEnvError as e:
            for report in e.args:
                if is_missing_file_report(report, file_role_codes.BOOTH_CONFIG):
                    report_missing_file("Booth config file", config_path)
                    e.sign_processed(report)
                if is_missing_file_report(report, file_role_codes.BOOTH_KEY):
                    report_missing_file("Booth key file", key_path)
                    e.sign_processed(report)
            raise e
        flush(env.booth["modified_env"])
        return result_of_next

    return apply
