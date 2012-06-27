# Wrapper for PCS command
#

def add_location_constraint(resource, node, score)
  id = "loc_" + node + "_" + resource
  puts "ADD LOCATION CONSTRAINT"
  puts PCS, "constraint", "location", "add", id, resource, node, score
  Open3.popen3(PCS, "constraint", "location", "add", id, resource,
	       node, score) { |stdin, stdout, stderror, waitth|
    puts stdout.readlines()
    return waitth.value
  }
end

def add_order_constraint(resourceA, resourceB, score, symmetrical = true)
  sym = symmetrical ? "symmetrical" : "nonsymmetrical"
  puts "ADD ORDER CONSTRAINT"
  puts PCS, "constraint", "order", "add", resourceA, resourceB, score, sym
  Open3.popen3(PCS, "constraint", "order", "add", resourceA,
	       resourceB, score, sym) { |stdin, stdout, stderror, waitth|
    puts stdout.readlines()
    return waitth.value
  }
end

def add_colocation_constraint(resourceA, resourceB, score)
  puts "ADD COLOCATION CONSTRAINT"
  puts PCS, "constraint", "colocation", "add", resourceA, resourceB, score
  Open3.popen3(PCS, "constraint", "colocation", "add", resourceA,
	       resourceB, score) { |stdin, stdout, stderror, waitth|
    puts stdout.readlines()
    return waitth.value
  }
end

def remove_constraint(constraint_id)
  puts "REMOVE CONSTRAINT"
  puts PCS, "constraint", "rm", constraint_id
  Open3.popen3(PCS, "constraint", "rm", constraint_id) { |stdin, stdout, stderror, waitth|
    puts stdout.readlines()
    return waitth.value
  }
end

def get_node_token(node)
  puts PCS, "cluster", "token", node
  Open3.popen3(PCS, "cluster", "token", node) { |stdin, stdout, stderror, waitth|
    return waitth.value,stdout.readlines()
  }
end

def send_request_with_token(node,request, post=false, data={})
  begin
    retval, token = get_node_token(node)
    puts "RETVAL/TOKEN"
    token = token[0].strip
    uri = URI.parse("http://#{node}:2222/remote/" + request)
    if post
      req = Net::HTTP::Post.new(uri.path)
      req.set_form_data(data)
    else
      req = Net::HTTP::Get.new(uri.path)
    end
    req.add_field("Cookie","token="+token)
    res = Net::HTTP.new(uri.host, uri.port).start do |http|
      http.request(req)
    end
    output = res
    return output.body
  rescue
    puts "No response from: " + node
    return '{"noresponse":true}'
  end
end

def add_node(new_nodename)
  Open3.popen3(PCS, "cluster", "localnode", "add", new_nodename) { |stdin, stdout, stderror, waitth|
    return waitth.value.exitstatus,stdout.readlines()
  }
end
