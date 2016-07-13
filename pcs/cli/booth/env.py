from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os.path

from pcs.cli.common import console_report
from pcs.common import report_codes, env_file_role_codes
from pcs.lib.errors import LibraryEnvError


def middleware_config(name, local_file_path):
    def create_booth_env():
        if not local_file_path:
            return {"name": name}
        try:
            return {
                "name": name,
                "config_file": {
                    "content": open(local_file_path).read()
                        if os.path.isfile(local_file_path) else None
                    ,
                }
            }
        except EnvironmentError as e:
            console_report.error(
                "Unable to read {0}: {1}".format(local_file_path, e.strerror)
            )

    def flush(modified_env):
        if not local_file_path:
            return
        if not modified_env:
            #TODO now this would not happen
            #for more information see comment in
            #pcs.cli.common.lib_wrapper.lib_env_to_cli_env
            console_report.error("Error during library communication")

        if(
            modified_env["config_file"]["no_existing_file_expected"]
            and
            os.path.exists(local_file_path)
        ):
            msg = "booth config file {0} already exists".format(local_file_path)
            if not modified_env["config_file"]["can_overwrite_existing_file"]:
                console_report.error("{0}, use --force to override".format(msg))
            console_report.write_warn(msg)

        try:
            f = open(local_file_path, "w")
            f.write(modified_env["config_file"]["content"])
            f.close()
        except EnvironmentError as e:
            console_report.error(
                "Unable to write {0}: {1}".format(local_file_path, e.strerror)
            )

    def apply(next_in_line, env, *args, **kwargs):
        env.booth = create_booth_env()
        try:
            result_of_next = next_in_line(env, *args, **kwargs)
        except LibraryEnvError as e:
            for report in e.args:
                if(
                    report.code == report_codes.FILE_DOES_NOT_EXIST
                    and
                    report.info["file_role"] == env_file_role_codes.BOOTH_CONFIG
                ):
                    console_report.write_error(
                        "Booth config file '{0}' does no exist".format(
                            local_file_path
                        )
                    )
                    e.sign_processed(report)
            raise e
        flush(env.booth["modified_env"])
        return result_of_next

    return apply
