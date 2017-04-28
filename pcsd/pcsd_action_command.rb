require 'pcsd_exchange_format.rb'
require 'settings.rb'
require 'pcs.rb' #(enable|disable|start|stop)_service, 

module PcsdActionCommand
  class ActionType
    def initialize(id, action)
      @id = id
      @action = action
    end

    def validate()
    end

    def process()
    end

  end

  class ServiceCommand < ActionType
    @@services = {
      "pacemaker_remote" => [
        "enable",
        "disable",
        "start",
        "stop",
      ]
    }

    def error(message)
      return PcsdExchangeFormat::Error.for_item("action", @id, message)
    end

    def validate()
      unless @action.has_key?(:service)
        raise self.error("'service' is missing")
      end

      unless @action.has_key?(:command)
        raise self.error("'command' is missing")
      end

      unless @@services.key?(@action[:service])
        raise self.error(
          "unsupported 'service' ('#{@action[:service]}')"+
          " supported are #{@@services.keys}"
        )
      end

      unless @@services[@action[:service]].include?(@action[:command])
        raise self.error(
          "unsupported 'command' ('#{@action[:command]}') for service "+
          "'#{@action[:service]}',"+
          " supported are #{@@services[@action[:service]]}"
        )
      end
    end

    def run_service_command()
      #validate here required or else there could be entered a disallowed
      #@action[:service]
      self.validate()

      case @action[:command] 
      when "enable"
        return enable_service(@action[:service])
      when "disable"
        return disable_service(@action[:service])
      when "start"
        return start_service(@action[:service])
      when "stop"
        return stop_service(@action[:service])
      else
        #a mistake in @@services?
        raise self.error(
          "unsupported 'command' ('#{@action[:command]}') for service "+
          "'#{@action[:service]}'"
        )
      end
    end

    def process()
      return PcsdExchangeFormat::result(
        self.run_service_command() ? :success : :fail
      )
    end
  end

  class RemovePcmkRemoteAuthkey < ActionType
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
    "service_command" => ServiceCommand,
    "remove_pcmk_remote_authkey" => RemovePcmkRemoteAuthkey,
  }
end
