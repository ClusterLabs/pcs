require 'settings.rb'

module PcsdRemoveFile
  class RemoveFile
    def initialize(id, action)
      @id = id
      @action = action
    end

    def validate()
    end

    def full_file_name()
      raise NotImplementedError.new(
        "'#{__method__}' is not implemented in '#{self.class}'"
      )
    end

    def process()
      unless File.exist? self.full_file_name
        return PcsdExchangeFormat::result(:not_found)
      end
      begin
        File.delete(self.full_file_name)
        return PcsdExchangeFormat::result(:deleted)
      rescue => e
        return PcsdExchangeFormat::result(:unexpected, e.message)
      end
    end
  end

  class RemovePcmkRemoteAuthkey < RemoveFile
    def full_file_name()
      @full_file_name ||= PACEMAKER_AUTHKEY
    end
  end

  class RemovePcsdSettings < RemoveFile
    def full_file_name()
      @full_file_name ||= PCSD_SETTINGS_CONF_LOCATION
    end
  end

  class RemovePcsDrConf < RemoveFile
    def full_file_name
      @full_file_name ||= PCSD_DR_CONFIG_LOCATION
    end
  end

  TYPES = {
    "pcmk_remote_authkey" => RemovePcmkRemoteAuthkey,
    "pcsd_settings" => RemovePcsdSettings,
    "pcs_disaster_recovery_conf" => RemovePcsDrConf,
  }
end
