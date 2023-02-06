require "base64"
require "date"
require "json"
require 'rack'
require 'sinatra'

require 'settings.rb'


def pack_response(response)
  return [200, {}, [response.to_json.to_str]]
end

class TornadoCommunicationMiddleware
  def initialize(app)
    @app = app
  end

  def call(env)
    Thread.current[:pcsd_logger_container] = []
    begin
      type = env["HTTP_X_PCSD_TYPE"]

      if "sinatra" == type
        session = JSON.parse(Base64.strict_decode64(env["HTTP_X_PCSD_PAYLOAD"]))
        Thread.current[:tornado_username] = session["username"]
        Thread.current[:tornado_groups] = session["groups"]

        status, headers, body = @app.call(env)

        return pack_response({
          :status => status,
          :headers => headers,
          :body => Base64.encode64(body.join("")),
          :logs => Thread.current[:pcsd_logger_container],
        })
      end

      if type == "sync_configs"
        return pack_response({
          :next => Time.now.to_i + run_cfgsync(),
          :logs => Thread.current[:pcsd_logger_container],
        })
      end

      return pack_response({
        :error => "Unexpected value for key 'type': '#{type}'"
      })
    rescue => e
      return pack_response({
        :error => "Processing request error: '#{e}' '#{e.backtrace}'"
      })
    end
  end
end


use TornadoCommunicationMiddleware

require 'pcsd'

::Rack::Handler.get('puma').run(
  Sinatra::Application, :Host => "#{PCSD_RUBY_SOCKET}?umask=0o077", :timeout => 0
) do |server|
  puts server.class
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
