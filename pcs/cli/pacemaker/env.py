from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.common import console_report
from pcs.common.env_file_role_codes import PACEMAKER_AUTHKEY
from pcs.lib.errors import LibraryEnvError
from pcs.cli.common import env_file


def middleware_config(authkey_path):
    is_mocked_environment = authkey_path
    def create_pacemaker_env():
        if not is_mocked_environment:
            return {}
        return {
            "authkey": env_file.read(authkey_path),
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
            "pacemaker authkey",
            modified_env["authkey"],
            authkey_path
        )
        env_file.write(modified_env["authkey"], authkey_path)

    def apply(next_in_line, env, *args, **kwargs):
        env.pacemaker = create_pacemaker_env()
        try:
            result_of_next = next_in_line(env, *args, **kwargs)
        except LibraryEnvError as e:
            missing_file = env_file.MissingFileCandidateInfo
            env_file.evaluate_for_missing_files(e, [missing_file(
                PACEMAKER_AUTHKEY,
                "Pacemaker authkey",
                authkey_path
            )])
            raise e
        flush(env.pacemaker["modified_env"])
        return result_of_next

    return apply
