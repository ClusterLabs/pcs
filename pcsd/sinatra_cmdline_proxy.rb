require "json"
require "base64"

orig_std_out = STDOUT.clone
request_json = ARGF.read()



# request_json = '{"config": {"user_pass_dir": "/root/pcs/pcsd/"}, "env": {"PATH_INFO": "/manage", "QUERY_STRING": "tornado.session.username=hacluster", "REMOTE_ADDR": "192.168.122.51", "REMOTE_HOST": "abe:3224", "REQUEST_METHOD": "GET", "REQUEST_URI": "https://abe:3224/manage", "SCRIPT_NAME": "", "SERVER_NAME": "abe", "SERVER_PORT": 3224, "SERVER_PROTOCOL": "HTTP/1.1", "HTTP_HOST": "abe:3224", "HTTP_ACCEPT": "*/*", "HTTP_COOKIE": "rack.session=7okzyqaa5vgpgvcip11pyvke8pfs6qoyiptrhorz2nke1e4bmmrdh24yxjxlucs6", "HTTPS": "on", "SSL_CLIENT_CERT": "", "SSL_CIPHER": "DHE-RSA-AES256-GCM-SHA384", "SSL_PROTOCOL": "TLSv1/SSLv3", "SSL_CIPHER_USEKEYSIZE": "256", "SSL_CIPHER_ALGKEYSIZE": "256", "HTTP_VERSION": "HTTP/1.1", "REQUEST_PATH": "/manage"}}'

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
