from pcs.lib.corosync.config_facade import ConfigFacade
from pcs.lib.errors import LibraryError

from pcs_test.tools.assertions import prepare_diff

CALL_TYPE_PUSH_COROSYNC_CONF = "CALL_TYPE_PUSH_COROSYNC_CONF"


class Call:
    type = CALL_TYPE_PUSH_COROSYNC_CONF

    def __init__(
        self,
        corosync_conf_text,
        skip_offline_targets,
        raises=False,
        need_stopped_cluster=False,
    ):
        self.corosync_conf_text = corosync_conf_text
        self.skip_offline_targets = skip_offline_targets
        self.raises = raises
        self.need_stopped_cluster = need_stopped_cluster

    def __repr__(self):
        return str("<CorosyncConfPush skip-offline='{0}'>").format(
            self.skip_offline_targets
        )


def get_push_corosync_conf(call_queue):
    def push_corosync_conf(
        lib_env, corosync_conf_facade, skip_offline_nodes=False
    ):
        del lib_env
        i, expected_call = call_queue.take(CALL_TYPE_PUSH_COROSYNC_CONF)

        if not isinstance(corosync_conf_facade, ConfigFacade):
            raise AssertionError(
                (
                    "Trying to call env.push_corosync_conf (call no. {0}) with"
                    " {1} instead of lib.corosync.config_facade.ConfigFacade"
                ).format(i, type(corosync_conf_facade))
            )

        to_push = corosync_conf_facade.config.export()
        if to_push != expected_call.corosync_conf_text:
            raise AssertionError(
                "Trying to call env.push_corosync_conf but the pushed "
                "corosync.conf is not as expected:\n{0}".format(
                    prepare_diff(to_push, expected_call.corosync_conf_text)
                )
            )
        if skip_offline_nodes != expected_call.skip_offline_targets:
            raise AssertionError(
                (
                    "Trying to call env.push_corosync_conf but the "
                    "skip_offline flag is not as expected:\nexpected '{0}' != "
                    "actual '{1}'"
                ).format(
                    expected_call.skip_offline_targets,
                    skip_offline_nodes,
                )
            )
        if (
            corosync_conf_facade.need_stopped_cluster
            != expected_call.need_stopped_cluster
        ):
            raise AssertionError(
                "Tryint to call env.push_corosync_conf but stopped cluster "
                "requirement (corosync_conf_facade.need_stopped_cluster) "
                f"differs. Expected: {expected_call.need_stopped_cluster}; "
                f"Actual: {corosync_conf_facade.need_stopped_cluster}"
            )
        if expected_call.raises:
            raise LibraryError()

    return push_corosync_conf


def is_push_corosync_conf_call_in(call_queue):
    return call_queue.has_type(CALL_TYPE_PUSH_COROSYNC_CONF)
