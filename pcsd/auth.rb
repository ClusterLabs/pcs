require 'base64'


class PCSAuth
  def self.getUsersGroups(username)
    stdout, stderr, retval = run_cmd(
      getSuperuserAuth(), "id", "-Gn", username
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

  def self.getSuperuserAuth()
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
end
