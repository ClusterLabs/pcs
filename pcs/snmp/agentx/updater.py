from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.snmp.agentx.pcs_pyagentx import Updater


class AgentxUpdaterBase(Updater):
    """
    Base class for SNMP angent updaters. It provides methods for comfortable
    setting of values provided by the agent.
    """

    # this has to be set by the descendants
    _oid_tree = None

    @property
    def oid_tree(self):
        return self._oid_tree

    def _set_val(self, data_type, oid, value):
        self._data[oid] = {'name': oid, 'type': data_type, 'value': value}

    def _set_value_list(self, data_type, oid, value):
        if not isinstance(value, list):
            value = [value]
        for index, val in enumerate(value):
            self._set_val(
                data_type, "{oid}.{index}".format(oid=oid, index=index), val
            )

    def set_typed_value(self, oid, value):
        """
        oid string -- oid in the number form
        value BaseType -- BaseType object filled with value to set. Value can be
          either primitive value or list of primitive values.
        """
        self._set_value_list(value.data_type, oid, value.value)

    def set_value(self, str_oid, value):
        """
        str_oid string -- string form of oid. Raw (number form) oid will be
          figured out based on oid_tree tree.
        value primitive value or list of primitive values -- value to be set on
          specified str_oid
        """
        oid, oid_cls = _str_oid_to_oid(self.oid_tree, str_oid)
        self.set_typed_value(oid, oid_cls.data_type(value))

    def set_table(self, oid, table):
        """
        oid string -- number form of oid
        table list of list of BaseType -- members of outer list represent rows
          of table and members of inner list are columns.
        """
        for row in table:
            if not row:
                continue
            row_id = _str_to_oid(str(row[0].value))
            for index, col in enumerate(row[1:], start=2):
                value_oid = "{base_oid}.{index}.{row_id}".format(
                    base_oid=oid, index=index, row_id=row_id
                )
                self._set_val(col.data_type, value_oid, col.value)


def _find_oid_in_sub_tree(sub_tree, section_name):
    if sub_tree.member_list is None:
        return None
    for oid in sub_tree.member_list:
        if oid.str_oid == section_name:
            return oid
    return None


def _str_oid_to_oid(sub_tree, str_oid):
    sections = str_oid.split(".")
    oid_list = []
    for section in sections:
        sub_tree = _find_oid_in_sub_tree(sub_tree, section)
        if sub_tree is None:
            raise AssertionError(
                "oid section {0} ({1}) not found in {1} ({2})".format(
                    section, str_oid, sub_tree.str_oid
                )
            )
        oid_list.append(str(sub_tree.oid))
        if sub_tree.data_type:
            oid = ".".join(oid_list)
            return (oid, sub_tree)


def _str_to_oid(data):
    length = len(data)
    oid_int = [str(ord(i)) for i in data]
    return str(length) + '.' + '.'.join(oid_int)
