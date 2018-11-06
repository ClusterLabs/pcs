import os.path
from collections import namedtuple

from pcs.cli.common import console_report
from pcs.common import report_codes


def report_missing(file_role, file_path):
    console_report.error(
        "{0} '{1}' does not exist".format(file_role, file_path)
    )

def is_missing_report(report, file_role_code):
    return (
        report.code == report_codes.FILE_DOES_NOT_EXIST
        and
        report.info["file_role"] == file_role_code
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

def write(env_file, file_path):
    try:
        file = open(
            file_path, "wb" if env_file.get("is_binary", False) else "w"
        )
        file.write(env_file["content"])
        file.close()
    except EnvironmentError as e:
        raise console_report.error(
            "Unable to write {0}: {1}".format(file_path, e.strerror)
        )

def read(path, is_binary=False):
    try:
        mode = "rb" if is_binary else "r"
        return {
            "content": open(path, mode).read() if os.path.isfile(path) else None
        }
    except EnvironmentError as e:
        raise console_report.error(
            "Unable to read {0}: {1}".format(path, e.strerror)
        )

MissingFileCandidateInfo = namedtuple(
    "MissingFileCandidateInfo",
    "code desc path"
)

def evaluate_for_missing_files(exception, file_info_list):
    """
    list of MissingFileCandidateInfo file_info_list contains the info for files
        that can be missing
    """
    for report in exception.args:
        for file_info in file_info_list:
            if is_missing_report(report, file_info.code):
                report_missing(file_info.desc, file_info.path)
                exception.sign_processed(report)
