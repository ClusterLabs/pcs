require 'rubygems'
require 'etc'
require 'json'
require 'stringio'

require 'bootstrap.rb'
require 'pcs.rb'
require 'auth.rb'

def cli_format_response(status, text=nil, data=nil)
  response = {'status' => status}
  response['text'] = text if text
  response['data'] = data if data
  response['log'] = $logger_device.string
  return JSON.generate(response)
end

def cli_exit(status, text=nil, data=nil, exitcode=0)
  output = cli_format_response(status, text, data)
  $logger.debug "pcsd-cli finished with code #{exitcode} and output #{output}"
  puts output
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
  $logger.info "'pcsd-cli #{command}' running as user: root"
  $session[:username] = 'hacluster'
  $cookies[:CIB_user] = 'hacluster'
else
  username = Etc.getpwuid(uid).name
  $logger.info "'pcsd-cli #{command}' running as user: #{username}"
  if not PCSAuth.isUserAllowedToLogin(username)
    $logger.info "pcsd-cli permission denied for user: #{username}"
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
  'write_tokens' => {
    'call' => lambda { |params| write_tokens(params) },
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



