import grp
import pwd
from collections import namedtuple
from concurrent.futures import ProcessPoolExecutor

from pam import pam
from tornado.gen import coroutine

import logging

# TODO use pacemaker_gname (??? + explanation why pacemaker_gname)
HA_ADM_GROUP = "haclient"

LOG = logging.getLogger("pcs.daemon")

IdentifiedUser = namedtuple("IdentifiedUser", "name groups")

class UserAuthorizationError(Exception):
    pass

def login_fail(username, reason, *args):
    LOG.info("Failed login by '%s' ({})".format(reason), username, *args)
    return None


def authorize_user_sync(username, password):
    LOG.info("Attempting login by %s", username)

    if not pam().authenticate(username, password, service="pcsd"):
        return login_fail(username, "bad username or password")

    try:
        groups = get_user_groups_sync(username)
    except KeyError as e:
        LOG.info("Unable to determine groups of user '%s': %s", username, e)
        return login_fail(username, "unable to determine user's groups")

    if HA_ADM_GROUP not in groups:
        return login_fail(username, "user is not a member of %s", HA_ADM_GROUP)

    return IdentifiedUser(username, groups)

def get_user_groups_sync(username):
    return tuple([
        group.gr_name
        for group in grp.getgrall()
        if username in group.gr_mem
    ] + [
        # `group.gr_mem` does not contain the `username` when `group` is
        # primary for the `username` (the same is in /etc/group). So it is
        # necessary add the primary group.
        grp.getgrgid(pwd.getpwnam(username).pw_gid).gr_name
    ])

# TODO async/await version - how to do it?
# When async/await is used then the problem is:
# "TypeError: object Future can't be used in 'await' expression" is raised even
# if the function "convert_yielded" is used according to
# http://www.tornadoweb.org/en/stable/guide/coroutines.html#python-3-5-async-and-await
@coroutine
def authorize_user(username, password):
    pool = ProcessPoolExecutor(max_workers=1)
    valid_user = yield pool.submit(authorize_user_sync, username, password)
    pool.shutdown()
    return valid_user
