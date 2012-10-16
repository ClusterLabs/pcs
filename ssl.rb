require 'webrick'
require 'webrick/https'
require 'openssl'
require 'logger'
require 'rack'

CRT_FILE = "/var/lib/pcsd/pcsd.crt"
KEY_FILE = "/var/lib/pcsd/pcsd.key"
server_name = WEBrick::Utils::getservername
name = "/C=US/ST=MN/L=Minneapolis/O=pcsd/OU=pcsd/CN=#{server_name}"
ca   = OpenSSL::X509::Name.parse(name)
key = OpenSSL::PKey::RSA.new(1024)
crt = OpenSSL::X509::Certificate.new
crt.version = 2
crt.serial  = 4
crt.subject = ca
crt.issuer = ca
crt.public_key = key.public_key
crt.not_before = Time.now
crt.not_after  = Time.now + 10 * 365 * 24 * 60 * 60 # 10 year

if not File.exists?(CRT_FILE) or not File.exists?(KEY_FILE)
  File.open(CRT_FILE, 'w') {|f| f.write(crt)}
  File.open(KEY_FILE, 'w') {|f| f.write(key)}
end

webrick_options = {
  :Port               => 2224,
  :SSLEnable          => true,
  :SSLVerifyClient    => OpenSSL::SSL::VERIFY_NONE,
  :SSLCertificate     => OpenSSL::X509::Certificate.new(File.open(CRT_FILE).read),
  :SSLPrivateKey      => OpenSSL::PKey::RSA.new(File.open(KEY_FILE).read()),
  :SSLCertName        => [[ "CN", server_name ]],
}

server = ::Rack::Handler::WEBrick
trap(:INT) do
  server.shutdown
end

require './pcsd'
server.run(Sinatra::Application , webrick_options) 
