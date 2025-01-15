from typing import Sequence


class PrintableTreeNode:
    @property
    def members(self) -> Sequence["PrintableTreeNode"]:
        raise NotImplementedError()

    @property
    def detail(self) -> list[str]:
        raise NotImplementedError()

    @property
    def is_leaf(self) -> bool:
        raise NotImplementedError()

    def get_title(self, verbose: bool) -> str:
        raise NotImplementedError()


def tree_to_lines(
    node: PrintableTreeNode,
    verbose: bool = False,
    title_prefix: str = "",
    indent: str = "",
) -> list[str]:
    """
    Return sequence of strings representing lines to print out tree structure on
    command line.
    """
    result = []
    note = ""
    if node.is_leaf:
        note = " [displayed elsewhere]"
    title = node.get_title(verbose)
    result.append(f"{title_prefix}{title}{note}")
    if node.is_leaf:
        return result
    _indent = "|  "
    if not node.members:
        _indent = "   "
    result.extend(f"{indent}{_indent}{line}" for line in node.detail)
    _indent = "|  "
    _title_prefix = "|- "
    for member in node.members:
        if member == node.members[-1]:
            _indent = "   "
            _title_prefix = "`- "
        result.extend(
            tree_to_lines(
                member,
                verbose,
                indent=f"{indent}{_indent}",
                title_prefix=f"{indent}{_title_prefix}",
            )
        )
    return result
