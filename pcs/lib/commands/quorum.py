from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


from pcs.lib import reports
from pcs.lib.errors import LibraryError


def get_config(lib_env):
    """
    Extract and return quorum configuration from corosync.conf
    lib_env LibraryEnvironment
    """
    __ensure_not_cman(lib_env)
    cfg = lib_env.get_corosync_conf()
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
    cfg = lib_env.get_corosync_conf()
    cfg.set_quorum_options(lib_env.report_processor, options)
    lib_env.push_corosync_conf(cfg)

def add_device(
    lib_env, model, model_options, generic_options, force_model=False,
    force_options=False
):
    """
    Add quorum device to cluster, distribute and reload configs if live
    model quorum device model
    model_options model specific options dict
    generic_options generic quorum device options dict
    force_model continue even if the model is not valid
    force_options continue even if options are not valid
    """
    __ensure_not_cman(lib_env)

    cfg = lib_env.get_corosync_conf()
    cfg.add_quorum_device(
        lib_env.report_processor,
        model,
        model_options,
        generic_options,
        force_model,
        force_options
    )
    # TODO validation, verification, certificates, etc.
    lib_env.push_corosync_conf(cfg)

def update_device(lib_env, model_options, generic_options, force_options=False):
    """
    Change quorum device settings, distribute and reload configs if live
    model_options model specific options dict
    generic_options generic quorum device options dict
    force_options continue even if options are not valid
    """
    __ensure_not_cman(lib_env)
    cfg = lib_env.get_corosync_conf()
    cfg.update_quorum_device(
        lib_env.report_processor,
        model_options,
        generic_options,
        force_options
    )
    lib_env.push_corosync_conf(cfg)

def remove_device(lib_env):
    """
    Stop using quorum device, distribute and reload configs if live
    """
    __ensure_not_cman(lib_env)

    cfg = lib_env.get_corosync_conf()
    cfg.remove_quorum_device()
    lib_env.push_corosync_conf(cfg)

def __ensure_not_cman(lib_env):
    if lib_env.is_corosync_conf_live and lib_env.is_cman_cluster:
        raise LibraryError(reports.cman_unsupported_command())

