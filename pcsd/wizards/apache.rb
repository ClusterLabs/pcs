require 'sinatra'
class ApacheWizard < PCSDWizard

  def long_name
    "HA Apache with Shared Storage"
  end

  def description
    "This wizard creates an HA Apache web server with a clustered IP address on a shared lvm volume"
  end

  def process_responses(params)
    out = ""
    errors = []
    device = params[:shared_storage_dev]
    filesystem = params[:file_system]
    vg = params[:vg_name]
    nm = params[:cidr_netmask]
    ip = params[:ip_address]
    errors << "You must enter a shared storage device" if device == ""
    errors << "You must enter a filesystem" if filesystem == ""
    errors << "You must enter a volume group" if vg == ""
    errors << "You must enter a netmask" if nm == ""
    errors << "You must enter a IP address" if ip == ""

    if errors.length != 0
      return collection_page(errors)
    end

    puts "PCS NAME"
    puts PCS
    puts run_cmd(PCS, 'resource','create','shared_dev', 'LVM', 'volgrpname='+vg)
    puts run_cmd(PCS, 'resource','create','shared_fs', 'Filesystem', 'device='+device, 'directory=/var/www/html', 'fstype="ext4"', 'options="ro"')
    puts run_cmd(PCS, 'resource','create','Apache','apache', 'configfile="/etc/httpd/conf/httpd.conf"', 'statusurl="http://127.0.0.1/server-status"')
    puts run_cmd(PCS, 'resource','create','ClusterIP','IPaddr2',"ip="+ip, "cidr_netmask="+nm)
    puts run_cmd(PCS, 'resource','group','add','ApacheGroup','shared_dev','shared_fs','ClusterIP','Apache')
    out = "Resources created..."
    return out.gsub(/\n/,"<br>")
  end

  def collection_page(errors=[])
    out = "<table>\n"
    if errors.length != 0
      errors.each {|e|
	out += '<tr><td style="color:red">'+e+'</td></tr>'+"\n"
      }
    end
    out += <<-output_string
    <tr>
      <td colspan=2>
	Configuration a HA Apache web server on top of shared storage:
      </td>
    </tr>
    <tr><td>What is the name of the shared device which contains an ext4 filesystem:</td><td><input name="shared_storage_dev" type="text"></td></tr>
    <tr><td>What is the name of your shared volume group: </td><td><input type="text" name="vg_name" value="my_vg"></td></tr>
    <tr><td>What IP address will be shared with all of the nodes: </td><td><input type="text" name="ip_address"></td></tr>
    <tr><td>What is the IP address netmask (ie. 24): </td><td><input type="text" name="cidr_netmask" value="24"></td></tr>
    <tr><td style="text-align:right" colspan=2><input type=submit></td></tr>
  </table>
    output_string

    return out
  end

end
