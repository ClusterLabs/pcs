gem 'rack', '< 2.0.0'
require 'rack/session/pool'

class SessionPoolLifetime < Rack::Session::Pool

  def initialize(app, options={})
    super
    @pool_timestamp = Hash.new()
  end

  def call(env)
    # save session storage to env so we can get it later
    env[:__session_storage] = self
    super
  end

  def get_session(env, sid)
    with_lock(env) do
      now = Time.now()
      # delete the session if expired
      if @default_options[:expire_after] and sid and
        get_timestamp_with_fallback(sid) and
        get_timestamp_with_fallback(sid) < (now - @default_options[:expire_after])
      then
        delete_session(sid.private_id)
        delete_session(sid.public_id)
      end
      # create new session if nonexistent
      unless sid and session = get_session_with_fallback(sid)
        sid, session = generate_sid, {}
        @pool.store sid.private_id, session
      end
      # bump session's access time
      @pool_timestamp[sid.private_id] = now
      [sid, session]
    end
  end

  def set_session(env, session_id, new_session, options)
    with_lock(env) do
      @pool.store session_id.private_id, new_session
      # bump session's access time
      @pool_timestamp[session_id.private_id] = Time.now()
      session_id
    end
  end

  def destroy_session(env, session_id, options)
    with_lock(env) do
      delete_session(session_id.private_id)
      delete_session(session_id.public_id)
      generate_sid unless options[:drop]
    end
  end

  def drop_expired(env)
    return unless lifetime = @default_options[:expire_after]
    with_lock(env) {
      threshold = Time.now() - lifetime
      sid_to_delete = []
      @pool_timestamp.each { |sid, timestamp|
        sid_to_delete << sid if timestamp < threshold
      }
      sid_to_delete.each { |sid|
        delete_session(sid)
      }
    }
  end

  private

  def delete_session(sid)
    @pool.delete(sid)
    @pool_timestamp.delete(sid)
  end

  def get_timestamp_with_fallback(sid)
    @pool_timestamp[sid.private_id] || @pool_timestamp[sid.public_id]
  end
end

