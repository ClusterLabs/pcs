mock = {
  cluster_status: {
    "cluster_name": "dwarf8",
    "error_list": [],
    "warning_list": [],
    "quorate": false,
    "status": "error",
    "node_list": [
      {
        "id": "",
        "error_list": [],
        "warning_list": [],
        "status": "offline",
        "quorum": null,
        "uptime": "0 days, 07:31:25",
        "name": "cat8",
        "services": {
            "pacemaker": {
                "installed": true,
                "running": false,
                "enabled": false
            },
            "pacemaker_remote": {
                "installed": false,
                "running": false,
                "enabled": false
            },
            "corosync": {
                "installed": true,
                "running": false,
                "enabled": false
            },
            "pcsd": {
                "installed": true,
                "running": true,
                "enabled": true
            },
            "sbd": {
                "installed": true,
                "running": false,
                "enabled": true
            }
        },
        "corosync": false,
        "pacemaker": false,
        "corosync_enabled": false,
        "pacemaker_enabled": false,
        "pcsd_enabled": true,
        "sbd_config": {
            "SBD_DELAY_START": "no",
            "SBD_OPTS": "\"-n cat8\"",
            "SBD_PACEMAKER": "yes",
            "SBD_STARTMODE": "always",
            "SBD_WATCHDOG_DEV": "/dev/watchdog",
            "SBD_WATCHDOG_TIMEOUT": "5"
        },
        "status_version": "2"
      },
      {
          "id": "",
          "error_list": [],
          "warning_list": [],
          "status": "offline",
          "quorum": null,
          "uptime": "4 days, 05:03:37",
          "name": "ace8",
          "services": {
              "pacemaker": {
                  "installed": true,
                  "running": false,
                  "enabled": false
              },
              "pacemaker_remote": {
                  "installed": false,
                  "running": false,
                  "enabled": false
              },
              "corosync": {
                  "installed": true,
                  "running": false,
                  "enabled": false
              },
              "pcsd": {
                  "installed": true,
                  "running": false,
                  "enabled": true
              },
              "sbd": {
                  "installed": true,
                  "running": false,
                  "enabled": true
              }
          },
          "corosync": false,
          "pacemaker": false,
          "corosync_enabled": false,
          "pacemaker_enabled": false,
          "pcsd_enabled": true,
          "sbd_config": {
              "SBD_DELAY_START": "no",
              "SBD_OPTS": "\"-n ace8\"",
              "SBD_PACEMAKER": "yes",
              "SBD_STARTMODE": "always",
              "SBD_WATCHDOG_DEV": "/dev/watchdog",
              "SBD_WATCHDOG_TIMEOUT": "5"
          },
          "status_version": "2"
      }
    ],
    "resource_list": [],
    "available_features": [
        "constraint_colocation_set",
        "sbd",
        "ticket_constraints",
        "moving_resource_in_group",
        "unmanaged_resource",
        "alerts",
        "hardened_cluster"
    ],
    "pcsd_capabilities": [
        "booth.set-config",
        "booth.set-config.multiple",
        "booth.get-config",
        "cluster.config.restore-local",
        "cluster.create",
        "cluster.create.separated-name-and-address",
        "cluster.create.transport.knet",
        "cluster.create.transport.udp-udpu",
        "cluster.create.transport.udp-udpu.no-rrp",
        "cluster.destroy",
        "corosync.config.get",
        "corosync.config.set",
        "corosync.qdevice.model.net.certificates",
        "corosync.quorum.status",
        "corosync.quorum.device.client",
        "corosync.quorum.device.client.model.net.certificates",
        "node.add",
        "node.add.separated-name-and-address",
        "node.remove",
        "node.remove.list",
        "node.start-stop-enable-disable",
        "node.start-stop-enable-disable.stop-component",
        "node.restart",
        "node.attributes",
        "node.standby",
        "node.utilization",
        "pcmk.acl.role",
        "pcmk.acl.role.delete-with-users-groups-implicit",
        "pcmk.alert",
        "pcmk.cib.get",
        "pcmk.constraint.location.simple",
        "pcmk.constraint.location.simple.rule",
        "pcmk.constraint.colocation.simple",
        "pcmk.constraint.colocation.set",
        "pcmk.constraint.order.simple",
        "pcmk.constraint.order.set",
        "pcmk.constraint.ticket.simple",
        "pcmk.constraint.ticket.set",
        "pcmk.properties.cluster",
        "pcmk.properties.cluster.describe",
        "pcmk.resource.create",
        "pcmk.resource.create.no-master",
        "pcmk.resource.create.promotable",
        "pcmk.resource.delete",
        "pcmk.resource.delete.list",
        "pcmk.resource.update",
        "pcmk.resource.update-meta",
        "pcmk.resource.group",
        "pcmk.resource.clone",
        "pcmk.resource.promotable",
        "pcmk.resource.enable-disable",
        "pcmk.resource.manage-unmanage",
        "pcmk.resource.manage-unmanage.list",
        "pcmk.resource.utilization",
        "pcmk.resource.cleanup.one-resource",
        "pcmk.resource.refresh.one-resource",
        "pcmk.stonith.create",
        "pcmk.stonith.update",
        "pcmk.stonith.levels",
        "pcs.auth.server",
        "pcs.auth.separated-name-and-address",
        "pcs.auth.no-bidirectional",
        "pcs.auth.known-host-change",
        "pcs.auth.export-cluster-known-hosts",
        "pcs.automatic-pcs-configs-sync",
        "pcs.permissions",
        "pcs.daemon-ssl-cert.set",
        "resource-agents.describe",
        "resource-agents.list",
        "stonith-agents.describe",
        "stonith-agents.list",
        "sbd",
        "sbd-node",
        "sbd-node.shared-block-device",
        "status.pcmk.local-node"
    ],
    "groups": [],
    "constraints": {},
    "cluster_settings": {},
    "need_ring1_address": false,
    "acls": {},
    "username": "hacluster",
    "fence_levels": {},
    "node_attr": {},
    "nodes_utilization": {},
    "alerts": null,
    "known_nodes": [
        "ace8",
        "cat8"
    ],
    "corosync_online": [],
    "corosync_offline": [
        "ace8",
        "cat8"
    ],
    "pacemaker_online": [],
    "pacemaker_offline": [],
    "pacemaker_standby": [],
    "status_version": "2"
  }
};
