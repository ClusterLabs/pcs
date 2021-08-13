from .. import const


def get_value_for_cib(
    role: const.PcmkRoleType, is_latest_supported: bool
) -> const.PcmkRoleType:
    if is_latest_supported:
        if role in const.PCMK_ROLES_PROMOTED:
            return const.PCMK_ROLE_PROMOTED_PRIMARY
        if role in const.PCMK_ROLES_UNPROMOTED:
            return const.PCMK_ROLE_UNPROMOTED_PRIMARY
    else:
        if role in const.PCMK_ROLES_PROMOTED:
            return const.PCMK_ROLE_PROMOTED_LEGACY
        if role in const.PCMK_ROLES_UNPROMOTED:
            return const.PCMK_ROLE_UNPROMOTED_LEGACY
    return role
