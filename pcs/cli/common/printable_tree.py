from typing import Sequence
from typing_extensions import Protocol


class PrintableTreeNode(Protocol):
    @property
    def members(self) -> Sequence["PrintableTreeNode"]:
        raise NotImplementedError()

    @property
    def detail(self) -> Sequence[str]:
        raise NotImplementedError()

    @property
    def title(self) -> str:
        raise NotImplementedError()

    @property
    def is_leaf(self) -> bool:
        raise NotImplementedError()


def tree_to_lines(
    node: PrintableTreeNode,
    title_prefix: str = "",
    indent: str = "",
) -> Sequence[str]:
    """
    Return sequence of strings representing lines to print out tree structure on
    command line.
    """
    result = []
    note = ""
    if node.is_leaf:
        note = f" [displayed elsewhere]"
    result.append(f"{title_prefix}{node.title}{note}")
    if node.is_leaf:
        return result
    _indent = "|  "
    if not node.members:
        _indent = "   "
    for line in node.detail:
        result.append(f"{indent}{_indent}{line}")
    _indent = "|  "
    _title_prefix = "|- "
    for member in node.members:
        if member == node.members[-1]:
            _indent = "   "
            _title_prefix = "`- "
        result.extend(
            tree_to_lines(
                member,
                indent=f"{indent}{_indent}",
                title_prefix=f"{indent}{_title_prefix}",
            )
        )
    return result
