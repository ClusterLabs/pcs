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

require 'pcsd'

if !request.include?("config") or !request["config"].include?("type")
  result = {:error => "Unknown type: '#{request["config"]["type"]}'"}
elsif request["config"]["type"] == "sinatra_request"
  $user_pass_file = request["config"]["user_pass_dir"] + $user_pass_file
  $tornado_username = request["config"]["username"]
  $tornado_groups = request["config"]["groups"]
  $tornado_is_authenticated = request["config"]["is_authenticated"]

  set :logging, true
  set :run, false
  app = [Sinatra::Application][0]

  env = request["env"]
  env["rack.input"] = StringIO.new("")

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

elsif request["config"]["type"] == "sync_configs"
  result = {
    :next => Time.now.to_i + run_cfgsync()
  }
else
  result = {:error => "Unknown type: '#{request["config"]["type"]}'"}
end

STDOUT.reopen(orig_std_out)
print result.to_json
