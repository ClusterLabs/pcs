class Cluster 
  attr_accessor :id, :name, :nodes, :num_nodes
  def initialize(name, nodes)
    @name = name
    @nodes = nodes
    @num_nodes = nodes.length
  end

  def ui_address
    return "/managec/" + @name + "/main"
  end
end

def wizard(params, request, wizard)
  wizard = "" if not wizard

  if request.request_method == "POST"
    device = "/dev/" + params[:vg_name] + "/" + params[:lv_name]
#    command(['pvcreate',params[:shared_storage_dev]])
#    command(['vgcreate',params[:vg_name], params[:shared_storage_dev]])
#    command(['lvcreate','-L750', '-n', params[:lv_name], params[:vg_name]])
#    command(['mkfs.ext4',"/dev/" + params[:vg_name] + "/" + params[:lv_name]])

    command(['pcs','resource','create','shared_dev', 'LVM', 'volgrpname='+params[:vg_name]])
    command(['pcs','resource','create','shared_fs', 'Filesystem', 'device='+device, 'directory=/var/www/html', 'fstype="ext4"', 'options="ro"'])
    command(['pcs','resource','create','apache', 'configfile="/etc/httpd/conf/httpd.conf"', 'statusurl="http://127.0.0.1/server-status"'])
    command(['pcs','resource','create','ClusterIP','IPaddr2',"ip="+params["ip_address"], "cidr_netmask="+params[:cidr_netmask]])
    command(['pcs','resource group add ApacheGroup shared_dev shared_fs ClusterIP apache'])

  end
  erb :"wizards/apache", :layout => :main

#
#  return [200, "HI: "+ wizard]
end

def command(args)
  puts args.join(" ")
end
