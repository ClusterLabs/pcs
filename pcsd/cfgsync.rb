require 'fileutils'
require 'rexml/document'
require 'digest/sha1'

require 'config.rb'
require 'corosyncconf.rb'

CFG_COROSYNC_CONF = "/etc/corosync/corosync.conf" unless defined? CFG_COROSYNC_CONF
CFG_CLUSTER_CONF = "/etc/cluster/cluster.conf" unless defined? CFG_CLUSTER_CONF
CFG_PCSD_SETTINGS = "pcs_settings.conf" unless defined? CFG_PCSD_SETTINGS

module Cfgsync
  class Config
    include Comparable

    # set @name, @file_path, @file_perm in ancestors
    class << self
      attr_reader :name, :file_path, :file_perm
    end

    def self.from_text(text)
      return self.new(text)
    end

    def self.from_file()
      begin
        file = nil
        file = File.open(@file_path, File::RDONLY)
        file.flock(File::LOCK_SH)
        return self.from_text(file.read())
      rescue => e
        $logger.warn "Cannot read config file: #{e.message}"
        raise
      ensure
        unless file.nil?
          file.flock(File::LOCK_UN)
          file.close()
        end
      end
    end

    def self.backup()
      begin
        FileUtils.cp(@file_path, @file_path + "." + Time.now.to_i.to_s)
      rescue => e
        $logger.debug "Exception trying to backup #{self.name}: #{e}"
      end
    end

    def text()
      return @text
    end

    def text=(text)
      @text = text
      self.clean_cache()
      return self
    end

    def hash()
      return @hash ||= self.get_hash()
    end

    def version()
      return @version ||= self.get_version().to_i()
    end

    def version=(new_version)
      self.text = self.set_version(new_version)
      return self
    end

    def save()
      begin
        file = nil
        file = File.open(self.class.file_path, 'w', self.class.file_perm)
        file.flock(File::LOCK_EX)
        file.write(self.text)
      rescue => e
        $logger.error "Cannot write to config file: #{e.message}"
        raise
      ensure
        unless file.nil?
          file.flock(File::LOCK_UN)
          file.close()
        end
      end
    end

    def <=>(other)
      if self.version == other.version
        return self.hash <=> other.hash
      else
        return self.version <=> other.version
      end
    end

    protected

    def initialize(text)
      self.text = text
    end

    def clean_cache()
      @hash = nil
      @version = nil
      return self
    end

    def get_hash()
      return Digest::SHA1.hexdigest(self.text)
    end
  end


  class PcsdSettings < Config
    @name = "pcs_settings.conf"
    @file_path = ::CFG_PCSD_SETTINGS
    @file_perm = 0644

    protected

    def get_version()
      return PCSConfig.new(self.text).data_version
    end

    def set_version(new_version)
      parsed = PCSConfig.new(self.text)
      parsed.data_version = new_version
      return parsed.text
    end
  end


  class ClusterConf < Config
    @name = "cluster.conf"
    @file_path = ::CFG_CLUSTER_CONF
    @file_perm = 0644

    protected

    def get_version()
      dom = REXML::Document.new(self.text)
      if dom.root and dom.root.name == 'cluster'
        return dom.root.attributes['config_version'].to_i
      end
      return 0
    end

    def set_version(new_version)
      dom = REXML::Document.new(self.text)
      if dom.root and dom.root.name == 'cluster'
        dom.root.attributes['config_version'] = new_version
      end
      return dom.to_s
    end
  end


  class CorosyncConf < Config
    @name = "corosync.conf"
    @file_path = ::CFG_COROSYNC_CONF
    @file_perm = 0644

    protected

    def get_version()
      parsed = ::CorosyncConf::parse_string(self.text)
      # mimic corosync behavior - the last config_version found is used
      version = nil
      parsed.sections('totem').each { |totem|
        totem.attributes('config_version').each { |attrib|
          version = attrib[1].to_i
        }
      }
      return version ? version : 0
    end

    def set_version(new_version)
      parsed = ::CorosyncConf::parse_string(self.text)
      parsed.sections('totem').each { |totem|
        totem.set_attribute('config_version', new_version)
      }
      return parsed.text
    end
  end


  def Cfgsync::cluster_cfg_class()
    return ISRHEL6 ? ClusterConf : CorosyncConf
  end
end
