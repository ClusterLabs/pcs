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
  
