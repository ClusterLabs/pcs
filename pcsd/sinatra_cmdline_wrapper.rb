require "base64"
require "date"
require "json"

orig_std_out = STDOUT.clone
request_json = ARGF.read()

begin
  request = JSON.parse(request_json)
rescue => e
  puts e
  exit
end


if !request.include?("config")
  STDOUT.reopen(orig_std_out)
  result = {:error => "config not specified"}
  print result.to_json
  exit
end

if !request["config"].include?("log_location")
  STDOUT.reopen(orig_std_out)
  result = {:error => "log location not specified"}
  print result.to_json
  exit
end

if !request.include?("type")
  STDOUT.reopen(orig_std_out)
  result = {:error => "Type not specified"}
  print result.to_json
  exit
end

$tornado_log_location = request["config"]["log_location"]

require 'pcsd'

if ["sinatra_gui", "sinatra_remote"].include?(request["type"])
  if request["type"] == "sinatra_gui"
    $tornado_username = request["session"]["username"]
    $tornado_groups = request["session"]["groups"]
    $tornado_is_authenticated = request["session"]["is_authenticated"]
  end

  set :logging, true
  set :run, false
  app = [Sinatra::Application][0]

  env = request["env"]
  env["rack.input"] = StringIO.new(env["rack.input"])

  status, headers, body = app.call(env)

  result = {
    :status => status,
    :headers => headers,
    :body => ""
  }


  full_body = ""
  body.each{|body_part|
    #For example public/css/style.css is long. The body is in 2 parts in this
    #case. An extra newlinew will appear here if "puts" is used.
    full_body += body_part
  }
  result[:body] = Base64.encode64(full_body)

elsif request["type"] == "sync_configs"
  result = {
    :next => Time.now.to_i + run_cfgsync()
  }
else
  result = {:error => "Unknown type: '#{request["type"]}'"}
end

STDOUT.reopen(orig_std_out)
print result.to_json
