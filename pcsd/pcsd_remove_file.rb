require 'settings.rb'

module PcsdRemoveFile
  class RemovePcmkRemoteAuthkey
    def initialize(id, action)
      @id = id
      @action = action
    end

    def validate()
    end

    def process()
      authkey_file = File.join(PACEMAKER_CONFIG_DIR, "authkey")
      unless File.exists? authkey_file
        return PcsdExchangeFormat::result(:not_found)
      end
      begin
        File.delete(authkey_file)
        return PcsdExchangeFormat::result(:deleted)
      rescue => e
        return PcsdExchangeFormat::result(:unexpected, e.message)
      end
    end
  end

  TYPES = {
    "pcmk_remote_authkey" => RemovePcmkRemoteAuthkey,
  }
end
