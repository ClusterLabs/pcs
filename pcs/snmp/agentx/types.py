from collections import namedtuple

# pylint: disable=import-error
import pyagentx

BaseType = namedtuple("BaseType", ["data_type", "value"])


class IntegerType(BaseType):
    def __new__(cls, value):
        return super(IntegerType, cls).__new__(
            cls, data_type=pyagentx.TYPE_INTEGER, value=value
        )


class StringType(BaseType):
    def __new__(cls, value):
        return super(StringType, cls).__new__(
            cls, data_type=pyagentx.TYPE_OCTETSTRING, value=value
        )


class Oid(
    namedtuple("OidBase", ["oid", "str_oid", "data_type", "member_list"])
):
    """
    This class represents one entity in OID tree. It is possible to define MIB
    tree model for translating string (human friendly) oid into numbered oid
    used in SNMP.

    oid int -- unique oid identificator on a given layer
    str_oid string -- string oid identificator in a given layer
    data_type BaseType -- class inherited from BaseType, data type of entity
      this class represents
    member_list list of Oid -- list of members/descendants of this entity.
      If set, this entity is threated as object identifier in MIB  and data_type
      is ignored.
    """

    __slots__ = ()

    def __new__(cls, oid, str_oid, data_type=None, member_list=None):
        return super(Oid, cls).__new__(
            cls, oid, str_oid, data_type, member_list
        )
