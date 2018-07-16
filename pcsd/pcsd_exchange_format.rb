module PcsdExchangeFormat
  class Error < StandardError
    def self.for_item(item_name, id, message)
      new "#{item_name} (key: #{id}): #{message}"
    end
  end
end

def PcsdExchangeFormat::result(code, message="")
  return {
    :code => code,
    :message => message,
  }
end

def PcsdExchangeFormat.no_hash_message(no_hash)
  return "should be 'Hash'. "+
      "But it is '#{no_hash.class}': #{JSON.generate(no_hash)}"
end

def PcsdExchangeFormat.validate_item_map_is_Hash(items_name, item_map)
  unless item_map.is_a? Hash
    raise PcsdExchangeFormat::Error.new(
      "#{items_name} #{self.no_hash_message(item_map)}"
    )
  end
end

def PcsdExchangeFormat.validate_item_is_Hash(item_name, id, file_data)
  unless file_data.is_a? Hash
    raise PcsdExchangeFormat::Error.for_item(
      item_name, id, PcsdExchangeFormat::no_hash_message(file_data)
    )
  end
end

def PcsdExchangeFormat.validate_item_is_Array(item_name, data)
  unless data.is_a? Array
    raise PcsdExchangeFormat::Error.new(
      item_name,
      "Should be 'Array', but is '#{data.class}': #{JSON.generate(data)}"
    )
  end
end

def PcsdExchangeFormat.run_action(action_types, item_name, id, action_hash)
  unless action_hash.has_key?(:type)
    raise PcsdExchangeFormat::Error.for_item(item_name, id, "'type' is missing")
  end

  unless action_types.key?(action_hash[:type])
    raise PcsdExchangeFormat::Error.for_item(
      item_name,
      id,
      "unsupported 'type' ('#{action_hash[:type]}')"+
      " supported are #{action_types.keys}"
    )
  end

  return action_types[action_hash[:type]].new(id, action_hash).process()
end
