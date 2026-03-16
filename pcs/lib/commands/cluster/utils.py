from pcs.common import file_type_codes, reports
from pcs.lib.corosync import config_parser
from pcs.lib.corosync.config_facade import ConfigFacade
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError


def ensure_live_env(env: LibraryEnvironment) -> None:
    not_live = []
    if not env.is_cib_live:
        not_live.append(file_type_codes.CIB)
    if not env.is_corosync_conf_live:
        not_live.append(file_type_codes.COROSYNC_CONF)
    if not_live:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.LiveEnvironmentRequired(not_live)
            )
        )


def verify_corosync_conf(corosync_conf_facade: ConfigFacade) -> None:
    # This is done in pcs.lib.env.LibraryEnvironment.push_corosync_conf
    # usually. But there are special cases here which use custom corosync.conf
    # pushing so the check must be done individually.
    (
        bad_sections,
        bad_attr_names,
        bad_attr_values,
    ) = config_parser.verify_section(corosync_conf_facade.config)
    if bad_sections or bad_attr_names or bad_attr_values:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.CorosyncConfigCannotSaveInvalidNamesValues(
                    bad_sections,
                    bad_attr_names,
                    bad_attr_values,
                )
            )
        )
