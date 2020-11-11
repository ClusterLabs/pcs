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
                    original_content = cib_file.read()
            except EnvironmentError as e:
                raise error(
                    "Cannot read cib file '{0}': '{1}'".format(filename, str(e))
                ) from e
            env.cib_data = original_content

        result_of_next = next_in_line(env, *args, **kwargs)

        if filename and env.cib_data != original_content:
            try:
                with open(filename, mode="w") as cib_file:
                    cib_file.write(env.cib_data)
            except EnvironmentError as e:
                raise error(
                    "Cannot write cib file '{0}': '{1}'".format(
                        filename, str(e)
                    )
                ) from e

        return result_of_next

    return apply


def corosync_conf_existing(local_file_path):
    def apply(next_in_line, env, *args, **kwargs):
        if local_file_path:
            try:
                env.corosync_conf_data = open(local_file_path).read()
            except EnvironmentError as e:
                raise error(
                    "Unable to read {0}: {1}".format(
                        local_file_path, e.strerror
                    )
                ) from e

        result_of_next = next_in_line(env, *args, **kwargs)

        if local_file_path:
            try:
                file = open(local_file_path, "w")
                file.write(env.corosync_conf_data)
                file.close()
            except EnvironmentError as e:
                raise error(
                    "Unable to write {0}: {1}".format(
                        local_file_path, e.strerror
                    )
                ) from e
        return result_of_next

    return apply


def create_middleware_factory(**kwargs):
    """
    Commandline options: no options
    """
    return namedtuple("MiddlewareFactory", kwargs.keys())(**kwargs)
