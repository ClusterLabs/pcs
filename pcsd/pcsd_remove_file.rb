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
      unless File.exists? PACEMAKER_AUTHKEY
        return PcsdExchangeFormat::result(:not_found)
      end
      begin
        File.delete(PACEMAKER_AUTHKEY)
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
