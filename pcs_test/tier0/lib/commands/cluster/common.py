TOTEM_TEMPLATE = """\
totem {{
    transport: {transport_type}\
{totem_options}{transport_options}{compression_options}{crypto_options}
}}
"""


def fixture_totem(
    transport_type="knet",
    transport_options=None,
    compression_options=None,
    crypto_options=None,
    totem_options=None,
):
    def options_fixture(options, prefix=""):
        options = options or {}
        template = "\n    {prefix}{option}: {value}"
        return "".join(
            [
                template.format(prefix=prefix, option=o, value=v)
                for o, v in sorted(options.items())
            ]
        )

    return TOTEM_TEMPLATE.format(
        transport_type=transport_type,
        transport_options=options_fixture(transport_options),
        compression_options=options_fixture(
            compression_options, prefix="knet_compression_"
        ),
        crypto_options=options_fixture(crypto_options, prefix="crypto_"),
        totem_options=options_fixture(totem_options),
    )
