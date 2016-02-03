require 'test/unit'

require 'pcsd_test_utils.rb'
require 'auth.rb'

class TestAuth < Test::Unit::TestCase

  class ::PCSAuth
    def self.getUsersGroups(username)
      groups = {
        'user1' => ['group1', 'haclient'],
        'user2' => ['group2'],
      }
      if groups.key?(username)
        return true, groups[username]
      else
        return false, []
      end
    end
  end

  def setup
    $user_pass_file = CFG_PCSD_USERS
    $logger = MockLogger.new
  end

  def testLoginByToken
    users = []
    users << {"username" => "user1", "token" => "token1"}
    users << {"username" => "user2", "token" => "token2"}
    users << {"username" => SUPERUSER, "token" => "tokenS"}
    password_file = File.open($user_pass_file, File::RDWR|File::CREAT)
    password_file.truncate(0)
    password_file.rewind
    password_file.write(JSON.pretty_generate(users))
    password_file.close()

    cookies = {}
    result = PCSAuth.loginByToken(cookies)
    assert_equal(nil, result)

    cookies = {'token' => 'tokenX'}
    result = PCSAuth.loginByToken(cookies)
    assert_equal(nil, result)

    cookies = {'token' => 'token1'}
    result = PCSAuth.loginByToken(cookies)
    assert_equal(
      {:username => 'user1', :usergroups => ['group1', 'haclient']},
      result
    )

    cookies = {
      'token' => 'token1',
      'CIB_user' => 'userX',
      'CIB_user_groups' => PCSAuth.cookieUserEncode('groupX')
    }
    result = PCSAuth.loginByToken(cookies)
    assert_equal(
      {:username => 'user1', :usergroups => ['group1', 'haclient']},
      result
    )

    cookies = {'token' => 'tokenS'}
    result = PCSAuth.loginByToken(cookies)
    assert_equal(
      {:username => SUPERUSER, :usergroups => []},
      result
    )

    cookies = {
      'token' => 'tokenS',
      'CIB_user' => 'userX',
      'CIB_user_groups' => PCSAuth.cookieUserEncode('groupX')
    }
    result = PCSAuth.loginByToken(cookies)
    assert_equal(
      {:username => 'userX', :usergroups => ['groupX']},
      result
    )
  end

end
