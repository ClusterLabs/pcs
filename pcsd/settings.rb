PCSD_EXEC_LOCATION = '/usr/lib/pcsd/'
PCSD_VAR_LOCATION = '/var/lib/pcsd/'

CRT_FILE = PCSD_VAR_LOCATION + 'pcsd.crt'
KEY_FILE = PCSD_VAR_LOCATION + 'pcsd.key'
COOKIE_FILE = PCSD_VAR_LOCATION + 'pcsd.cookiesecret'

OCF_ROOT = "/usr/lib/ocf"
HEARTBEAT_AGENTS_DIR = "/usr/lib/ocf/resource.d/heartbeat/"
PACEMAKER_AGENTS_DIR = "/usr/lib/ocf/resource.d/pacemaker/"
NAGIOS_METADATA_DIR = '/usr/share/pacemaker/nagios/plugins-metadata/'
PENGINE = "/usr/libexec/pacemaker/pengine"
CIB_BINARY = '/usr/libexec/pacemaker/cib'
CRM_MON = "/usr/sbin/crm_mon"
CRM_NODE = "/usr/sbin/crm_node"
CRM_ATTRIBUTE = "/usr/sbin/crm_attribute"
COROSYNC_BINARIES = "/usr/sbin/"
CMAN_TOOL = "/usr/sbin/cman_tool"
PACEMAKERD = "/usr/sbin/pacemakerd"
CIBADMIN = "/usr/sbin/cibadmin"
SBD_CONFIG = '/etc/sysconfig/sbd'
CIB_PATH='/var/lib/pacemaker/cib/cib.xml'

COROSYNC_QDEVICE_NET_SERVER_CERTS_DIR = "/etc/corosync/qdevice/net/qnetd/nssdb"
COROSYNC_QDEVICE_NET_SERVER_CA_FILE = (
  COROSYNC_QDEVICE_NET_SERVER_CERTS_DIR + "/qnetd-cacert.crt"
)
COROSYNC_QDEVICE_NET_CLIENT_CERTS_DIR = "/etc/corosync/qdevice/net/node/nssdb"

SUPERUSER = 'hacluster'
ADMIN_GROUP = 'haclient'
$user_pass_file = "pcs_users.conf"
