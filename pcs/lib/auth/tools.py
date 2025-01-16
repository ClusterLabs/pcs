import grp
import pwd
from typing import TYPE_CHECKING

from .types import (
    AuthUser,
    DesiredUser,
)

if TYPE_CHECKING:
    from pcs.common.tools import StringCollection


class UserGroupsError(Exception):
    pass


def get_user_groups(username: str) -> list[str]:
    try:
        return [
            group.gr_name
            for group in grp.getgrall()
            if username in group.gr_mem
        ] + [
            # `group.gr_mem` does not contain the `username` when `group` is
            # primary for the `username` (the same is in /etc/group). So it is
            # necessary to add the primary group.
            grp.getgrgid(pwd.getpwnam(username).pw_gid).gr_name
        ]
    except KeyError as e:
        raise UserGroupsError from e


def get_effective_user(
    authenticated_user: AuthUser,
    effective_user_candidate: DesiredUser,
) -> AuthUser:
    username = authenticated_user.username
    groups: StringCollection = authenticated_user.groups
    if effective_user_candidate.username:
        username = effective_user_candidate.username
        if effective_user_candidate.groups:
            groups = effective_user_candidate.groups
    return AuthUser(username=username, groups=tuple(groups))
