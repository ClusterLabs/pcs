from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial

from pcs.cli.common import console_report


def build(*middleware_list):
    def run(command, lib, argv, modificators):
        next_in_line = command
        for next_command in reversed(middleware_list):
            next_in_line = partial(next_command, next_in_line)

        next_in_line(lib, argv, modificators)
    return run

def cib(use_local_cib, cib_content, write_cib):
    def apply(next_in_line, lib, argv, modificators):
        if use_local_cib:
            lib.env.cib_data = cib_content

        next_in_line(lib, argv, modificators)

        if use_local_cib:
            write_cib(lib.env.cib_data)
    return apply

def corosync_conf_existing():
    def apply(next_in_line, lib, argv, modificators):
        local_file_path = modificators.get("corosync_conf", None)
        if local_file_path:
            try:
                lib.env.corosync_conf_data = open(local_file_path).read()
            except EnvironmentError as e:
                console_report.error("Unable to read {0}: {1}".format(
                    local_file_path,
                    e.strerror
                ))

        next_in_line(lib, argv, modificators)

        if local_file_path:
            try:
                f = open(local_file_path, "w")
                f.write(lib.env.corosync_conf_data)
                f.close()
            except EnvironmentError as e:
                console_report.error("Unable to write {0}: {1}".format(
                    local_file_path,
                    e.strerror
                ))
    return apply
