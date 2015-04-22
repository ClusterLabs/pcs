require 'fileutils'
require 'rexml/document'
require 'digest/sha1'

require 'config.rb'
require 'corosyncconf.rb'
require 'pcs.rb'

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
        $logger.info(
          "Saved config #{self.class.name} version #{self.version} #{self.hash}"
        )
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


  class ConfigPublisher
    def initialize(configs, nodes, cluster_name)
      @configs = configs
      @nodes = nodes
      @cluster_name = cluster_name
      @published_configs_names = @configs.collect { |cfg|
        cfg.class.name
      }
    end

    def publish()
      @configs.each { |cfg|
        cfg.version += 1
        $logger.info(
          "Broadcasting config #{cfg.class.name} version #{cfg.version} #{cfg.hash}"
        )
      }

      data = self.prepare_request_data(@configs, @cluster_name)
      node_response = {}
      threads = []
      @nodes.each { |node|
        threads << Thread.new {
          code, out = send_request_with_token(node, 'set_configs', true, data)
          if 200 == code
            begin
              node_response[node] = JSON.parse(out)
            rescue JSON::ParserError
            end
          else
            begin
              response = JSON.parse(out)
              if true == response['notauthorized'] or true == response['notoken']
                node_response[node] = {'status' => 'notauthorized'}
              end
            rescue JSON::ParserError
            end
          end
          if not node_response.key?(node)
            node_response[node] = {'status' => 'error'}
          end
        }
      }
      threads.each { |t| t.join }

      node_response.each { |node, response|
        $logger.debug("Broadcasting config response from #{node}: #{response}")
      }
      return [
        self.get_old_local_configs(node_response, @published_configs_names),
        node_response
      ]
    end

    protected

    def prepare_request_data(configs, cluster_name)
      data = {
        'configs' => {},
      }
      data['cluster_name'] = cluster_name if cluster_name
      configs.each { |cfg|
        data['configs'][cfg.class.name] = {
          'type' => 'file',
          'text' => cfg.text,
        }
      }
      return {
        'configs' => JSON.generate(data)
      }
    end

    def get_old_local_configs(node_response, published_configs_names)
      old_local_configs = []
      node_response.each { |node, response|
        if 'ok' == response['status'] and response['result']
          response['result'].each { |cfg_name, status|
            if 'rejected' == status and published_configs_names.include?(cfg_name)
              old_local_configs << cfg_name
            end
          }
        end
      }
      return old_local_configs.uniq
    end
  end


  class ConfigFetcher
    def initialize(config_classes, nodes, cluster_name)
      @config_classes = config_classes
      @nodes = nodes
      @cluster_name = cluster_name
    end

    def fetch()
      configs_cluster = self.filter_configs_cluster(
        self.get_configs_cluster(@nodes, @cluster_name),
        @config_classes
      )

      newest_configs_cluster = {}
      configs_cluster.each { |name, cfgs|
        newest_configs_cluster[name] = self.find_newest_config(cfgs)
      }
      configs_local = self.get_configs_local()

      to_update_locally = []
      to_update_in_cluster = []
      configs_local.each { |name, local_cfg|
        if newest_configs_cluster.key?(name)
          if newest_configs_cluster[name].version > local_cfg.version
            to_update_locally << newest_configs_cluster[name]
          elsif newest_configs_cluster[name].version < local_cfg.version
            to_update_in_cluster << local_cfg
          elsif newest_configs_cluster[name].hash != local_cfg.hash
            to_update_locally << newest_configs_cluster[name]
          end
        end
      }
      return to_update_locally, to_update_in_cluster
    end

    protected

    def get_configs_local()
      return Cfgsync::get_configs_local()
    end

    def get_configs_cluster(nodes, cluster_name)
      data = {
        'cluster_name' => cluster_name,
      }

      $logger.info 'Fetching configs from the cluster'
      threads = []
      node_configs = {}
      nodes.each { |node|
        threads << Thread.new {
          code, out = send_request_with_token(node, 'get_configs', false, data)
          if 200 == code
            begin
              parsed = JSON::parse(out)
              if 'ok' == parsed['status'] and cluster_name == parsed['cluster_name']
                node_configs[node], _ = Cfgsync::sync_msg_to_configs(parsed)
              end
            rescue JSON::ParserError
            end
          end
        }
      }
      threads.each { |t| t.join }
      return node_configs
    end

    def filter_configs_cluster(node_configs, wanted_configs_classes)
      configs = {}
      node_configs.each { |node, cfg_map|
        cfg_map.each { |name, cfg|
          if wanted_configs_classes.include?(cfg.class)
            configs[cfg.class.name] = configs[cfg.class.name] || []
            configs[cfg.class.name] << cfg
          end
        }
      }
      return configs
    end

    def find_newest_config(config_list)
      newest_version = config_list.collect { |cfg| cfg.version }.max
      hash_config = {}
      hash_count = {}
      config_list.each { |cfg|
        if cfg.version == newest_version
          hash_config[cfg.hash] = cfg
          if hash_count.key?(cfg.hash)
            hash_count[cfg.hash] += 1
          else
            hash_count[cfg.hash] = 1
          end
        end
      }
      most_frequent_hash_count = hash_count.max_by { |hash, count| count }[1]
      most_frequent_hashes = hash_count.reject { |hash, count|
        count != most_frequent_hash_count
      }
      return hash_config[most_frequent_hashes.keys.max]
    end
  end


  def self.cluster_cfg_class()
    return ISRHEL6 ? ClusterConf : CorosyncConf
  end

  def self.get_cfg_classes()
    return [PcsdSettings]
    # return [PcsdSettings, self.cluster_cfg_class]
  end

  def self.get_cfg_classes_by_name()
    classes = {}
    self.get_cfg_classes.each { |cfgclass|
      classes[cfgclass.name] = cfgclass
    }
    return classes
  end

  def self.sync_msg_to_configs(sync_msg)
    cfg_classes = self.get_cfg_classes_by_name
    configs = {}
    unknown_config_names = []
    sync_msg['configs'].each { |name, data|
      if cfg_classes[name]
        if 'file' == data['type'] and data['text'] and not data['text'].strip.empty?
          configs[name] = cfg_classes[name].from_text(data['text'])
        end
      else
        unknown_config_names << name
      end
    }
    return configs, unknown_config_names
  end

  def self.get_configs_local()
    configs = {}
    self.get_cfg_classes.each { |cfg_class|
      begin
        configs[cfg_class.name] = cfg_class.from_file
      rescue
      end
    }
    return configs
  end

  # save and sync updated config
  # return true on success, false on version conflict
  def self.save_sync_new_version(config, nodes, cluster_name, fetch_on_conflict)
    if not cluster_name or cluster_name.empty?
      # we run on a standalone host, no config syncing
      config.version += 1
      config.save()
      return true
    else
      # we run in a cluster so we need to sync the config
      publisher = ConfigPublisher.new([config], nodes, cluster_name)
      old_configs, _ = publisher.publish()
      if old_configs.include?(config.class.name)
        if fetch_on_conflict
          fetcher = ConfigFetcher.new([config.class], nodes, cluster_name)
          cfgs_to_save, _ = fetcher.fetch()
          cfgs_to_save.each { |cfg_to_save|
            cfg_to_save.save() if cfg_to_save.class == config.class
          }
        end
        return false
      end
      return true
    end
  end
end
