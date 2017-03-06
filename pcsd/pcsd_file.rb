require 'base64'
require 'pcs.rb' #write_file_lock, read_file_lock
require 'settings.rb'

class PcsdFormatError < StandardError
  def self.for_file(id, message)
    new "file (key: #{id}): #{message}"
  end
end

module PcsdFile
  class PutFile
    def initialize(id, file)
      @id = id
      @file = file
    end

    def validate()
      PcsdFile::validate_file_key_with_string(@id, @file, :data)
    end

    def rewrite_existing()
      return @file[:rewrite_existing]
    end

    def full_file_name()
      raise NotImplementedError.new(
        "'#{__method__}' is not implemented in '#{self.class}'"
      )
    end

    def binary?()
      return true
    end

    def exists?()
      return @exists if defined? @exists
      @exists ||= File.file?(self.full_file_name)
    end

    def exists_with_same_content()
      unless self.exists?
        return false
      end

      if self.binary?
        return Base64.strict_encode64(self.read()) == @file[:data]
      end

      return self.read() == @file[:data]
    end

    def write()
      write_file_lock(
        self.full_file_name,
        self.permissions,
        self.binary? ? Base64.decode64(@file[:data]) : @file[:data],
        self.binary?
      )
    end

    def permissions()
      return nil
    end

    def read()
      return read_file_lock(self.full_file_name, self.binary?)
    end

    def process()
      self.validate()
      begin
        unless self.exists?
          self.write()
          return PcsdFile::result(:written)
        end

        if self.rewrite_existing
          self.write()
          return PcsdFile::result(:rewritten)
        end

        if self.exists_with_same_content()
          return PcsdFile::result(:same_content)
        end

        return PcsdFile::result(:conflict)
      rescue => e
        return PcsdFile::result(:unexpected, e.message)
      end
    end
  end

  class PutFileBooth < PutFile
    def validate()
      super
      PcsdFile::validate_file_key_with_string(@id, @file, :name)
      if @file[:name].empty?
        raise PcsdFormatError.for_file(@id, "'name' is empty")
      end
    end

    def dir()
      return BOOTH_CONFIG_DIR
    end

    def full_file_name()
      @full_file_name ||= File.join(self.dir, @file[:name])
    end

  end

  class PutFileBoothAuthfile < PutFileBooth
    def permissions()
      return 0600
    end
  end

  class PutFileBoothConfig < PutFileBooth
    def binary?()
      return false
    end
  end

  TYPES = {
    "booth_authfile" => PutFileBoothAuthfile,
    "booth_config" => PutFileBoothConfig,
  }
end

def PcsdFile.result(code, message="")
  return {
    :code => code,
    :message => message,
  }
end

def PcsdFile.validate_file_key_with_string(id, file_hash, key_name)
  unless file_hash.has_key?(key_name)
    raise PcsdFormatError.for_file(id, "'#{key_name}' is missing")
  end

  unless file_hash[key_name].is_a? String
    raise PcsdFormatError.for_file(
      id,
      "'#{key_name}' is not String: '#{file_hash[key_name].class}'"
    )
  end
end

def PcsdFile.no_hash_message(no_hash)
  return "should be 'Hash'. "+
      "But it is '#{no_hash.class}': #{JSON.generate(no_hash)}"
end

def PcsdFile.validate_file_map_is_Hash(file_map)
  unless file_map.is_a? Hash
    raise PcsdFormatError.new("files #{self.no_hash_message(file_map)}")
  end
end

def PcsdFile.validate_file_is_Hash(id, file_data)
  unless file_data.is_a? Hash
    raise PcsdFormatError.for_file(id, self.no_hash_message(file_data))
  end
end

def PcsdFile.put_file(id, file_hash)
  unless file_hash.has_key?(:type)
    raise PcsdFormatError.for_file(id, "'type' is missing")
  end

  unless PcsdFile::TYPES.key?(file_hash[:type])
    raise PcsdFormatError.for_file(
      id,
      "unsupported 'type' ('#{file_hash[:type]}')"+
      " supported are #{PcsdFile::TYPES.keys}"
    )
  end

  return PcsdFile::TYPES[file_hash[:type]].new(id, file_hash).process()
end
