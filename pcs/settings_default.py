import multiprocessing
import os.path

systemctl_binary = "/bin/systemctl"
chkconfig_binary = "/sbin/chkconfig"
service_binary = "/sbin/service"
pacemaker_binaries = "/usr/sbin/"
crm_resource_binary = os.path.join(pacemaker_binaries, "crm_resource")
corosync_binaries = "/usr/sbin/"
corosync_qnet_binaries = "/usr/bin/"
corosync_conf_dir = "/etc/corosync/"
corosync_conf_file = os.path.join(corosync_conf_dir, "corosync.conf")
corosync_uidgid_dir = os.path.join(corosync_conf_dir, "uidgid.d/")
corosync_qdevice_net_server_certs_dir = os.path.join(
    corosync_conf_dir, "qnetd/nssdb"
)
corosync_qdevice_net_client_certs_dir = os.path.join(
    corosync_conf_dir, "qdevice/net/nssdb"
)
corosync_qdevice_net_client_ca_file_name = "qnetd-cacert.crt"
corosync_authkey_file = os.path.join(corosync_conf_dir, "authkey")
# Must be set to 256 for corosync to work in FIPS environment.
corosync_authkey_bytes = 256
corosync_log_file = "/var/log/cluster/corosync.log"
pacemaker_authkey_file = "/etc/pacemaker/authkey"
# Using the same value as for corosync. Higher values MAY work in FIPS.
pacemaker_authkey_bytes = 256
pcsd_token_max_bytes = 256
booth_authkey_file_mode = 0o600
# Booth does not support keys longer than 64 bytes.
booth_authkey_bytes = 64
cluster_conf_file = "/etc/cluster/cluster.conf"
fence_agent_binaries = "/usr/sbin/"
pacemaker_schedulerd = "/usr/libexec/pacemaker/pacemaker-schedulerd"
pacemaker_controld = "/usr/libexec/pacemaker/pacemaker-controld"
pacemaker_based = "/usr/libexec/pacemaker/pacemaker-based"
pacemaker_fenced = "/usr/libexec/pacemaker/pacemaker-fenced"
pcs_version = "0.10.8"
crm_report = os.path.join(pacemaker_binaries, "crm_report")
crm_rule = os.path.join(pacemaker_binaries, "crm_rule")
crm_verify = os.path.join(pacemaker_binaries, "crm_verify")
cibadmin = os.path.join(pacemaker_binaries, "cibadmin")
crm_mon_schema = "/usr/share/pacemaker/crm_mon.rng"
agent_metadata_schema = "/usr/share/resource-agents/ra-api-1.dtd"
pcsd_var_location = "/var/lib/pcsd/"
pcsd_ruby_socket = "/run/pcsd-ruby.socket"
pcsd_cert_location = os.path.join(pcsd_var_location, "pcsd.crt")
pcsd_key_location = os.path.join(pcsd_var_location, "pcsd.key")
pcsd_known_hosts_location = os.path.join(pcsd_var_location, "known-hosts")
pcsd_users_conf_location = os.path.join(pcsd_var_location, "pcs_users.conf")
pcsd_settings_conf_location = os.path.join(
    pcsd_var_location, "pcs_settings.conf"
)
pcsd_dr_config_location = os.path.join(pcsd_var_location, "disaster-recovery")
pcsd_exec_location = "/usr/lib/pcsd/"
pcsd_log_location = "/var/log/pcsd/pcsd.log"
pcsd_default_port = 2224
pcsd_config = "/etc/sysconfig/pcsd"
cib_dir = "/var/lib/pacemaker/cib/"
pacemaker_uname = "hacluster"
pacemaker_gname = "haclient"
sbd_binary = "/usr/sbin/sbd"
sbd_watchdog_default = "/dev/watchdog"
sbd_config = "/etc/sysconfig/sbd"
# this limit is also mentioned in docs, change there as well
sbd_max_device_num = 3
# message types are also mentioned in docs, change there as well
sbd_message_types = ["test", "reset", "off", "crashdump", "exit", "clear"]
pacemaker_wait_timeout_status = 124
booth_config_dir = "/etc/booth"
booth_binary = "/usr/sbin/booth"
default_request_timeout = 60
pcs_bundled_dir = "/usr/lib/pcs/bundled/"
pcs_bundled_pacakges_dir = os.path.join(pcs_bundled_dir, "packages")

default_ssl_ciphers = "DEFAULT:!RC4:!3DES:@STRENGTH"

# Ssl options are based on default options in python (maybe with some extra
# options). Format here is the same as the PCSD_SSL_OPTIONS environment
# variable format (string with coma as a delimiter).
default_ssl_options = ",".join(
    [
        "OP_NO_COMPRESSION",
        "OP_CIPHER_SERVER_PREFERENCE",
        "OP_SINGLE_DH_USE",
        "OP_SINGLE_ECDH_USE",
        "OP_NO_SSLv2",
        "OP_NO_SSLv3",
        "OP_NO_TLSv1",
        "OP_NO_TLSv1_1",
        "OP_NO_RENEGOTIATION",
    ]
)
# Set pcsd_gem_path to None if there are no bundled ruby gems and the path does
# not exists.
pcsd_gem_path = "vendor/bundle/ruby"
ruby_executable = "/usr/bin/ruby"

gui_session_lifetime_seconds = 60 * 60

# Scheduler settings
async_api_scheduler_enable = False
async_api_scheduler_interval_ms = 300

worker_count = multiprocessing.cpu_count()
worker_task_limit = 5

task_unresponsive_timeout_seconds = 60 * 60
task_abandoned_timeout_seconds = 1 * 60

worker_logs_path = "/var/log/pcsd/worker_logs/"
async_api_log_filename = "/var/log/pcsd/async_api.log"
