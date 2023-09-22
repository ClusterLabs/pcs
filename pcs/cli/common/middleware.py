import fcntl
from collections import namedtuple
from functools import partial

from pcs.cli.reports.output import error


def build(*middleware_list):
    def run(command, env, *args, **kwargs):
        next_in_line = command
        for next_command in reversed(middleware_list):
            next_in_line = partial(next_command, next_in_line)

        return next_in_line(env, *args, **kwargs)

    return run


def cib(filename, touch_cib_file):
    """
    return configured middleware that cares about local cib
    bool use_local_cib is flag if local cib was required
    callable load_cib_content returns local cib content, take no params
    callable write_cib put content of cib to required place
    """

    def apply(next_in_line, env, *args, **kwargs):
        if filename:
            touch_cib_file(filename)
            try:
                with open(filename, mode="r") as cib_file:
                    # the lock is released when the file gets closed on leaving
                    # the with statement
                    fcntl.flock(cib_file.fileno(), fcntl.LOCK_SH)
                    original_content = cib_file.read()
            except EnvironmentError as e:
                raise error(f"Cannot read cib file '{filename}': '{e}'") from e
            env.cib_data = original_content

        result_of_next = next_in_line(env, *args, **kwargs)

        if filename and env.cib_data != original_content:
            try:
                with open(filename, mode="w") as cib_file:
                    # the lock is released when the file gets closed on leaving
                    # the with statement
                    fcntl.flock(cib_file.fileno(), fcntl.LOCK_EX)
                    cib_file.write(env.cib_data)
            except EnvironmentError as e:
                raise error(f"Cannot write cib file '{filename}': '{e}'") from e

        return result_of_next

    return apply


def corosync_conf_existing(local_file_path):
    def apply(next_in_line, env, *args, **kwargs):
        if local_file_path:
            try:
                with open(local_file_path, "r") as local_file:
                    # the lock is released when the file gets closed on leaving
                    # the with statement
                    fcntl.flock(local_file.fileno(), fcntl.LOCK_SH)
                    original_content = local_file.read()
            except EnvironmentError as e:
                raise error(
                    f"Unable to read {local_file_path}: {e.strerror}"
                ) from e
            env.corosync_conf_data = original_content

        result_of_next = next_in_line(env, *args, **kwargs)

        if local_file_path and env.corosync_conf_data != original_content:
            try:
                with open(local_file_path, "w") as local_file:
                    # the lock is released when the file gets closed on leaving
                    # the with statement
                    fcntl.flock(local_file.fileno(), fcntl.LOCK_EX)
                    local_file.write(env.corosync_conf_data)
            except EnvironmentError as e:
                raise error(
                    f"Unable to write {local_file_path}: {e.strerror}"
                ) from e
        return result_of_next

    return apply


def create_middleware_factory(**kwargs):
    """
    Commandline options: no options
    """
    return namedtuple("MiddlewareFactory", kwargs.keys())(**kwargs)
