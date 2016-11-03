require 'logger'
require 'pathname'
require 'open4'

require 'settings.rb'


def is_rhel6()
  # Checking corosync version works in most cases and supports non-rhel
  # distributions as well as running (manually compiled) corosync2 on rhel6.
  # - corosync2 does not support cman at all
  # - corosync1 runs with cman on rhel6
  # - corosync1 can be used without cman, but we don't support it anyways
  # - corosync2 is the default result if errors occur
  out = ''
  status = Open4::popen4(COROSYNC, '-v') { |pid, stdin, stdout, stderr|
    out = stdout.readlines()
  }
  retval = status.exitstatus
  return false if retval != 0
  match = /version\D+(\d+)/.match(out.join())
  return (match and match[1] == "1")
end

def is_systemctl()
  systemctl_paths = [
      '/usr/bin/systemctl',
      '/bin/systemctl',
      '/var/run/systemd/system',
      '/run/systemd/system',
  ]
  systemctl_paths.each { |path|
    return true if File.exist?(path)
  }
  return false
end

def get_pcs_path(pcsd_path)
  real_path = Pathname.new(pcsd_path).realpath.to_s
  if PCSD_EXEC_LOCATION == real_path or PCSD_EXEC_LOCATION == (real_path + '/')
    return '/usr/sbin/pcs'
  else
    return '../pcs/pcs'
  end
end

PCS_VERSION = '0.9.155'
COROSYNC = COROSYNC_BINARIES + "corosync"
ISRHEL6 = is_rhel6
ISSYSTEMCTL = is_systemctl
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

