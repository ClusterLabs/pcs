require 'fileutils'
require 'rexml/document'
require 'digest/sha1'

require 'settings.rb'
require 'config.rb'
require 'corosyncconf.rb'
require 'pcs.rb'
require 'auth.rb'

def token_file_path()
  filename = ENV['PCS_TOKEN_FILE']
  unless filename.nil?
    return filename
  end
  if Process.uid == 0
    return File.join(PCSD_VAR_LOCATION, 'tokens')
  end
  return File.expand_path('~/.pcs/tokens')
end

def settings_file_path()
  current_dir = File.expand_path(File.dirname(__FILE__))
  if PCSD_EXEC_LOCATION == current_dir or PCSD_EXEC_LOCATION == (current_dir + '/')
    return File.join(PCSD_VAR_LOCATION, 'pcs_settings.conf')
  else
    return File.join(current_dir, 'pcs_settings.conf')
  end
end

CFG_COROSYNC_CONF = "/etc/corosync/corosync.conf" unless defined? CFG_COROSYNC_CONF
CFG_CLUSTER_CONF = "/etc/cluster/cluster.conf" unless defined? CFG_CLUSTER_CONF
CFG_PCSD_SETTINGS = settings_file_path() unless defined? CFG_PCSD_SETTINGS
CFG_PCSD_TOKENS = token_file_path() unless defined? CFG_PCSD_TOKENS

