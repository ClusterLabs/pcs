require 'base64'
require 'pcs.rb' #write_file_lock, read_file_lock
require 'settings.rb'
require 'pcsd_exchange_format.rb'
require 'cfgsync.rb' # CFG_PCSD_SETTINGS


module PcsdFile
  class PutFile
    def initialize(id, file)
      @id = id
      @file = file
    end

    def validate()
      PcsdFile::validate_file_key_with_string(@id, @file, :data)
    end

    def rewrite_existing()
      return @file[:rewrite_existing]
    end

    def full_file_name()
      raise NotImplementedError.new(
        "'#{__method__}' is not implemented in '#{self.class}'"
      )
    end

    def binary?()
      return true
    end

    def exists?()
      return @exists if defined? @exists
      @exists ||= File.file?(self.full_file_name)
    end

    def exists_with_same_content()
      unless self.exists?
        return false
      end

      if self.binary?
        return Base64.strict_encode64(self.read()) == @file[:data]
      end

      return self.read() == @file[:data]
    end

    def write()
      write_file_lock(
        self.full_file_name,
        self.permissions,
        self.binary? ? Base64.decode64(@file[:data]) : @file[:data],
        self.binary?,
        self.user,
        self.group
      )
    end

    def permissions()
      return nil
    end

    def user()
      return nil
    end

    def group()
      return nil
    end

    def read()
      return read_file_lock(self.full_file_name, self.binary?)
    end

    def process()
      self.validate()
      begin
        unless self.exists?
          self.write()
          return PcsdExchangeFormat::result(:written)
        end

        if self.rewrite_existing
          self.write()
          return PcsdExchangeFormat::result(:rewritten)
        end

        if self.exists_with_same_content()
          return PcsdExchangeFormat::result(:same_content)
        end

        return PcsdExchangeFormat::result(:conflict)
      rescue => e
        return PcsdExchangeFormat::result(:unexpected, e.message)
      end
    end
  end

  class PutFileBooth < PutFile
    def validate()
      super
      PcsdFile::validate_file_key_with_string(@id, @file, :name)
      if @file[:name].empty?
        raise PcsdExchangeFormat::Error.for_item('file', @id, "'name' is empty")
      end
      if @file[:name].include?('/')
        raise PcsdExchangeFormat::Error.for_item(
          'file', @id, "'name' cannot contain '/'"
        )
      end
    end

    def dir()
      return BOOTH_CONFIG_DIR
    end

    def full_file_name()
      @full_file_name ||= File.join(self.dir, @file[:name])
    end
  end

  class PutFileBoothAuthfile < PutFileBooth
    def permissions()
      return 0600
    end
  end

  class PutFileBoothConfig < PutFileBooth
    def binary?()
      return false
    end
  end

  class PutFilePcmkRemoteAuthkey < PutFile
    def full_file_name
      #TODO determine the file name from the system
      @full_file_name ||= PACEMAKER_AUTHKEY
    end

    def permissions()
      return 0400
    end

    def user()
      return 'hacluster'
    end

    def group()
      return 'haclient'
    end

    def write()
      pacemaker_config_dir = File.dirname(PACEMAKER_AUTHKEY)
      if not File.directory?(pacemaker_config_dir)
        Dir.mkdir(pacemaker_config_dir)
      end
      super
    end
  end

  class PutFileCorosyncAuthkey < PutFile
    def full_file_name
      @full_file_name ||= COROSYNC_AUTHKEY
    end

    def permissions()
      return 0400
    end
  end

  class PutFileCorosyncConf < PutFile
    def full_file_name
      @full_file_name ||= COROSYNC_CONF
    end

    def binary?()
      return false
    end

    def permissions()
      return 0644
    end
  end

  class PutPcsSettingsConf < PutFile
    def full_file_name
      @full_file_name ||= CFG_PCSD_SETTINGS
    end

    def binary?()
      return false
    end

    def permissions()
      return 0644
    end
  end

  class PutPcsDrConf < PutFile
    def full_file_name
      @full_file_name ||= PCSD_DR_CONFIG_LOCATION
    end

    def binary?()
      return true
    end

    def permissions()
      return 0600
    end
  end

  TYPES = {
    "booth_authfile" => PutFileBoothAuthfile,
    "booth_config" => PutFileBoothConfig,
    "pcmk_remote_authkey" => PutFilePcmkRemoteAuthkey,
    "corosync_authkey" => PutFileCorosyncAuthkey,
    "corosync_conf" => PutFileCorosyncConf,
    "pcs_settings_conf" => PutPcsSettingsConf,
    "pcs_disaster_recovery_conf" => PutPcsDrConf,
  }
end

def PcsdFile.validate_file_key_with_string(id, file_hash, key_name)
  unless file_hash.has_key?(key_name)
    raise PcsdExchangeFormat::Error.for_item(
      'file', id, "'#{key_name}' is missing"
    )
  end

  unless file_hash[key_name].is_a? String
    raise PcsdExchangeFormat::Error.for_item(
      'file',
      id,
      "'#{key_name}' is not String: '#{file_hash[key_name].class}'"
    )
  end
end
