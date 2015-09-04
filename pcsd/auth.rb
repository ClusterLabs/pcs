require 'json'
require 'securerandom'
require 'rpam'
require 'base64'

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

  def self.validUser(username, password, generate_token = false)
    $logger.info("Attempting login by '#{username}'")
    if not Rpam.auth(username, password, :service => "pcsd")
      $logger.info("Failed login by '#{username}' (bad username or password)")
      return nil
    end
    return nil if not isUserAllowedToLogin(username)

    if generate_token
      token = PCSAuth.uuid
      begin
        password_file = File.open($user_pass_file, File::RDWR|File::CREAT)
        password_file.flock(File::LOCK_EX)
        json = password_file.read()
        users = JSON.parse(json)
      rescue Exception
        $logger.info "Empty pcs_users.conf file, creating new file"
        users = []
      end
      users << {"username" => username, "token" => token, "creation_date" => Time.now}
      password_file.truncate(0)
      password_file.rewind
      password_file.write(JSON.pretty_generate(users))
      password_file.close()
      return token
    end
    return true
  end

  def self.getUsersGroups(username)
    stdout, stderr, retval = run_cmd(
      getSuperuserSession, "id", "-Gn", username
    )
    if retval != 0
      $logger.info(
        "Unable to determine groups of user '#{username}': #{stderr.join(' ').strip}"
      )
      return [false, []]
    end
    return [true, stdout.join(' ').split(nil)]
  end

  def self.isUserAllowedToLogin(username, log_success=true)
    success, groups = getUsersGroups(username)
    if not success
      $logger.info(
        "Failed login by '#{username}' (unable to determine user's groups)"
      )
      return false
    end
    if not groups.include?(ADMIN_GROUP)
      $logger.info(
        "Failed login by '#{username}' (user is not a member of #{ADMIN_GROUP})"
      )
      return false
    end
    if log_success
      $logger.info("Successful login by '#{username}'")
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

  def self.loginByToken(session, cookies)
    if username = validToken(cookies["token"])
      if SUPERUSER == username
        if cookies['CIB_user'] and cookies['CIB_user'].strip != ''
          session[:username] = cookies['CIB_user']
          if cookies['CIB_user_groups'] and cookies['CIB_user_groups'].strip != ''
            session[:usergroups] = cookieUserDecode(
              cookies['CIB_user_groups']
            ).split(nil)
          else
            session[:usergroups] = []
          end
        else
          session[:username] = SUPERUSER
          session[:usergroups] = []
        end
        return true
      else
        session[:username] = username
        success, groups = getUsersGroups(username)
        session[:usergroups] = success ? groups : []
        return true
      end
    end
    return false
  end

  def self.loginByPassword(session, username, password)
    if validUser(username, password)
      session[:username] = username
      success, groups = getUsersGroups(username)
      session[:usergroups] = success ? groups : []
      return true
    end
    return false
  end

  def self.isLoggedIn(session)
    username = session[:username]
    if (username != nil) and isUserAllowedToLogin(username, false)
      success, groups = getUsersGroups(username)
      session[:usergroups] = success ? groups : []
      return true
    end
    return false
  end

  def self.getSuperuserSession()
    return {
      :username => SUPERUSER,
      :usergroups => [],
    }
  end

  # Let's be safe about characters in cookie variables and do base64.
  # We cannot do it for CIB_user however to be backward compatible
  # so we at least remove disallowed characters.
  def self.cookieUserSafe(text)
    return text.gsub(/[^!-~]/, '').gsub(';', '')
  end

  def self.cookieUserEncode(text)
    return Base64.encode64(text).gsub("\n", '')
  end

  def self.cookieUserDecode(text)
    return Base64.decode64(text)
  end
end

