require 'json'
require 'pp'
require 'securerandom'

class PCSAuth
  def self.validUser(username, password)
    begin
      json = File.read($user_pass_file)
      users = JSON.parse(json)
    rescue
      users = []
    end

    users.each {|u|
      if u["username"] == username
	if u["password"] == password
	  return u["token"]
	end
      end
    }
    return nil
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

