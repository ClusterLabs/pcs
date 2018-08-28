require 'logger'
require 'open4'
require 'pathname'

require 'settings.rb'


def is_systemctl()
  systemctl_paths = [
      '/run/systemd/system',
      '/var/run/systemd/system',
  ]
  systemctl_paths.each { |path|
    return true if File.directory?(path)
  }
  return false
end

def get_pcsd_path()
  return Pathname.new(
      File.expand_path(File.dirname(__FILE__))
    ).realpath
end

def get_pcs_path()
  pcsd_path = get_pcsd_path().to_s
  if PCSD_EXEC_LOCATION == pcsd_path or PCSD_EXEC_LOCATION == (pcsd_path + '/')
    return PCS_EXEC
  else
    return pcsd_path + '/../pcs/pcs'
  end
end

PCS_VERSION = '0.10.0'
# unique instance signature, allows detection of dameon restarts
COROSYNC = COROSYNC_BINARIES + "corosync"
ISSYSTEMCTL = is_systemctl
COROSYNC_CMAPCTL = COROSYNC_BINARIES + "corosync-cmapctl"
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

  if ISSYSTEMCTL
    logger.debug "Detected systemd is in use"
  else
    logger.debug "Detected systemd is not in use"
  end
  return logger
end

def get_capabilities(logger)
  capabilities = []
  capabilities_pcsd = []
  begin
    filename = (get_pcsd_path() + Pathname.new('capabilities.xml')).to_s
    capabilities_xml = REXML::Document.new(File.new(filename))
    capabilities_xml.elements.each('.//capability') { |feat_xml|
      feat = {}
      feat_xml.attributes.each() { |name, value|
        feat[name] = value
      }
      feat['description'] = ''
      if feat_xml.elements['description']
        feat['description'] = feat_xml.elements['description'].text.strip
      end
      capabilities << feat
    }
    capabilities.each { |feat|
      if feat['in-pcsd'] == '1'
        capabilities_pcsd << feat['id']
      end
    }
  rescue => e
    logger.error(
      "Cannot read capabilities definition file '#{filename}': '#{e}'"
    )
    return [], []
  end
  return capabilities, capabilities_pcsd
end
