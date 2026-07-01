from typing import Final, NewType

FencingTargetType = NewType("FencingTargetType", str)
FencingTargetValue = str | tuple[str, str]

TARGET_TYPE_NODE: Final = FencingTargetType("node")
TARGET_TYPE_REGEXP: Final = FencingTargetType("regexp")
TARGET_TYPE_ATTRIBUTE: Final = FencingTargetType("attribute")
