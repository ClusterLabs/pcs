require 'logger'
require 'open4'
require 'pathname'
require 'stringio'

require 'settings.rb'


def is_systemctl()
  SYSTEMD_UNIT_PATHS.each { |path|
    return true if File.directory?(path)
  }
  return false
end

def get_current_pcsd_path()
  return Pathname.new(
      File.expand_path(File.dirname(__FILE__))
    ).realpath
end

def get_system_or_local_path(system_path, local_path)
  current_pcsd_path = get_current_pcsd_path().to_s
  if current_pcsd_path == File.expand_path(PCSD_EXEC_LOCATION)
    # i.e. this file is inside the system pcsd directory => the system
    # executable is used
    return system_path
  else
    # i.e. this file is outside the system pcsd directory => the local
    # (development) executable is used
    return File.join(current_pcsd_path, local_path)
  end
end

def get_pcs_path()
  return get_system_or_local_path(PCS_EXEC, "../pcs/pcs")
end

def get_pcs_internal_path()
  return get_system_or_local_path(PCS_INTERNAL_EXEC, "../pcs/pcs_internal")
end

# unique instance signature, allows detection of daemon restarts
COROSYNC = File.join(COROSYNC_BINARIES, "corosync")
ISSYSTEMCTL = is_systemctl
COROSYNC_CMAPCTL = File.join(COROSYNC_BINARIES, "corosync-cmapctl")
COROSYNC_QUORUMTOOL = File.join(COROSYNC_BINARIES, "corosync-quorumtool")

if not defined? $cur_node_name
  $cur_node_name = `/bin/hostname`.chomp
end

if ENV['PCSD_RESTART_AFTER_REQUESTS']
  begin
    PCSD_RESTART_AFTER_REQUESTS = Integer(ENV['PCSD_RESTART_AFTER_REQUESTS'])
  rescue ArgumentError
    # The value will be left on default from constant definition in settings.rb
  else
    if
      PCSD_RESTART_AFTER_REQUESTS != 0 &&
      PCSD_RESTART_AFTER_REQUESTS < PCSD_RESTART_AFTER_REQUESTS_MIN
    then
      PCSD_RESTART_AFTER_REQUESTS = PCSD_RESTART_AFTER_REQUESTS_MIN
    end
  end
end

if not defined? $request_counter
  $request_counter = 0
end

def configure_logger()
  logger = Logger.new(StringIO.new())
  logger.formatter = proc {|severity, datetime, progname, msg|
    if Thread.current.key?(:pcsd_logger_container)
      Thread.current[:pcsd_logger_container] << {
        :level => severity,
        :timestamp_usec => (datetime.to_f * 1000000).to_i,
        :message => msg,
      }
    else
      STDERR.puts("#{datetime} #{progname} #{severity} #{msg}")
    end
  }
  return logger
end

def early_log(logger)
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
end

def get_capabilities(logger)
  capabilities = []
  capabilities_pcsd = []
  begin
    filename = (get_current_pcsd_path() + Pathname.new('capabilities.xml')).to_s
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
