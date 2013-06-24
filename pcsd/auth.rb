require 'json'
require 'pp'
require 'securerandom'
require 'rpam'

class PCSAuth
  def self.validUser(username, password, generate_token = false, request = nil)
    if username != "hacluster"
      return nil
    end
    if not Rpam.auth(username,password, :service => "pcsd")
      return nil
    end

    if generate_token
      token = SecureRandom.uuid
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
	return true
      end
    }
    return false
  end

  def self.isLoggedIn(session, cookies)
    return true if validToken(cookies["token"])
    session["username"] != nil
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

    token = SecureRandom.uuid

    users.delete_if{|u| u["username"] == username}
    users << {"username" => username, "password" => password, "token" => token}
    File.open($user_pass_file, "w") do |f|
      f.write(JSON.pretty_generate(users))
    end
  end
end

