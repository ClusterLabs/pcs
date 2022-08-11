import grp
import pwd


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
