from .types import DeprecatedMessageCode as _D

# DEPRECATED REPORT CODES
# Move the unused report codes to the top of this file and remove
# the ReportItemMessage and CliReportMessageCustom definitions with associated
# report building tests

# Comment structure:
# Removed after <version>[, unused after <version>]

# Use known version number of last release. "Removed" means when was the report
# code deprecated. "Unused" means that the report is no longer produced by PCS
# but the report code and message are still defined.

# Optionally, if the report is being replaced by a different report, a comment
# with the new report code can be added

# Removed after 0.11.6
CANNOT_MOVE_RESOURCE_BUNDLE = _D("CANNOT_MOVE_RESOURCE_BUNDLE")
CANNOT_MOVE_RESOURCE_CLONE = _D("CANNOT_MOVE_RESOURCE_CLONE")

# Removed after 0.11.3
SBD_NOT_INSTALLED = _D("SBD_NOT_INSTALLED")
UNABLE_TO_DETERMINE_USER_UID = _D("UNABLE_TO_DETERMINE_USER_UID")
UNABLE_TO_DETERMINE_GROUP_GID = _D("UNABLE_TO_DETERMINE_GROUP_GID")

# Removed after 0.11.3, unused after 0.11.2
# Replaced by DEFAULTS_CAN_BE_OVERRIDDEN
# Fixed a typo in report code
DEFAULTS_CAN_BE_OVERRIDEN = _D("DEFAULTS_CAN_BE_OVERRIDEN")

# Removed after 0.11.3, unused after 0.10.10
# Replaced by ADD_REMOVE_* reports from new add/remove validator
CANNOT_GROUP_RESOURCE_ADJACENT_RESOURCE_FOR_NEW_GROUP = _D(
    "CANNOT_GROUP_RESOURCE_ADJACENT_RESOURCE_FOR_NEW_GROUP"
)
CANNOT_GROUP_RESOURCE_ADJACENT_RESOURCE_NOT_IN_GROUP = _D(
    "CANNOT_GROUP_RESOURCE_ADJACENT_RESOURCE_NOT_IN_GROUP"
)
CANNOT_GROUP_RESOURCE_ALREADY_IN_THE_GROUP = _D(
    "CANNOT_GROUP_RESOURCE_ALREADY_IN_THE_GROUP"
)
CANNOT_GROUP_RESOURCE_MORE_THAN_ONCE = _D(
    "CANNOT_GROUP_RESOURCE_MORE_THAN_ONCE"
)
CANNOT_GROUP_RESOURCE_NO_RESOURCES = _D("CANNOT_GROUP_RESOURCE_NO_RESOURCES")
CANNOT_GROUP_RESOURCE_NEXT_TO_ITSELF = _D(
    "CANNOT_GROUP_RESOURCE_NEXT_TO_ITSELF"
)

# Removed after 0.11.3, unused after 0.10.8
# Produced only with Pacemaker 1.x
MULTIPLE_SCORE_OPTIONS = _D("MULTIPLE_SCORE_OPTIONS")


# Removed after 0.11.6, unused after 0.11.6
# Replaced by COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED
# and COROSYNC_NOT_RUNNING_CHECK_NODE_RUNNING
# These reports were replaced as they were to generic (both the codes and the
# messages) and thus didn't convey the required specific information and use
# case
COROSYNC_NOT_RUNNING_ON_NODE = _D("COROSYNC_NOT_RUNNING_ON_NODE")
COROSYNC_RUNNING_ON_NODE = _D("COROSYNC_RUNNING_ON_NODE")

# Removed after 0.11.7, unused after 0.11.7
# Replaced by DUPLICATE_CONSTRAINTS_EXIST and
# pcs.cli.reports.preprocessor.get_duplicate_constraint_exists_preprocessor
DUPLICATE_CONSTRAINTS_LIST = _D("DUPLICATE_CONSTRAINTS_LIST")
