require 'json'
require 'pp'
require 'securerandom'
require 'rpam'

class PCSAuth
  # Ruby 1.8.7 doesn't implement SecureRandom.uuid
  def self.uuid
    if defined? SecureRandom.uuid
      return SecureRandom.uuid
    else
      ary = SecureRandom.random_bytes(16).unpack("NnnnnN")
      ary[2] = (ary[2] & 0x0fff) | 0x4000
      ary[3] = (ary[3] & 0x3fff) | 0x8000
      return "%08x-%04x-%04x-%04x-%04x%08x" % ary
    end
  end

  def self.validUser(username, password, generate_token = false, request = nil)
    $logger.info("Attempting login by '#{username}'")
    if not Rpam.auth(username,password, :service => "pcsd")
      $logger.info("Failed login by '#{username}' (bad username or password)")
      return nil
    end

    stdout, stderr, retval = run_cmd("id", "-Gn", username)
    if retval != 0
      $logger.info("Failed login by '#{username}' (unable to determine groups user is a member of)")
      return nil
    end

    if not stdout[0].match(/\bhaclient\b/)
      $logger.info("Failed login by '#{username}' (user is not a member of haclient)")
      return nil
    end

    $logger.info("Successful login by '#{username}'")

    if generate_token
      token = PCSAuth.uuid
      begin
      	password_file = File.open($user_pass_file, File::RDWR|File::CREAT)
	password_file.flock(File::LOCK_EX)
	json = password_file.read()
	users = JSON.parse(json)
      rescue Exception => ex
	$logger.info "Empty pcs_users.conf file, creating new file"
	users = []
      end
      users << {"username" => username, "token" => token, "client" => request.ip, "creation_date" => Time.now}
      password_file.truncate(0)
      password_file.rewind
      password_file.write(JSON.pretty_generate(users))
      password_file.close()
      return token
    end
    return true
  end

  def self.validToken(token)
    begin
      json = File.read($user_pass_file)
      users = JSON.parse(json)
    rescue
      users = []
    end

    users.each {|u|
      if u["token"] == token
	return u["username"]
      end
    }
    return false
  end

  def self.isLoggedIn(session, cookies)
    if username = validToken(cookies["token"])
      if username == "hacluster" and $cookies.key?(:CIB_user) and $cookies.key?(:CIB_user) != ""
        $session[:username] = $cookies[:CIB_user]
      end
      return true
    else
      return session[:username] != nil
    end
  end

  # Always an admin until we implement groups
  def self.isAdmin(session)
    true
  end

  def self.createUser(username, password)
    begin
      json = File.read($user_pass_file)
      users = JSON.parse(json)
    rescue
      users = []
    end

    token = PCSAuth.uuid

    users.delete_if{|u| u["username"] == username}
    users << {"username" => username, "password" => password, "token" => token}
    File.open($user_pass_file, "w") do |f|
      f.write(JSON.pretty_generate(users))
    end
  end
end

