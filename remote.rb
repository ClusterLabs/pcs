require 'json'
require 'net/http'
require 'uri'

# Commands for remote access
def remote(params)
  case (params[:command])
  when "status"
    if params[:node] != nil and params[:node] != "" and params[:node] != @@cur_node_name
      begin
	uri = URI.parse("http://#{params[:node]}:2222/remote/status?hello=1")
	output = Net::HTTP::get_response(uri)
	return output.body
      rescue
	return '[{"noresponse":true}]'
      end
    end
    uptime = `uptime`.chomp
    corosync_status = system("/etc/init.d/corosync", "status")
    pacemaker_status = system("/etc/init.d/pacemaker", "status")
    status = ["uptime" => uptime, "corosync" => corosync_status, "pacemaker" => pacemaker_status]
    ret = JSON.generate(status)
    return ret
  when "set_corosync_conf"
    puts "#{params['corosync_conf']}"
  when "start_daemons"
    puts "Starting Daemons"
    puts `/etc/init.d/corosync start`
    puts `/etc/init.d/pacemaker start`
  end
end
