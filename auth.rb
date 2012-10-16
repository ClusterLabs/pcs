require 'json'
require 'pp'
require 'securerandom'
require 'rpam'

class PCSAuth
  def self.validUser(username, password, generate_token = false, request = nil)
    if username != "hacluster"
      return nil
    end
    if not Rpam.auth(username,password)
      return nil
    end

    if generate_token
      token = SecureRandom.uuid
      begin
	json = File.read($user_pass_file)
	users = JSON.parse(json)
      rescue
	users = []
      end
      users << {"username" => username, "token" => token, "client" => request.ip, "creation_date" => Time.now}
      File.open($user_pass_file, "w") do |f|
	f.write(JSON.pretty_generate(users))
      end
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

