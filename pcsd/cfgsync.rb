require 'fileutils'
require 'rexml/document'
require 'digest/sha1'

require 'settings.rb'
require 'config.rb'
require 'corosyncconf.rb'
require 'pcs.rb'
require 'auth.rb'

def known_hosts_file_path()
  if Process.uid == 0
    return File.join(PCSD_VAR_LOCATION, KNOWN_HOSTS_FILE_NAME)
  end
  return File.join(File.expand_path('~/.pcs'), KNOWN_HOSTS_FILE_NAME)
end

# trick with defined? allows to prefill this constants in tests
CFG_COROSYNC_CONF = COROSYNC_CONF unless defined? CFG_COROSYNC_CONF
CFG_PCSD_SETTINGS = PCSD_SETTINGS_CONF_LOCATION unless defined? CFG_PCSD_SETTINGS
CFG_PCSD_KNOWN_HOSTS = known_hosts_file_path() unless defined? CFG_PCSD_KNOWN_HOSTS

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
        return self.on_file_missing(default) if not File::exist?(@file_path)
        file = nil
        file = File.open(@file_path, File::RDONLY)
        file.flock(File::LOCK_SH)
        return self.from_text(file.read())
      rescue => e
        return self.on_file_read_error(e, default)
      ensure
        unless file.nil?
          file.flock(File::LOCK_UN)
          file.close()
        end
      end
    end

    def self.exist?()
      return File::exist?(@file_path)
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
        # File.open(path, mode, options)
        # File.open(path, mode, perm, options)
        # In order to set permissions, the method must be called with 4 arguments.
        file = File.open(self.class.file_path, 'w', self.class.file_perm, {})
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

    def self.on_file_missing(default)
      $logger.warn(
        "Cannot read config '#{@name}' from '#{@file_path}': No such file"
      )
      return self.from_text(default) if default
      raise SystemCallError.new(@file_path, Errno::ENOENT::Errno)
    end

    def self.on_file_read_error(exception, default)
      $logger.warn(
        "Cannot read config '#{@name}' from '#{@file_path}': #{exception.message}"
      )
      return self.from_text(default) if default
      raise exception
    end

    def initialize(text)
      self.text = text
    end

    def clean_cache()
      @hash = nil
      @version = nil
      return self
    end

    def get_hash()
      return Digest::SHA1.hexdigest(self.text || '')
    end
  end


  class PcsdSettings < Config
    @name = "pcs_settings.conf"
    @file_path = ::CFG_PCSD_SETTINGS
    @file_perm = 0644

    protected

    def self.on_file_missing(default)
      return self.from_text(nil)
    end

    def self.on_file_read_error(exception, default)
      $logger.warn(
        "Cannot read config '#{@name}' from '#{@file_path}': #{exception.message}"
      )
      return self.from_text('')
    end

    def get_version()
      return PCSConfig.new(self.text).data_version
    end

    def set_version(new_version)
      parsed = PCSConfig.new(self.text)
      parsed.data_version = new_version
      return parsed.text
    end
  end


  class PcsdKnownHosts < Config
    @name = KNOWN_HOSTS_FILE_NAME
    @file_path = ::CFG_PCSD_KNOWN_HOSTS
    @file_perm = 0600

    def self.backup()
    end

    def save()
      dirname = File.dirname(self.class.file_path)
      if not File.directory?(dirname)
        FileUtils.mkdir_p(dirname, {:mode => 0700})
      end
      super
    end

    protected

    def self.on_file_missing(default)
      return self.from_text(nil)
    end

    def self.on_file_read_error(exception, default)
      $logger.warn(
        "Cannot read config '#{@name}' from '#{@file_path}': #{exception.message}"
      )
      return self.from_text(nil)
    end

    def get_version()
      return CfgKnownHosts.new(self.text).data_version
    end

    def set_version(new_version)
      parsed = CfgKnownHosts.new(self.text)
      parsed.data_version = new_version
      return parsed.text
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
    # intervals in seconds
    @thread_interval_default = 600
    @thread_interval_minimum = 60
    @thread_interval_previous_not_connected_default = 60
    @thread_interval_previous_not_connected_minimum = 20
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

    def self.sync_thread_interval_previous_not_connected()
      return self.get_integer_value(
        self.load()['thread_interval_previous_not_connected'],
        @thread_interval_previous_not_connected_default,
        @thread_interval_previous_not_connected_minimum
      )
    end

    def self.sync_thread_interval_previous_not_connected=(seconds)
      data = self.load()
      data['thread_interval_previous_not_connected'] = seconds
      return self.save(data)
    end

    def self.sync_thread_pause(seconds=300)
      data = self.load()
      data['thread_paused_until'] = Time.now.to_i() + seconds.to_i()
      return self.save(data)
    end

    def self.sync_thread_resume()
      data = self.load()
      if data['thread_paused_until']
        data.delete('thread_paused_until')
        return self.save(data)
      end
      return true
    end

    def self.sync_thread_disable()
      data = self.load()
      data['thread_disabled'] = true
      return self.save(data)
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
        # File.open(path, mode, options)
        # File.open(path, mode, perm, options)
        # In order to set permissions, the method must be called with 4 arguments.
        file = File.open(CFG_SYNC_CONTROL, 'w', 0600, {})
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
    def initialize(auth_user, configs, nodes, cluster_name, known_hosts=[])
      @auth_user = auth_user
      @configs = configs
      @nodes = nodes
      @cluster_name = cluster_name
      @additional_known_hosts = {}
      known_hosts.each{ |host| @additional_known_hosts[host.name] = host}
      @published_configs_names = @configs.collect { |cfg|
        cfg.class.name
      }
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
            @auth_user, node, 'set_configs', true, data, true, nil, 30,
            @additional_known_hosts
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
    def initialize(
      auth_user, config_classes, nodes, cluster_name, known_hosts=[]
    )
      @config_classes = config_classes
      @nodes = nodes
      @cluster_name = cluster_name
      @auth_user = auth_user
      @additional_known_hosts = {}
      known_hosts.each{ |host| @additional_known_hosts[host.name] = host}
    end

    def fetch_all()
      node_configs, node_connected = self.get_configs_cluster(
        @nodes, @cluster_name
      )
      filtered_configs = self.filter_configs_cluster(
        node_configs, @config_classes
      )
      return filtered_configs, node_connected
    end

    def fetch()
      configs_cluster, node_connected = self.fetch_all()

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
      return to_update_locally, to_update_in_cluster, node_connected
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
      connected_to = {}
      nodes.each { |node|
        threads << Thread.new {
          code, out = send_request_with_token(
            @auth_user, node, 'get_configs', false, data, true, nil, nil,
            @additional_known_hosts
          )
          connected_to[node] = false
          if 200 == code
            connected_to[node] = true
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

      node_connected = false
      if connected_to.empty?()
        node_connected = true # no nodes to connect to => no connection errors
      else
        connected_count = 0
        connected_to.each { |node, connected|
          if connected
            connected_count += 1
          end
        }
        # If we only connected to one node, consider it a fail and continue as
        # if we could not connect anywhere. The one node is probably the local
        # node.
        node_connected = connected_count > 1
      end

      return node_configs, node_connected
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
    return CorosyncConf
  end

  def self.get_cfg_classes()
    return [PcsdSettings, PcsdKnownHosts]
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
  def self.save_sync_new_version(
    config, nodes, cluster_name, fetch_on_conflict, known_hosts=[]
  )
    if not cluster_name or cluster_name.empty? or not nodes or nodes.empty?
      # we run on a standalone host, no config syncing
      config.version += 1
      config.save()
      return true, {}
    else
      # we run in a cluster so we need to sync the config
      publisher = ConfigPublisher.new(
        PCSAuth.getSuperuserAuth(), [config], nodes, cluster_name, known_hosts
      )
      old_configs, node_responses = publisher.publish()
      if old_configs.include?(config.class.name)
        if fetch_on_conflict
          fetcher = ConfigFetcher.new(
            PCSAuth.getSuperuserAuth(), [config.class], nodes, cluster_name
          )
          cfgs_to_save, _, _ = fetcher.fetch()
          cfgs_to_save.each { |cfg_to_save|
            cfg_to_save.save() if cfg_to_save.class == config.class
          }
        end
        return false, node_responses
      end
      return true, node_responses
    end
  end

  def self.merge_known_host_files(
    orig_cfg, to_merge_cfgs, new_hosts, remove_hosts_names
  )
    # Merge known-hosts files, use only newer known-hosts files, keep the most
    # recent known-hosts, make sure remove_hosts_names are deleted and new_hosts
    # are included
    max_version = orig_cfg.version
    with_new_hosts = CfgKnownHosts.new(orig_cfg.text)
    if to_merge_cfgs and to_merge_cfgs.length > 0
      to_merge_cfgs.reject! { |item| item.version <= orig_cfg.version }
      if to_merge_cfgs.length > 0
        to_merge_cfgs.sort.each { |merge_cfg|
          with_new_hosts.known_hosts.update(
            CfgKnownHosts.new(merge_cfg.text).known_hosts
          )
        }
        max_version = [to_merge_cfgs.max.version, max_version].max
      end
    end
    remove_hosts_names.each { |host_name|
      with_new_hosts.known_hosts.delete(host_name)
    }
    new_hosts.each { |host|
      with_new_hosts.known_hosts[host.name] = host
    }
    config_new = PcsdKnownHosts.from_text(with_new_hosts.text)
    config_new.version = max_version
    return config_new
  end

  def self.save_sync_new_known_hosts(
    new_hosts, remove_hosts_names, target_nodes, cluster_name
  )
    config_old = PcsdKnownHosts.from_file()
    config_new = Cfgsync::merge_known_host_files(
      config_old, [], new_hosts, remove_hosts_names
    )
    if not cluster_name or cluster_name.empty? or not target_nodes or target_nodes.empty?
      # we run on a standalone host, no config syncing
      config_new.version += 1
      config_new.save()
      return true, {}
    end
    # we run in a cluster so we need to sync the config
    publisher = ConfigPublisher.new(
      PCSAuth.getSuperuserAuth(), [config_new], target_nodes, cluster_name,
      new_hosts
    )
    old_configs, node_responses = publisher.publish()
    if not old_configs.include?(config_new.class.name)
      # no node had newer tokens file, we are ok, everything done
      return true, node_responses
    end
    # get tokens from all nodes and merge them
    fetcher = ConfigFetcher.new(
      PCSAuth.getSuperuserAuth(), [config_new.class], target_nodes,
      cluster_name, new_hosts
    )
    fetched_hosts, _ = fetcher.fetch_all()[config_new.class.name]
    config_new = Cfgsync::merge_known_host_files(
      config_old, fetched_hosts, new_hosts, remove_hosts_names
    )
    # and try to publish again
    return Cfgsync::save_sync_new_version(
      config_new, target_nodes, cluster_name, true, new_hosts
    )
  end
end
