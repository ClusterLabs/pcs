require "base64"
require "date"
require "json"
require 'rack'
require 'sinatra'
require 'thin'

require 'settings.rb'

def tm
  t1 = Time.now
  " #{t1.min}:#{t1.sec}.#{t1.usec}"
end

class TornadoCommunicationMiddleware
  def initialize(app)
    @app = app
  end

  def call(env)
    tornado_logs = []
    Thread.current[:pcsd_logger_container] = tornado_logs
    id = (0...4).map { (65 + rand(26)).chr }.join
    # raw_data = request.env["rack.input"].read
    # puts raw_data
    tornado_request = Base64.strict_decode64(env["rack.request.form_hash"]["TORNADO_REQUEST"]);
    #TODO begin - rescue for JSON.parse
    #TODO check if requests includes key "type" - see sinatra_cmdline_wrapper.rb
    #TODO sinatra "use" settings - see sinatra_cmdline_wrapper.rb
    # puts tornado_request
    request = JSON.parse(tornado_request)
    if ["sinatra_gui", "sinatra_remote"].include?(request["type"])
      if request["type"] == "sinatra_gui"
        Thread.current[:tornado_username] = request["session"]["username"]
        Thread.current[:tornado_groups] = request["session"]["groups"]
        Thread.current[:tornado_is_authenticated] = request["session"]["is_authenticated"]
      end

      # set :logging, true
      # set :run, false
      # Do not turn exceptions into fancy 100kB HTML pages and print them on stdout.
      # Instead, rack.errors is logged and therefore returned in result[:log].
      # set :show_exceptions, false

      env = request["env"]
      env["rack.input"] = StringIO.new(env["rack.input"])
      env["rack.errors"] = StringIO.new()

      puts id + tm() +" "+request["env"]["PATH_INFO"]
      status, headers, body = @app.call(env)
      rack_errors = env['rack.errors'].string()
      if not rack_errors.empty?()
        $logger.error(rack_errors)
      end

      puts id + tm() +" "+status.to_s
      # puts id+" "+body.join("")
      # tornado_logs.each{|log|
      #   puts id+" "+log[:level]+" "+log[:message].to_s
      # }
      # puts "=================================================================="
      result = {
        :status => status,
        :headers => headers,
        :body => Base64.encode64(body.join("")),
      }

    elsif request["type"] == "sync_configs"
      result = {
        :next => Time.now.to_i + run_cfgsync()
      }
    else
      result = {:error => "Unknown type: '#{request["type"]}'"}
    end

    result[:logs] = tornado_logs

    [200, {}, [result.to_json.to_str]]
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
