from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.common.parse_args import group_by_keywords


DEFAULT_BOOTH_NAME = "booth"

def config_setup(lib, arg_list, modifiers):
    """
    create booth config
    """
    booth_configuration = group_by_keywords(
        arg_list,
        set(["sites", "arbitrators"]),
        keyword_repeat_allowed=False
    )
    lib.booth.config_setup(booth_configuration, modifiers["force"])

def config_show(lib, arg_list, modifiers):
    """
    print booth config
    """
    booth_configuration = lib.booth.config_show()
    line_list = (
        ["site = {0}".format(site) for site in booth_configuration["sites"]]
        +
        [
            "arbitrator = {0}".format(arbitrator)
            for arbitrator in booth_configuration["arbitrators"]
        ]
    )
    for line in line_list:
        print(line)
