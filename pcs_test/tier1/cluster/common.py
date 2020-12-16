from textwrap import dedent


def fixture_corosync_conf_minimal():
    return dedent(
        """\
        totem {
            version: 2
            cluster_name: cluster_name
            transport: knet
            ip_version: ipv6
            crypto_cipher: aes256
            crypto_hash: sha256
        }

        nodelist {
            node {
                ring0_addr: node1_addr
                name: node1
                nodeid: 1
            }

            node {
                ring0_addr: node2_addr
                name: node2
                nodeid: 2
            }
        }

        quorum {
            provider: corosync_votequorum
            two_node: 1
        }

        logging {
            to_logfile: yes
            logfile: /var/log/cluster/corosync.log
            to_syslog: yes
            timestamp: on
        }
        """
    )
