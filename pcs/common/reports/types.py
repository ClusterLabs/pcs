from typing import Collection, NewType

AddRemoveContainerType = NewType("AddRemoveContainerType", str)
AddRemoveItemType = NewType("AddRemoveItemType", str)
BoothConfigUsedWhere = NewType("BoothConfigUsedWhere", str)
DefaultAddressSource = NewType("DefaultAddressSource", str)
FenceHistoryCommandType = NewType("FenceHistoryCommandType", str)
ForceCode = NewType("ForceCode", str)
# Container would suffice. However, this type is used in interfaces of many
# library commands. When calling the commands via API, their input comes in
# JSON and is transformed by dacite. In JSON, force flags are held in a list,
# there is no other way. And dacite is unable to deserialize a list to
# attributes annotated as Iterable or Container.
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
