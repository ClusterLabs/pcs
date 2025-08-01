from textwrap import dedent

from pcs_test.tools.misc import outdent

QDEVICE_HOST = "qdevice.host"
CLUSTER_NAME = "myCluster"
CLUSTER_UUID = "abcdef0123456789abcdef0123456789"


def get_two_node(nodes_num):
    if nodes_num == 2:
        return [("two_node", "1")]
    return []


def _corosync_options_fixture(option_list, indent_level=2):
    indent = indent_level * 4 * " "
    return "".join(
        [f"{indent}{option}: {value}\n" for option, value in option_list]
    )


def corosync_conf_fixture(
    node_list=(),
    quorum_options=(),
    qdevice_net=False,
    cluster_name=CLUSTER_NAME,
):
    nodes = [
        dedent(
            """\
                node {{
            {options}    }}
            """
        ).format(options=_corosync_options_fixture(node))
        for node in node_list
    ]
    device = ""
    if qdevice_net:
        device = outdent(
            f"""
                device {{
                    model: net

                    net {{
                        host: {QDEVICE_HOST}
                    }}
                }}
            """
        )
    return dedent(
        """\
        totem {{
            version: 2
            cluster_name: {cluster_name}
            transport: knet
        }}

        nodelist {{
        {nodes}}}

        quorum {{
            provider: corosync_votequorum
        {quorum}{device}}}

        logging {{
            to_logfile: yes
            logfile: /var/log/cluster/corosync.log
            to_syslog: yes
        }}
        """
    ).format(
        cluster_name=cluster_name,
        nodes="\n".join(nodes),
        quorum=_corosync_options_fixture(quorum_options, indent_level=1),
        device=device,
    )


def corosync_node_fixture(node_id, node, addrs):
    return [(f"ring{i}_addr", addr) for i, addr in enumerate(addrs)] + [
        ("name", node),
        ("nodeid", str(node_id)),
    ]


def node_fixture(node, node_id, addr_suffix=""):
    return corosync_node_fixture(node_id, node, [f"{node}{addr_suffix}"])


TOTEM_TEMPLATE = """\
totem {{
    transport: {transport_type}{cluster_uuid}\
{totem_options}{transport_options}{compression_options}{crypto_options}
}}
"""


def fixture_totem(
    cluster_uuid=CLUSTER_UUID,
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

    if cluster_uuid:
        cluster_uuid = f"\n    cluster_uuid: {cluster_uuid}"

    return TOTEM_TEMPLATE.format(
        cluster_uuid=cluster_uuid or "",
        transport_type=transport_type,
        transport_options=options_fixture(transport_options),
        compression_options=options_fixture(
            compression_options, prefix="knet_compression_"
        ),
        crypto_options=options_fixture(crypto_options, prefix="crypto_"),
        totem_options=options_fixture(totem_options),
    )
