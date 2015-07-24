#!/usr/bin/ruby

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
session = {}
PCS = get_pcs_path(File.expand_path(File.dirname(__FILE__)))
$logger_device = StringIO.new
$logger = configure_logger($logger_device)

# check and set user
uid = Process.uid
if 0 == uid
  if ENV['CIB_user'] and ENV['CIB_user'].strip != ''
    session[:username] = ENV['CIB_user']
    if ENV['CIB_user_groups'] and ENV['CIB_user_groups'].strip != ''
      session[:usergroups] = ENV['CIB_user_groups'].split(nil)
    else
      session[:usergroups] = []
    end
  else
    session[:username] = SUPERUSER
    session[:usergroups] = []
  end
else
  username = Etc.getpwuid(uid).name
  if not PCSAuth.isUserAllowedToLogin(username)
    cli_exit('access_denied')
  else
    session[:username] = username
    success, groups = PCSAuth.getUsersGroups(username)
    session[:usergroups] = success ? groups : []
  end
end

# continue environment setup with user set in session
$cluster_name = get_cluster_name()

# get params and run a command
command = ARGV[0]
allowed_commands = {
  'read_tokens' => {
    # returns tokens of the user who runs pcsd-cli, thus no permission check
    'only_superuser' => false,
    'permissions' => nil,
    'call' => lambda { |params, session| read_tokens() },
  },
  'auth' => {
    'only_superuser' => false,
    'permissions' => nil,
    'call' => lambda { |params, session|
      auth_responses, sync_successful, sync_nodes_err, sync_responses = pcs_auth(
        session, params['nodes'] || [], params['username'] || '',
        params['password'] || '', params['force'], params['local']
      )
      return {
        'auth_responses' => auth_responses,
        'sync_successful' => sync_successful,
        'sync_nodes_err' => sync_nodes_err,
        'sync_responses' => sync_responses,
      }
    },
  },
  'send_local_configs' => {
    'only_superuser' => false,
    'permissions' => Permissions::FULL,
    'call' => lambda { |params, session|
      send_local_configs_to_nodes(
        # for a case when sending to a node which is being added to a cluster
        # - the node doesn't have the config so it cannot check permissions
        PCSAuth.getSuperuserSession(),
        params['nodes'] || [],
        params['force'] || false,
        params['clear_local_cluster_permissions'] || false
      )
    }
  },
  'send_local_certs' => {
    'only_superuser' => false,
    'permissions' => Permissions::FULL,
    'call' => lambda { |params, session|
      send_local_certs_to_nodes(session, params['nodes'] || [])
    }
  },
  'pcsd_restart_nodes' => {
    'only_superuser' => false,
    'permissions' => nil,
    'call' => lambda { |params, session|
      pcsd_restart_nodes(session, params['nodes'] || [])
    }
  },
}

if allowed_commands.key?(command)
  begin
    params = JSON.parse(STDIN.read)
  rescue JSON::ParserError => e
    cli_exit('bad_json_input', e.to_s)
  end
  if allowed_commands['only_superuser']
    if not allowed_for_superuser(session)
      cli_exit('permission_denied')
    end
  end
  if allowed_commands['permissions']
    if not allowed_for_local_cluster(session, command_settings['permissions'])
      cli_exit('permission_denied')
    end
  end
  result = allowed_commands[command]['call'].call(params, session)
  cli_exit('ok', nil, result)
else
  cli_exit('bad_command')
end

