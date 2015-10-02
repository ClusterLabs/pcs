require 'rubygems'
require 'webrick'
require 'webrick/https'
require 'openssl'
require 'rack'

require 'bootstrap.rb'
require 'pcs.rb'

server_name = WEBrick::Utils::getservername
$logger = configure_logger('/var/log/pcsd/pcsd.log')

def generate_cert_key_pair(server_name)
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
  return crt, key
end

if not File.exists?(CRT_FILE) or not File.exists?(KEY_FILE)
  crt, key = generate_cert_key_pair(server_name)
  File.open(CRT_FILE, 'w',0700) {|f| f.write(crt)}
  File.open(KEY_FILE, 'w',0700) {|f| f.write(key)}
else
  crt, key = nil, nil
  begin
    crt = File.read(CRT_FILE)
    key = File.read(KEY_FILE)
  rescue => e
    $logger.error "Unable to read certificate or key: #{e}"
  end
  crt_errors = verify_cert_key_pair(crt, key)
  if crt_errors and not crt_errors.empty?
    crt_errors.each { |err| $logger.error err }
    $logger.error "Invalid certificate and/or key, using temporary ones"
    crt, key = generate_cert_key_pair(server_name)
  end
end

webrick_options = {
  :Port               => 2224,
  :BindAddress        => '::',
  :Host               => '::',
  :SSLEnable          => true,
  :SSLVerifyClient    => OpenSSL::SSL::VERIFY_NONE,
  :SSLCertificate     => OpenSSL::X509::Certificate.new(crt),
  :SSLPrivateKey      => OpenSSL::PKey::RSA.new(key),
  :SSLCertName        => [[ "CN", server_name ]],
  :SSLOptions         => OpenSSL::SSL::OP_NO_SSLv2 | OpenSSL::SSL::OP_NO_SSLv3,
}

server = ::Rack::Handler::WEBrick
trap(:INT) do
  puts "Shutting down (INT)"
  if server.instance_variable_get("@server")
    server.shutdown
  else
    exit
  end
end

trap(:TERM) do
  puts "Shutting down (TERM)"
  if server.instance_variable_get("@server")
    server.shutdown
  else
    exit
  end
end

require 'pcsd'
begin
  server.run(Sinatra::Application, webrick_options)
rescue Errno::EAFNOSUPPORT
  webrick_options[:BindAddress] = '0.0.0.0'
  webrick_options[:Host] = '0.0.0.0'
  server.run(Sinatra::Application, webrick_options)
end
