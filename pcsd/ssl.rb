require 'rubygems'
require 'webrick'
require 'webrick/https'
require 'openssl'
require 'logger'
require 'rack'

def is_rhel7_compat()
  is_compatible = true

  if not IO.popen('/usr/sbin/corosync -v').read =~ /version '2.3/
    is_compatible = false
  end

  if not IO.popen('/usr/sbin/pacemakerd -$').read =~ /Pacemaker 1.1/
    is_compatible = false
  end

  return is_compatible
end

def is_systemctl()
  if File.exist?('/usr/bin/systemctl')
    return true
  else
    return false
  end
end

CRT_FILE = "/var/lib/pcsd/pcsd.crt"
KEY_FILE = "/var/lib/pcsd/pcsd.key"
server_name = WEBrick::Utils::getservername

if not File.exists?(CRT_FILE) or not File.exists?(KEY_FILE)
  name = "/C=US/ST=MN/L=Minneapolis/O=pcsd/OU=pcsd/CN=#{server_name}"
  ca   = OpenSSL::X509::Name.parse(name)
  key = OpenSSL::PKey::RSA.new(2048)
  crt = OpenSSL::X509::Certificate.new
  crt.version = 2
  crt.serial  = ((Time.now).to_f * 1000).to_i
  crt.subject = ca
  crt.issuer = ca
  crt.public_key = key.public_key
  crt.not_before = Time.now
  crt.not_after  = Time.now + 10 * 365 * 24 * 60 * 60 # 10 year
  crt.sign(key, OpenSSL::Digest::SHA256.new)

  File.open(CRT_FILE, 'w',0700) {|f| f.write(crt)}
  File.open(KEY_FILE, 'w',0700) {|f| f.write(key)}
end

webrick_options = {
  :Port               => 2224,
  :BindAddress        => "::",
  :SSLEnable          => true,
  :SSLVerifyClient    => OpenSSL::SSL::VERIFY_NONE,
  :SSLCertificate     => OpenSSL::X509::Certificate.new(File.open(CRT_FILE).read),
  :SSLPrivateKey      => OpenSSL::PKey::RSA.new(File.open(KEY_FILE).read()),
  :SSLCertName        => [[ "CN", server_name ]],
}

if is_systemctl
  webrick_options[:StartCallback] = Proc.new {
  	`python /usr/lib/pcsd/systemd-notify-fix.py`
  }
end

server = ::Rack::Handler::WEBrick
trap(:INT) do
  puts "Shutting down (INT)"
  server.shutdown
  #exit
end

trap(:TERM) do
  puts "Shutting down (TERM)"
  server.shutdown
  #exit
end

require 'pcsd'
WEBrick::Daemon.start if not is_systemctl
begin
  server.run(Sinatra::Application, webrick_options)
rescue Errno::EAFNOSUPPORT
  webrick_options[:BindAddress] = '0.0.0.0'
  server.run(Sinatra::Application, webrick_options)
end
