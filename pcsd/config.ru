require "./pcsd.rb"

use Rack::SSL

#run Sinatra::Application
CERT_PATH = "."
Rack::Server.start :app => Sinatra::Application,
  :SSLEnable => true,
  :Port => 2222,
  :SSLVerifyClient    => OpenSSL::SSL::VERIFY_NONE,
  :SSLCertificate     => OpenSSL::X509::Certificate.new(  File.open(File.join(CERT_PATH, "server.crt")).read),
  :SSLPrivateKey      => OpenSSL::PKey::RSA.new(          File.open(File.join(CERT_PATH, "server.key")).read)

