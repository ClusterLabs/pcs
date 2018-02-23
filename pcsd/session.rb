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

  def find_session(req, sid)
    with_lock(req) do
      now = Time.now()
      # delete the session if expired
      if @default_options[:expire_after] and sid and @pool_timestamp[sid] and
        @pool_timestamp[sid] < (now - @default_options[:expire_after])
      then
        remove_session(sid)
      end
      # create new session if nonexistent
      unless sid and session = @pool[sid]
        sid, session = generate_sid, {}
        @pool.store sid, session
      end
      # bump session's access time
      @pool_timestamp[sid] = now
      [sid, session]
    end
  end

  def write_session(req, session_id, new_session, options)
    with_lock(req) do
      @pool.store session_id, new_session
      # bump session's access time
      @pool_timestamp[session_id] = Time.now()
      session_id
    end
  end

  def delete_session(req, session_id, options)
    with_lock(req) do
      remove_session(session_id)
      generate_sid unless options[:drop]
    end
  end

  def drop_expired(req)
    return unless lifetime = @default_options[:expire_after]
    with_lock(req) {
      threshold = Time.now() - lifetime
      sid_to_delete = []
      @pool_timestamp.each { |sid, timestamp|
        sid_to_delete << sid if timestamp < threshold
      }
      sid_to_delete.each { |sid|
        remove_session(sid)
      }
    }
  end

  private

  def remove_session(sid)
    @pool.delete(sid)
    @pool_timestamp.delete(sid)
  end
end

