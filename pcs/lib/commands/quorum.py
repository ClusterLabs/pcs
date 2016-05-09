from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


from pcs.lib import error_codes
from pcs.lib.errors import ReportItem, LibraryError
from pcs.lib.corosync.config_facade import ConfigFacade as CorosyncConfigFacade


def get_config(lib_env):
    """
    Extract and return quorum configuration from corosync.conf
    lib_env LibraryEnvironment
    """
    __ensure_not_cman(lib_env)
    cfg = CorosyncConfigFacade.from_string(lib_env.get_corosync_conf())
    device = None
    if cfg.has_quorum_device():
        model, model_options, generic_options = cfg.get_quorum_device_settings()
        device = {
            "model": model,
            "model_options": model_options,
            "generic_options": generic_options,
        }
    return {
        "options": cfg.get_quorum_options(),
        "device": device,
    }

def set_options(lib_env, options):
    """
    Set corosync quorum options, distribute and reload corosync.conf if live
    lib_env LibraryEnvironment
    options quorum options (dict)
    """
    __ensure_not_cman(lib_env)

    cfg = CorosyncConfigFacade.from_string(lib_env.get_corosync_conf())
    cfg.set_quorum_options(lib_env.report_processor, options)
    exported_config = cfg.config.export()

    lib_env.push_corosync_conf(exported_config)

def add_device(lib_env, model, model_options, generic_options):
    """
    Add quorum device to cluster, distribute and reload configs if live
    model quorum device model
    model_options model specific options dict
    generic_options generic quorum device options dict
    """
    __ensure_not_cman(lib_env)

    cfg = CorosyncConfigFacade.from_string(lib_env.get_corosync_conf())
    cfg.add_quorum_device(
        lib_env.report_processor,
        model,
        model_options,
        generic_options
    )
    exported_config = cfg.config.export()

    # TODO validation, verification, certificates, etc.

    lib_env.push_corosync_conf(exported_config)

def update_device(lib_env, model_options, generic_options):
    """
    Change quorum device settings, distribute and reload configs if live
    model_options model specific options dict
    generic_options generic quorum device options dict
    """
    __ensure_not_cman(lib_env)

    cfg = CorosyncConfigFacade.from_string(lib_env.get_corosync_conf())
    cfg.update_quorum_device(
        lib_env.report_processor,
        model_options,
        generic_options
    )
    exported_config = cfg.config.export()

    lib_env.push_corosync_conf(exported_config)

def remove_device(lib_env):
    """
    Stop using quorum device, distribute and reload configs if live
    """
    __ensure_not_cman(lib_env)

    cfg = CorosyncConfigFacade.from_string(lib_env.get_corosync_conf())
    cfg.remove_quorum_device()
    exported_config = cfg.config.export()

    lib_env.push_corosync_conf(exported_config)

def __ensure_not_cman(lib_env):
    if lib_env.is_corosync_conf_live and lib_env.is_cman_cluster:
        raise LibraryError(ReportItem.error(
            error_codes.CMAN_UNSUPPORTED_COMMAND,
            "This command is not supported on CMAN clusters"
        ))