CFG_SYNC_CONTROL = File.join(PCSD_VAR_LOCATION, 'cfgsync_ctl') unless defined? CFG_SYNC_CONTROL

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

    def self.from_file(default=nil)
      begin
        file = nil
        file = File.open(@file_path, File::RDONLY)
        file.flock(File::LOCK_SH)
        return self.from_text(file.read())
      rescue => e
        $logger.warn(
          "Cannot read config '#{@name}' from '#{@file_path}': #{e.message}"
        )
        return self.from_text(default) if default
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
        $logger.debug("Exception when backing up config '#{self.name}': #{e}")
        return
      end
      begin
        self.remove_old_backups()
      rescue => e
        $logger.debug("Exception when removing old backup files: #{e}")
      end
    end

    def self.remove_old_backups()
      backup_files = []
      Dir.glob(@file_path + '.*') { |path|
        if File.file?(path)
          match = path.match(/^#{@file_path}\.(\d+)$/)
          if match
            backup_files << [match[1].to_i(), path]
          end
        end
      }
      backup_count = ConfigSyncControl::file_backup_count()
      to_delete = backup_files.sort()[0..-(backup_count + 1)]
      return if not to_delete
      to_delete.each { |timestamp, path|
        File.delete(path)
      }
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
          "Saved config '#{self.class.name}' version #{self.version} #{self.hash} to '#{self.class.file_path}'"
        )
      rescue => e
        $logger.error(
          "Cannot save config '#{self.class.name}': #{e.message}"
        )
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


  class PcsdTokens < Config
    @name = 'tokens'
    @file_path = ::CFG_PCSD_TOKENS
    @file_perm = 0600

    def self.backup()
    end

    def save()
      dirname = File.dirname(self.class.file_path)
      if not ENV['PCS_TOKEN_FILE'] and not File.directory?(dirname)
        FileUtils.mkdir_p(dirname, {:mode => 0700})
      end
      super
    end

    protected

    def get_version()
      return PCSTokens.new(self.text).data_version
    end

    def set_version(new_version)
      parsed = PCSTokens.new(self.text)
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


  class ConfigSyncControl
    @thread_interval_default = 60
    @thread_interval_minimum = 20
    @file_backup_count_default = 50
    @file_backup_count_minimum = 0

    def self.sync_thread_allowed?()
      data = self.load()
      return !(
        self.sync_thread_paused_data?(data)\
        or\
        self.sync_thread_disabled_data?(data)
      )
    end

    def self.sync_thread_paused?()
      return self.sync_thread_paused_data?(self.load())
    end

    def self.sync_thread_disabled?()
      return self.sync_thread_disabled_data?(self.load())
    end

    def self.sync_thread_interval()
      return self.get_integer_value(
        self.load()['thread_interval'],
        @thread_interval_default,
        @thread_interval_minimum
      )
    end

    def self.sync_thread_interval=(seconds)
      data = self.load()
      data['thread_interval'] = seconds
      return self.save(data)
    end

    def self.sync_thread_pause(semaphore_cfgsync, seconds=300)
      # wait for the thread to finish current run and disable it
      semaphore_cfgsync.synchronize {
        data = self.load()
        data['thread_paused_until'] = Time.now.to_i() + seconds.to_i()
        return self.save(data)
      }
    end

    def self.sync_thread_resume()
      data = self.load()
      if data['thread_paused_until']
        data.delete('thread_paused_until')
        return self.save(data)
      end
      return true
    end

    def self.sync_thread_disable(semaphore_cfgsync)
      # wait for the thread to finish current run and disable it
      semaphore_cfgsync.synchronize {
        data = self.load()
        data['thread_disabled'] = true
        return self.save(data)
      }
    end

    def self.sync_thread_enable()
      data = self.load()
      if data['thread_disabled']
        data.delete('thread_disabled')
        return self.save(data)
      end
      return true
    end

    def self.file_backup_count()
      return self.get_integer_value(
        self.load()['file_backup_count'],
        @file_backup_count_default,
        @file_backup_count_minimum
      )
    end

    def self.file_backup_count=(count)
      data = self.load()
      data['file_backup_count'] = count
      return self.save(data)
    end

    protected

    def self.sync_thread_paused_data?(data)
      if data['thread_paused_until']
        paused_until = data['thread_paused_until'].to_i()
        return ((paused_until > 0) and (Time.now().to_i() < paused_until))
      end
      return false
    end

    def self.sync_thread_disabled_data?(data)
      return data['thread_disabled']
    end

    def self.get_integer_value(value, default, minimum)
      return default if value.nil?
      if value.respond_to?(:match)
        return default if not value.match(/\A\s*[+-]?\d+\Z/)
      end
      return default if not value.respond_to?(:to_i)
      numeric = value.to_i()
      return minimum if numeric < minimum
      return numeric
    end

    def self.load()
      begin
        file = nil
        file = File.open(CFG_SYNC_CONTROL, File::RDONLY)
        file.flock(File::LOCK_SH)
        return JSON.parse(file.read())
      rescue => e
        $logger.debug("Cannot read config '#{CFG_SYNC_CONTROL}': #{e.message}")
        return {}
      ensure
        unless file.nil?
          file.flock(File::LOCK_UN)
          file.close()
        end
      end
    end

    def self.save(data)
      text = JSON.pretty_generate(data)
      begin
        file = nil
        file = File.open(CFG_SYNC_CONTROL, 'w', 0600)
        file.flock(File::LOCK_EX)
        file.write(text)
      rescue => e
        $logger.error("Cannot save config '#{CFG_SYNC_CONTROL}': #{e.message}")
        return false
      ensure
        unless file.nil?
          file.flock(File::LOCK_UN)
          file.close()
        end
      end
      return true
    end
  end


  class ConfigPublisher
    def initialize(session, configs, nodes, cluster_name, tokens={})
      @configs = configs
      @nodes = nodes
      @cluster_name = cluster_name
      @published_configs_names = @configs.collect { |cfg|
        cfg.class.name
      }
      @additional_tokens = tokens
      @session = session
    end

    def send(force=false)
      nodes_txt = @nodes.join(', ')
      @configs.each { |cfg|
        $logger.info(
          "Sending config '#{cfg.class.name}' version #{cfg.version} #{cfg.hash}"\
          + " to nodes: #{nodes_txt}"
        )
      }

      data = self.prepare_request_data(@configs, @cluster_name, force)
      node_response = {}
      threads = []
      @nodes.each { |node|
        threads << Thread.new {
          code, out = send_request_with_token(
            @session, node, 'set_configs', true, data, true, nil, 30,
            @additional_tokens
          )
          if 200 == code
            begin
              node_response[node] = JSON.parse(out)
            rescue JSON::ParserError
            end
          elsif 404 == code
            node_response[node] = {'status' => 'not_supported'}
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
          # old pcsd returns this instead of 404 if pacemaker isn't running there
          if node_response[node]['pacemaker_not_running']
            node_response[node] = {'status' => 'not_supported'}
          end
        }
      }
      threads.each { |t| t.join }

      node_response.each { |node, response|
        $logger.info("Sending config response from #{node}: #{response}")
      }

      return node_response
    end

    def publish()
      @configs.each { |cfg|
        cfg.version += 1
      }
      node_response = self.send()
      return [
        self.get_old_local_configs(node_response, @published_configs_names),
        node_response
      ]
    end

    protected

    def prepare_request_data(configs, cluster_name, force)
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
      data['force'] = true if force
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
    def initialize(session, config_classes, nodes, cluster_name)
      @config_classes = config_classes
      @nodes = nodes
      @cluster_name = cluster_name
      @session = session
    end

    def fetch_all()
      return self.filter_configs_cluster(
        self.get_configs_cluster(@nodes, @cluster_name),
        @config_classes
      )
    end

    def fetch()
      configs_cluster = self.fetch_all()

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
      return Cfgsync::get_configs_local(true)
    end

    def get_configs_cluster(nodes, cluster_name)
      data = {
        'cluster_name' => cluster_name,
      }

      $logger.debug 'Fetching configs from the cluster'
      threads = []
      node_configs = {}
      nodes.each { |node|
        threads << Thread.new {
          code, out = send_request_with_token(
            @session, node, 'get_configs', false, data
          )
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
    return [PcsdSettings, PcsdTokens]
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
        if 'file' == data['type'] and data['text']
          configs[name] = cfg_classes[name].from_text(data['text'])
        end
      else
        unknown_config_names << name
      end
    }
    return configs, unknown_config_names
  end

  def self.get_configs_local(with_missing=false)
    default = with_missing ? '' : nil
    configs = {}
    self.get_cfg_classes.each { |cfg_class|
      begin
        configs[cfg_class.name] = cfg_class.from_file(default)
      rescue
      end
    }
    return configs
  end

  # save and sync updated config
  # return true on success, false on version conflict
  def self.save_sync_new_version(config, nodes, cluster_name, fetch_on_conflict, tokens={})
    if not cluster_name or cluster_name.empty?
      # we run on a standalone host, no config syncing
      config.version += 1
      config.save()
      return true, {}
    else
      # we run in a cluster so we need to sync the config
      publisher = ConfigPublisher.new(
        PCSAuth.getSuperuserSession(), [config], nodes, cluster_name, tokens
      )
      old_configs, node_responses = publisher.publish()
      if old_configs.include?(config.class.name)
        if fetch_on_conflict
          fetcher = ConfigFetcher.new(
            PCSAuth.getSuperuserSession(), [config.class], nodes, cluster_name
          )
          cfgs_to_save, _ = fetcher.fetch()
          cfgs_to_save.each { |cfg_to_save|
            cfg_to_save.save() if cfg_to_save.class == config.class
          }
        end
        return false, node_responses
      end
      return true, node_responses
    end
  end

  def self.merge_tokens_files(orig_cfg, to_merge_cfgs, new_tokens)
    # Merge tokens files, use only newer tokens files, keep the most recent
    # tokens, make sure new_tokens are included.
    max_version = orig_cfg.version
    with_new_tokens = PCSTokens.new(orig_cfg.text)
    if to_merge_cfgs
      to_merge_cfgs.reject! { |item| item.version <= orig_cfg.version }
      if to_merge_cfgs.length > 0
        to_merge_cfgs.sort.each { |ft|
          with_new_tokens.tokens.update(PCSTokens.new(ft.text).tokens)
        }
        max_version = [to_merge_cfgs.max.version, max_version].max
      end
    end
    with_new_tokens.tokens.update(new_tokens)
    config_new = PcsdTokens.from_text(with_new_tokens.text)
    config_new.version = max_version
    return config_new
  end

  def self.save_sync_new_tokens(config, new_tokens, nodes, cluster_name)
    with_new_tokens = PCSTokens.new(config.text)
    with_new_tokens.tokens.update(new_tokens)
    config_new = PcsdTokens.from_text(with_new_tokens.text)
    if not cluster_name or cluster_name.empty?
      # we run on a standalone host, no config syncing
      config_new.version += 1
      config_new.save()
      return true, {}
    end
    # we run in a cluster so we need to sync the config
    publisher = ConfigPublisher.new(
      PCSAuth.getSuperuserSession(), [config_new], nodes, cluster_name,
      new_tokens
    )
    old_configs, node_responses = publisher.publish()
    if not old_configs.include?(config_new.class.name)
      # no node had newer tokens file, we are ok, everything done
      return true, node_responses
    end
    # get tokens from all nodes and merge them
    fetcher = ConfigFetcher.new(
      PCSAuth.getSuperuserSession(), [config_new.class], nodes, cluster_name
    )
    fetched_tokens = fetcher.fetch_all()[config_new.class.name]
    config_new = Cfgsync::merge_tokens_files(config, fetched_tokens, new_tokens)
    # and try to publish again
    return Cfgsync::save_sync_new_version(
      config_new, nodes, cluster_name, true, new_tokens
    )
  end
end
