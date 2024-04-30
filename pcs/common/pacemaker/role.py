from .. import const


def get_value_for_cib(
    role: const.PcmkRoleType, is_latest_supported: bool
) -> const.PcmkRoleType:
    if is_latest_supported:
        return get_value_primary(role)
    if role == const.PCMK_ROLE_PROMOTED:
        return const.PCMK_ROLE_PROMOTED_LEGACY
    if role == const.PCMK_ROLE_UNPROMOTED:
        return const.PCMK_ROLE_UNPROMOTED_LEGACY
    return role


def get_value_primary(role: const.PcmkRoleType) -> const.PcmkRoleType:
    if role == const.PCMK_ROLE_PROMOTED_LEGACY:
        return const.PCMK_ROLE_PROMOTED
    if role == const.PCMK_ROLE_UNPROMOTED_LEGACY:
        return const.PCMK_ROLE_UNPROMOTED
    return role
