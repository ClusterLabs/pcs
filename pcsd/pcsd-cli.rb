require 'rubygems'
require 'etc'
require 'json'
require 'stringio'
require 'orderedhash'

require 'bootstrap.rb'
require 'pcs.rb'
require 'auth.rb'

def cli_format_response(status, text=nil, data=nil)
  response = OrderedHash.new
  response['status'] = status
  response['text'] = text if text
  response['data'] = data if data
  response['log'] = $logger_device.string.lines.to_a
  return JSON.pretty_generate(response)
end

def cli_exit(status, text=nil, data=nil, exitcode=0)
  puts cli_format_response(status, text, data)
  exit exitcode
end


# bootstrap, emulate environment created by pcsd http server
$session = {}
$cookies = {}
PCS = get_pcs_path(File.expand_path(File.dirname(__FILE__)))
$logger_device = StringIO.new
$logger = configure_logger($logger_device)
$cluster_name = get_cluster_name()

command = ARGV[0]

# check and set user
uid = Process.uid
if 0 == uid
  $session[:username] = 'hacluster'
  $cookies[:CIB_user] = 'hacluster'
else
  username = Etc.getpwuid(uid).name
  if not PCSAuth.isUserAllowedToLogin(username)
    cli_exit('access_denied')
  else
    $session[:username] = username
    $cookies[:CIB_user] = username
  end
end

# get params and run a command
allowed_commands = {
  'read_tokens' => {
    'call' => lambda { |params| read_tokens() },
  },
  'auth' => {
    'call' => lambda { |params|
      pcs_auth(
        params['nodes'] || [], params['username'] || '', params['password'] || '',
        params['force'], params['local'],
      )
    },
  },
}

if allowed_commands.key?(command)
  begin
    params = JSON.parse(STDIN.read)
  rescue JSON::ParserError => e
    cli_exit('bad_json_input', e.to_s)
  end
  result = allowed_commands[command]['call'].call(params)
  cli_exit('ok', nil, result)
else
  cli_exit('bad_command')
end

