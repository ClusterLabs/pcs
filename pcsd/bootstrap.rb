require 'logger'

require 'settings.rb'


def get_rhel_version()
  if File.exists?('/etc/system-release')
    release = File.open('/etc/system-release').read
    match = /(\d+)\.(\d+)/.match(release)
    if match
      return match[1, 2].collect{ |x| x.to_i}
    end
  end
  return nil
end

def is_rhel6()
  version = get_rhel_version()
  return (version and version[0] == 6)
end

def is_systemctl()
  systemctl_paths = [
      '/usr/bin/systemctl',
      '/bin/systemctl',
      '/var/run/systemd/system',
  ]
  systemctl_paths.each { |path|
    return true if File.exist?(path)
  }
  return false
end

def get_pcs_path(pcsd_path)
  if PCSD_EXEC_LOCATION == pcsd_path or PCSD_EXEC_LOCATION == (pcsd_path + '/')
    return '/usr/sbin/pcs'
  else
    return '../pcs/pcs'
  end
end

PCS_VERSION = '0.9.142'
ISRHEL6 = is_rhel6
ISSYSTEMCTL = is_systemctl

COROSYNC = COROSYNC_BINARIES + "corosync"
if ISRHEL6
  COROSYNC_CMAPCTL = COROSYNC_BINARIES + "corosync-objctl"
else
  COROSYNC_CMAPCTL = COROSYNC_BINARIES + "corosync-cmapctl"
end
COROSYNC_QUORUMTOOL = COROSYNC_BINARIES + "corosync-quorumtool"

if not defined? $cur_node_name
  $cur_node_name = `hostname`.chomp
end

def configure_logger(log_device)
  logger = Logger.new(log_device)
  if ENV['PCSD_DEBUG'] and ENV['PCSD_DEBUG'].downcase == "true" then
    logger.level = Logger::DEBUG
    logger.info "PCSD Debugging enabled"
  else
    logger.level = Logger::INFO
  end

  if ISRHEL6
    logger.debug "Detected RHEL 6"
  else
    logger.debug "Did not detect RHEL 6"
  end
  return logger
end

