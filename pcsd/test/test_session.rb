require 'test/unit'

require 'pcsd_test_utils.rb'
require 'session.rb'
require 'sinatra'

class TestSessionPool < Test::Unit::TestCase

  def setup()
    @request = Sinatra::Request.new({
      'rack.multithread' => true,
    })
  end

  def fixture_get_pool(lifetime)
    pool = SessionPoolLifetime.new(nil, {:expire_after => lifetime,})
    (1..3).each { |i| pool.write_session(@request, "sid#{i}", {'value' => i}, {}) }
    return pool
  end

  def test_drop_expired_on_get()
    lifetime = 2
    pool = fixture_get_pool(lifetime)
    # touch sessions each second
    lifetime.times {
      sleep(1)
      assert_equal({'value' => 1}, pool.find_session(@request, 'sid1')[1])
      assert_equal({'value' => 3}, pool.find_session(@request, 'sid3')[1])
    }
    # after @lifetime passes the unused session gets removed on access
    sleep(1)
    assert_equal({'value' => 1}, pool.find_session(@request, 'sid1')[1])
    assert_equal({'value' => 3}, pool.find_session(@request, 'sid3')[1])
    assert_equal({}, pool.find_session(@request, 'sid2')[1])
  end

  def test_drop_expired_explicit()
    lifetime = 2
    pool = fixture_get_pool(lifetime)
    # touch sessions each second (otherwise they will be removed on access)
    lifetime.times {
      sleep(1)
      pool.find_session(@request, 'sid2')
      pool.write_session(@request, 'sid3', {'value' => 33}, {})
    }
    sleep(1)

    pool.drop_expired(@request)
    assert_equal(
      {
        'sid2' => {'value' => 2,},
        'sid3' => {'value' => 33,},
      },
      pool.pool
    )
  end

  def test_no_lifetime()
    pool = fixture_get_pool(nil)
    sleep(1)
    assert_equal({'value' => 1}, pool.find_session(@request, 'sid1')[1])
    assert_equal({'value' => 2}, pool.find_session(@request, 'sid2')[1])
    assert_equal({'value' => 3}, pool.find_session(@request, 'sid3')[1])
    sleep(1)
    pool.drop_expired(@request)
    assert_equal({'value' => 1}, pool.find_session(@request, 'sid1')[1])
    assert_equal({'value' => 2}, pool.find_session(@request, 'sid2')[1])
    assert_equal({'value' => 3}, pool.find_session(@request, 'sid3')[1])
  end

end

