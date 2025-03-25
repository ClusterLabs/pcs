from typing import Collection, NewType

AddRemoveContainerType = NewType("AddRemoveContainerType", str)
AddRemoveItemType = NewType("AddRemoveItemType", str)
BoothConfigUsedWhere = NewType("BoothConfigUsedWhere", str)
DefaultAddressSource = NewType("DefaultAddressSource", str)
FenceHistoryCommandType = NewType("FenceHistoryCommandType", str)
ForceCode = NewType("ForceCode", str)
ForceFlags = Collection[ForceCode]
MessageCode = NewType("MessageCode", str)
DeprecatedMessageCode = NewType("DeprecatedMessageCode", str)
PcsCommand = NewType("PcsCommand", str)
ReasonType = NewType("ReasonType", str)
ServiceAction = NewType("ServiceAction", str)
SeverityLevel = NewType("SeverityLevel", str)
StonithRestartlessUpdateUnableToPerformReason = NewType(
    "StonithRestartlessUpdateUnableToPerformReason", str
)
StonithWatchdogTimeoutCannotBeSetReason = NewType(
    "StonithWatchdogTimeoutCannotBeSetReason", str
)
