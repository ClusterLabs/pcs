from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from pcs.lib.booth.config_structure import ConfigItem

def to_exchange_format(booth_configuration):
    return [
        {
            "key": item.key,
            "value": item.value,
            "details": to_exchange_format(item.details),
        }
        for item in booth_configuration
    ]


def from_exchange_format(exchange_format):
    return [
        ConfigItem(
            item["key"],
            item["value"],
            from_exchange_format(item["details"]),
        )
        for item in exchange_format
    ]
