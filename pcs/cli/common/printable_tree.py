class PrintableTreeNode(object):
    @property
    def members(self):
        raise NotImplementedError()

    @property
    def detail(self):
        raise NotImplementedError()

    @property
    def is_leaf(self):
        raise NotImplementedError()

    def get_title(self, verbose):
        raise NotImplementedError()


def tree_to_lines(node, verbose=False, title_prefix="", indent=""):
    """
    Return sequence of strings representing lines to print out tree structure on
    command line.
    """
    result = []
    note = ""
    if node.is_leaf:
        note = " [displayed elsewhere]"
    title = node.get_title(verbose)
    result.append("{}{}{}".format(title_prefix, title, note))
    if node.is_leaf:
        return result
    _indent = "|  "
    if not node.members:
        _indent = "   "
    for line in node.detail:
        result.append("{}{}{}".format(indent, _indent, line))
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
                indent="{}{}".format(indent, _indent),
                title_prefix="{}{}".format(indent, _title_prefix),
            )
        )
    return result
