import os.path

systemctl_binary = "/bin/systemctl"
chkconfig_binary = "/sbin/chkconfig"
service_binary = "/sbin/service"
pacemaker_binaries = "/usr/sbin/"
corosync_binaries = "/usr/sbin/"
corosync_qnet_binaries = "/usr/bin/"
ccs_binaries = "/usr/sbin/"
corosync_conf_dir = "/etc/corosync/"
corosync_conf_file = os.path.join(corosync_conf_dir, "corosync.conf")
corosync_uidgid_dir = os.path.join(corosync_conf_dir, "uidgid.d/")
corosync_qdevice_net_server_certs_dir = os.path.join(
    corosync_conf_dir,
    "qnetd/nssdb"
)
corosync_qdevice_net_client_certs_dir = os.path.join(
    corosync_conf_dir,
    "qdevice/net/nssdb"
)
corosync_qdevice_net_client_ca_file_name = "qnetd-cacert.crt"
cluster_conf_file = "/etc/cluster/cluster.conf"
fence_agent_binaries = "/usr/sbin/"
pengine_binary = "/usr/libexec/pacemaker/pengine"
crmd_binary = "/usr/libexec/pacemaker/crmd"
cib_binary = "/usr/libexec/pacemaker/cib"
stonithd_binary = "/usr/libexec/pacemaker/stonithd"
pcs_version = "0.9.155"
crm_report = pacemaker_binaries + "crm_report"
crm_verify = pacemaker_binaries + "crm_verify"
crm_mon_schema = '/usr/share/pacemaker/crm_mon.rng'
agent_metadata_schema = "/usr/share/resource-agents/ra-api-1.dtd"
pcsd_cert_location = "/var/lib/pcsd/pcsd.crt"
pcsd_key_location = "/var/lib/pcsd/pcsd.key"
pcsd_tokens_location = "/var/lib/pcsd/tokens"
pcsd_users_conf_location = "/var/lib/pcsd/pcs_users.conf"
pcsd_settings_conf_location = "/var/lib/pcsd/pcs_settings.conf"
pcsd_exec_location = "/usr/lib/pcsd/"
cib_dir = "/var/lib/pacemaker/cib/"
pacemaker_uname = "hacluster"
pacemaker_gname = "haclient"
sbd_watchdog_default = "/dev/watchdog"
sbd_config = "/etc/sysconfig/sbd"
pacemaker_wait_timeout_status = 62
booth_config_dir = "/etc/booth"
booth_binary = "/usr/sbin/booth"
