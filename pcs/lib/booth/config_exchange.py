from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from pcs.lib.booth.config_structure import ConfigItem

EXCHANGE_PRIMITIVES = ["authfile"]
EXCHANGE_LISTS = [
    ("site", "sites"),
    ("arbitrator", "arbitrators"),
    ("ticket", "tickets"),
]


def to_exchange_format(booth_configuration):
    exchange_lists = dict(EXCHANGE_LISTS)
    exchange = dict(
        (exchange_key, []) for exchange_key in exchange_lists.values()
    )

    for key, value, _ in booth_configuration:
        if key in exchange_lists:
            exchange[exchange_lists[key]].append(value)
        if key in EXCHANGE_PRIMITIVES:
            exchange[key] = value

    return exchange


def from_exchange_format(exchange_format):
    booth_config = []
    for key in EXCHANGE_PRIMITIVES:
        if key in exchange_format:
            booth_config.append(ConfigItem(key, exchange_format[key]))

    for key, exchange_key in EXCHANGE_LISTS:
        booth_config.extend([
            ConfigItem(key, value)
            for value in exchange_format.get(exchange_key, [])
        ])
    return booth_config
