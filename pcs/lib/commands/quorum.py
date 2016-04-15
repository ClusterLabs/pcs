from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


from pcs.lib import error_codes
from pcs.lib.errors import ReportItem, LibraryError
from pcs.lib.external import (
    NodeCommunicationException,
    node_communicator_exception_to_report_item,
)
from pcs.lib.corosync.config_facade import ConfigFacade as CorosyncConfigFacade
from pcs.lib.corosync import live as corosync_live


def get_config(lib_env):
    """
    Extract and return quorum configuration from corosync.conf
    lib_env LibraryEnvironment
    """
    __ensure_not_cman(lib_env)
    cfg = CorosyncConfigFacade.from_string(lib_env.get_corosync_conf())
    return {
        "options": cfg.get_quorum_options(),
    }

def set_options(lib_env, options):
    """
    Set corosync quorum options, distribute and reload corosync.conf if live
    lib_env LibraryEnvironment
    options quorum options (dict)
    """
    __ensure_not_cman(lib_env)

    cfg = CorosyncConfigFacade.from_string(lib_env.get_corosync_conf())
    cfg.set_quorum_options(options)
    exported_config = cfg.config.export()

    if lib_env.is_corosync_conf_live:
        lib_env.logger.info("Sending updated corosync.conf to nodes...")
        report = []
        # TODO use parallel communication
        for node in cfg.get_nodes():
            try:
                corosync_live.set_remote_corosync_conf(
                    lib_env.node_communicator(),
                    node,
                    exported_config
                )
                lib_env.logger.info("{node}: Succeeded".format(node=node.label))
            except NodeCommunicationException as e:
                report.append(node_communicator_exception_to_report_item(e))
                report.append(ReportItem.error(
                    error_codes.NODE_COROSYNC_CONF_SAVE_ERROR,
                    "{node}: Unable to set corosync config",
                    info={"node": node.label}
                ))
            except Exception as e:
                report.append(ReportItem.error(
                    error_codes.COMMON_ERROR,
                    str(e)
                ))
        if report:
            raise LibraryError(*report)

        corosync_live.reload_config(lib_env.cmd_runner())
        lib_env.logger.info("Corosync configuration reloaded")

    else:
        lib_env.push_corosync_conf(exported_config)

def __ensure_not_cman(lib_env):
    if lib_env.is_corosync_conf_live and lib_env.is_cman_cluster:
        raise LibraryError(ReportItem.error(
            error_codes.CMAN_UNSUPPORTED_COMMAND,
            "This command is not supported on CMAN clusters"
        ))
