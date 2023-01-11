require 'rubygems'
require 'etc'
require 'json'
require 'stringio'

require 'bootstrap.rb'
require 'pcs.rb'
require 'auth.rb'
require 'remote.rb'


PCS = get_pcs_path()
PCS_INTERNAL = get_pcs_internal_path()
$logger_device = StringIO.new
$logger = Logger.new($logger_device)
early_log($logger)

capabilities, capabilities_pcsd = get_capabilities($logger)
CAPABILITIES = capabilities.freeze
CAPABILITIES_PCSD = capabilities_pcsd.freeze


def cli_format_response(status, text=nil, data=nil)
  response = Hash.new
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


def pcsd_cli_main()
  # bootstrap, emulate environment created by pcsd http server
  auth_user = {}

  # check and set user
  uid = Process.uid
  if 0 == uid
    if ENV['CIB_user'] and ENV['CIB_user'].strip != ''
      auth_user[:username] = ENV['CIB_user']
      if ENV['CIB_user_groups'] and ENV['CIB_user_groups'].strip != ''
        auth_user[:usergroups] = ENV['CIB_user_groups'].split(nil)
      else
        auth_user[:usergroups] = []
      end
    else
      auth_user[:username] = SUPERUSER
      auth_user[:usergroups] = []
    end
  else
    username = Etc.getpwuid(uid).name
    if not PCSAuth.isUserAllowedToLogin(username)
      cli_exit('access_denied')
    else
      auth_user[:username] = username
      success, groups = PCSAuth.getUsersGroups(username)
      auth_user[:usergroups] = success ? groups : []
    end
  end

  # continue environment setup with user set in auth_user
  $cluster_name = get_cluster_name()

  # get params and run a command
  command = ARGV[0]
  allowed_commands = {
    'remove_known_hosts' => {
      # changes hosts of the user who runs pcsd-cli, thus no permission check
      'only_superuser' => false,
      'call' => lambda { |params, auth_user_|
        sync_successful, sync_nodes_err, sync_responses, hosts_not_found = pcs_deauth(
          auth_user_, params.fetch('host_names')
        )
        return {
          'hosts_not_found' => hosts_not_found,
          'sync_successful' => sync_successful,
          'sync_nodes_err' => sync_nodes_err,
          'sync_responses' => sync_responses,
        }
      },
    },
    'auth' => {
      'only_superuser' => false,
      'call' => lambda { |params, auth_user_|
        auth_responses, sync_successful, sync_nodes_err, sync_responses = pcs_auth(
          auth_user_, params.fetch('nodes')
        )
        return {
          'auth_responses' => auth_responses,
          'sync_successful' => sync_successful,
          'sync_nodes_err' => sync_nodes_err,
          'sync_responses' => sync_responses,
        }
      },
    },
    'auth_with_token' => {
      'only_superuser' => false,
      'call' => lambda { |params, auth_user_|
        pcs_auth_token(params.fetch('nodes'))
        return {}
      },
    },
    'send_local_configs' => {
      'only_superuser' => false,
      'call' => lambda { |params, auth_user_|
        send_local_configs_to_nodes(
          # for a case when sending to a node which is being added to a cluster
          # - the node doesn't have the config so it cannot check permissions
          PCSAuth.getSuperuserAuth(),
          params['nodes'] || [],
          params['force'] || false,
          params['clear_local_cluster_permissions'] || false
        )
      }
    },
    'node_status' => {
      'only_superuser' => true,
      'call' => lambda { |params, auth_user_|
        return JSON.parse(node_status(
          {
            :version => '2',
            :operations => '1',
            :skip_auth_check => '1',
          },
          {},
          auth_user_
        ))
      }
    },
  }
  if allowed_commands.key?(command)
    begin
      params = JSON.parse(STDIN.read)
    rescue JSON::ParserError => e
      cli_exit('bad_json_input', e.to_s)
    end
    cmd = allowed_commands[command]
    if cmd['only_superuser']
      if not allowed_for_superuser(auth_user)
        cli_exit('permission_denied')
      end
    end
    result = cmd['call'].call(params, auth_user)
    cli_exit('ok', nil, result)
  else
    cli_exit('bad_command')
  end
end
