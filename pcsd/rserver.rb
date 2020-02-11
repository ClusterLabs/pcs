require "base64"
require "date"
require "json"
require 'rack'
require 'sinatra'
require 'thin'

require 'settings.rb'

def pack_response(response)
  return [200, {}, [response.to_json.to_str]]
end

def unpack_request(transport_env)
  return JSON.parse(Base64.strict_decode64(
    transport_env["rack.request.form_hash"]["TORNADO_REQUEST"]
  ))
end

class TornadoCommunicationMiddleware
  def initialize(app)
    @app = app
  end

  def call(transport_env)
    Thread.current[:pcsd_logger_container] = []
    begin
      request = unpack_request(transport_env)

      if ["sinatra_gui", "sinatra_remote"].include?(request["type"])
        if request["type"] == "sinatra_gui"
          session = request["session"]
          Thread.current[:tornado_username] = session["username"]
          Thread.current[:tornado_groups] = session["groups"]
          Thread.current[:tornado_is_authenticated] = session["is_authenticated"]
        end

        # Keys rack.input and rack.errors are required. We make sure they are
        # there.
        request_env = request["env"]
        request_env["rack.input"] = StringIO.new(request_env["rack.input"])
        request_env["rack.errors"] = StringIO.new()

        status, headers, body = @app.call(request_env)

        rack_errors = request_env['rack.errors'].string()
        if not rack_errors.empty?()
          $logger.error(rack_errors)
        end

        return pack_response({
          :status => status,
          :headers => headers,
          :body => Base64.encode64(body.join("")),
          :logs => Thread.current[:pcsd_logger_container],
        })
      end

      if request["type"] == "sync_configs"
        return pack_response({
          :next => Time.now.to_i + run_cfgsync(),
          :logs => Thread.current[:pcsd_logger_container],
        })
      end

      raise "Unexpected value for key 'type': '#{request['type']}'"
    rescue => e
      return pack_response({:error => "Processing request error: '#{e}'"})
    end
  end
end


use TornadoCommunicationMiddleware

require 'pcsd'

::Rack::Handler.get('thin').run(Sinatra::Application, {
  :Host => PCSD_RUBY_SOCKET,
}) do |server|
  puts server.class
  server.threaded = true
  # notify systemd we are running
  if ISSYSTEMCTL
    if ENV['NOTIFY_SOCKET']
      socket_name = ENV['NOTIFY_SOCKET'].dup
      if socket_name.start_with?('@')
        # abstract namespace socket
        socket_name[0] = "\0"
      end
      $logger.info("Notifying systemd we are running (socket #{socket_name})")
      sd_socket = Socket.new(Socket::AF_UNIX, Socket::SOCK_DGRAM)
      sd_socket.connect(Socket.pack_sockaddr_un(socket_name))
      sd_socket.send('READY=1', 0)
      sd_socket.close()
    end
  end
end
