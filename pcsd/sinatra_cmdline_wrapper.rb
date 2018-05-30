require "base64"
require "date"
require "json"

request_json = ARGF.read()

begin
  request = JSON.parse(request_json)
rescue => e
  puts e
  exit
end

if !request.include?("type")
  result = {:error => "Type not specified"}
  print result.to_json
  exit
end

$tornado_logs = []

require 'pcsd'

if ["sinatra_gui", "sinatra_remote"].include?(request["type"])
  if request["type"] == "sinatra_gui"
    $tornado_username = request["session"]["username"]
    $tornado_groups = request["session"]["groups"]
    $tornado_is_authenticated = request["session"]["is_authenticated"]
  end

  set :logging, true
  set :run, false
  # Do not turn exceptions into fancy 100kB HTML pages and print them on stdout.
  # Instead, rack.errors is logged and therefore returned in result[:log].
  set :show_exceptions, false
  app = [Sinatra::Application][0]

  env = request["env"]
  env["rack.input"] = StringIO.new(env["rack.input"])
  env["rack.errors"] = StringIO.new()

  status, headers, body = app.call(env)
  rack_errors = env['rack.errors'].string()
  if not rack_errors.empty?()
    $logger.error(rack_errors)
  end

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

result[:logs] = $tornado_logs
print result.to_json
