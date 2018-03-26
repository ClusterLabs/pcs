require "json"
require "base64"

orig_std_out = STDOUT.clone
request_json = ARGF.read()

begin
  request = JSON.parse(request_json)
rescue => e
  puts e
  exit
end

require 'pcsd'
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

STDOUT.reopen(orig_std_out)

result = {
  :status => status,
  :headers => headers,
  :body => ""
}

# puts result.to_json

full_body = ""
body.each{|body_part|
  #For example public/css/style.css is long. The body is in 2 parts in this
  #case. An extra newlinew will appear here if "puts" is used.
  full_body += body_part
}
result[:body] = Base64.encode64(full_body)

print result.to_json
