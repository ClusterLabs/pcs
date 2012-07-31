Pcs = Ember.Application.create({
  update: function(first_run) {
    if (first_run)
      show_loading_screen();
    $.ajax({
      url: "/remote/status_all",
      dataType: "json",
      success: function(data) {
	Pcs.nodesController.update(data);
	Pcs.resourcesController.update(data);
	Ember.run.next(this,disable_checkbox_clicks);
	if (first_run) {
	  if ($('#resource_page')) {
	    Ember.run.next(this,function () {
	      Pcs.resourcesController.load_resource($('.node_selected').first());
	    });
	  } else {
	    Ember.run.next(this,function () {
	      Pcs.nodesController.load_node($('.node_selected').first());
	    });
	  }
	  hide_loading_screen();
	}
	window.setTimeout(Pcs.update,20000);
      },
      error: hide_loading_screen
    });
  }
});

Pcs.Resource = Ember.Object.extend({
  name: null,
  cur_resource: false,
  checked: false,
  nodes_running: [],
  up: function() {
    return this.active;
  }.property("active"),
  trclass: function(){
    if (this.cur_resource == true)
      return "node_selected";
    else
      return ""
  }.property("cur_resource"),
  onmouseover: function(){
    if (this.cur_resource == true)
      return ""
    else
      return "hover_over(this);"
  }.property("cur_resource"),
  onmouseout: function(){
    if (this.cur_resource == true)
      return ""
    else
      return "hover_out(this);"
  }.property("cur_resource"),
  showArrow: function(){
    if (this.cur_resource != true)
      return "display:none;"
    else
      return ""
  }.property("cur_resource"),
});

Pcs.Clusternode = Ember.Object.extend({
  name: null,
  cur_node: false,
  checked: false,
  resources_running: [],
  url: function() { return "window.location='/nodes/" + this.get("name")+"'"
  }.property(),
  trclass: function(){
    if (this.cur_node == true)
      return "node_selected";
  }.property("cur_node"),
  onmouseover: function(){
    if (this.cur_node == true)
      return ""
    else
      return "hover_over(this);"
  }.property("cur_node"),
  onmouseout: function(){
    if (this.cur_node == true)
      return ""
    else
      return "hover_out(this);"
  }.property("cur_node"),
  showArrow: function(){
    if (this.cur_node != true)
      return "display:none;"
    else
      return ""
  }.property("cur_node"),
  location_constraints: null
});

Pcs.resourcesController = Ember.ArrayController.create({
  content: [],
  no_resources: function () {
    if (this.content.length == 0)
      return true;
    else
      return false;
  }.property("content"),
  cur_resource: null,
  init: function(){
    this._super();
  },

  load_resource: function(resource_row) {
    load_row(resource_row, this, 'cur_resource');
    load_resource_agent_form(resource_row, this, 'cur_resource');
  },

  remove_constraint: function(constraint_id) {
    $.each(this.content, function(key, value) {
      if (value.location_constraints) {
	value.set("location_constraints", $.grep(value.location_constraints, function (value2, key) {
	  if (value2.id == constraint_id)
	    return false
	  return true;
	}));
      }
      if (value.ordering_constraints) {
	value.set("ordering_constraints", $.grep(value.ordering_constraints, function (value2, key) {
	  if (value2.id == constraint_id)
	    return false
	  return true;
	}));
      }
      if (value.colocation_constraints) {
	value.set("colocation_constraints", $.grep(value.colocation_constraints, function (value2, key) {
	  if (value2.id == constraint_id)
	    return false
	  return true;
	}));
      }
    });
  },


  update: function(data) {
    var self = this;
    var resources = {};
    var ord_con = {}
    var loc_con = {}
    var col_con = {}
    var res_loc_constraints = {};
    var res_ord_constraints = {};
    var res_col_constraints = {};
    $.each(data, function(key, value) {
      if (value["resources"]) {
	$.each(value["resources"], function(k2, v2) {
	  resources[v2["id"]] = v2;
	});
      }

      if (value["constraints"]) {
	if (value["constraints"]["rsc_location"]) {
	  $.each(value["constraints"]["rsc_location"], function (key, value) {
	    loc_con[value["id"]] = value;
	  });
	}
	if (value["constraints"]["rsc_order"]) {
	  $.each(value["constraints"]["rsc_order"], function (key, value) {
	    ord_con[value["id"]] = value;
	  });
	}
	if (value["constraints"]["rsc_colocation"]) {
	  $.each(value["constraints"]["rsc_colocation"], function (key, value) {
	    col_con[value["id"]] = value;
	  });
	}
      }
    });

    $.each(loc_con, function (key, value) {
      if (value["rsc"] in res_loc_constraints)
	res_loc_constraints[value["rsc"]].push(value);
      else res_loc_constraints[value["rsc"]] = [value];
    });

    var cur_res_holder = "";
    if (self.cur_resource)
      cur_res_holder = self.cur_resource.name

    resources_checked = {};
    $.each(self.content, function (key, value) {
      if (value.checked)
	resources_checked[value.name] = true;
    });


    $.each(ord_con, function (key, value) {
      first = $.extend({"other_rsc":value["then"],"before":false}, value);
      if (value["first"] in res_ord_constraints)
	res_ord_constraints[value["first"]].push(first);
      else res_ord_constraints[value["first"]] = [first];
      then = $.extend({"other_rsc":value["first"],"before":true}, value);
      if (value["then"] in res_ord_constraints)
	res_ord_constraints[value["then"]].push(then);
      else res_ord_constraints[value["then"]] = [then];
    });

    $.each(col_con, function (key, value) {
      if (value["score"] == "INFINITY")
	value["together"] = "Together";
      else if (value["score"] == "-INFINITY" || value["score"] < 0)
	value["together"] = "Apart";
      else if (value["score"] >= 0)
	value["together"] = "Together";

      first = $.extend({"other_rsc":value["with-rsc"],"first":true}, value);
      if (value["rsc"] in res_col_constraints)
	res_col_constraints[value["rsc"]].push(first);
      else res_col_constraints[value["rsc"]] = [first];
      second = $.extend({"other_rsc":value["rsc"],"first":false}, value);
      if (value["with-rsc"] in res_col_constraints)
	res_col_constraints[value["with-rsc"]].push(second);
      else res_col_constraints[value["with-rsc"]] = [second];
    });

    self.set('content',[]);
    $.each(resources, function(key, value) {
      var resource = Pcs.Resource.create({
	name: value["id"],
	agentname: value["agentname"],
	active: value["active"],
	nodes: value["nodes"],
	group: value["group"],
	clone: value["clone"],
	failed: value["failed"],
	orphaned: value["orphaned"],
	options: value["options"],
	location_constraints: res_loc_constraints[value["id"]],
	ordering_constraints: res_ord_constraints[value["id"]],
	colocation_constraints: res_col_constraints[value["id"]]
      });
      var pathname = window.location.pathname.split('/');

      if (cur_res_holder == "") {
	cur_res_name = pathname[pathname.length-1];
      } else {
	cur_res_name = cur_res_holder;
      }
      if (resource.name == cur_res_name) {
	resource.set("cur_resource",true);
	self.set("cur_resource", resource);
      }

      if (resources_checked[resource.name])
	resource.checked = true;

      self.pushObject(resource);
    });
    if (self.content && self.content.length > 0 && self.cur_resource == null) {
      self.set("cur_resource", self.content[0]);
      self.content[0].set("cur_resource",true);
    }
  }
});

Pcs.nodesController = Ember.ArrayController.create({
  content: [],
  cur_node: null,
  init: function(){
    this._super();
  },

  load_node: function(node_row){
    load_row(node_row, this, 'cur_node');
  },

  update: function(data){
    var self = this;
    var nodes = [];
    corosync_nodes_online = [];
    pacemaker_nodes_online = [];
    $.each(data, function(key, value) {
      nodes.push(key);
      if (value["corosync_online"])
	corosync_nodes_online = corosync_nodes_online.concat(value["corosync_online"]);
      if (value["pacemaker_online"])
	pacemaker_nodes_online = pacemaker_nodes_online.concat(value["pacemaker_online"]);

    });
    nodes.sort();
    var resources_on_nodes = {};
    var lc_on_nodes = {};
    $.each(data, function(node, node_info) {
      resources_on_nodes[node] = [];
      lc_on_nodes[node] = [];
      if (node_info["resources"]) {
	$.each(node_info["resources"], function(key, resource) {
	  $.each(resource["nodes"], function(node_key, resource_on_node) {
	    if (resources_on_nodes[resource_on_node])
	      resources_on_nodes[resource_on_node].push(resource["id"] + " (" +
							resource["agentname"] + ")");
	    else
	      resources_on_nodes[resource_on_node] = [resource["id"] + " (" +
		resource["agentname"] + ")"];
	  });
	});
      }
      if (node_info["constraints"] && node_info["constraints"]["rsc_location"]) {
	$.each(node_info["constraints"]["rsc_location"], function(key, constraint) {
	  if (constraint["node"] == node)
	    lc_on_nodes[node].push(constraint)
	});
      }
    });

    var nodes_checked = {};
    var cur_node_holder = "";
    if (self.cur_node)
      cur_node_holder = self.cur_node.name;
    $.each(self.content, function (key, value) {
      if (value.checked)
	nodes_checked[value.name] = true;
    });

    self.set('content',[]);
    $.each(nodes, function(key, node_id) {
      if (data[node_id]["noresponse"] == true) {
	up_status = false;
      } else {
	up_status = true;
      }

      if ($.inArray(node_id, corosync_nodes_online) > -1) {
	corosync_online = true;
      } else {
	corosync_online = false;
      }
      if ($.inArray(node_id, pacemaker_nodes_online) > -1) {
	pacemaker_online = true;
      } else {
	pacemaker_online = false;
      }

      var node = Pcs.Clusternode.create({
	name: node_id,
	up: up_status,
	corosync_daemon: data[node_id]["corosync"],
	pacemaker_daemon: data[node_id]["pacemaker"],
	corosync: corosync_online,
	pacemaker: pacemaker_online,
	cur_node: false,
	running_resources: $.unique(resources_on_nodes[node_id].sort().reverse()),
	location_constraints: lc_on_nodes[node_id].sort(),
	uptime: data[node_id]["uptime"]
      });
      var pathname = window.location.pathname.split('/');

      if (cur_node_holder == "") {
	cur_node_name = pathname[pathname.length-1];
      } else {
	cur_node_name = cur_node_holder;
      }
      if (node.name == cur_node_name) {
	node.set("cur_node",true);
	self.set("cur_node", node);
      }

      if (nodes_checked[node.name])
	node.checked = true;

      self.pushObject(node);
    });
    if (self.content && self.content.length > 0 && self.cur_node == null) {
      self.set("cur_node", self.content[0]);
      self.content[0].set("cur_node",true);
    }
  }
});

function myUpdate() {
  Pcs.update();
//  window.setTimeout(myUpdate,4000);
}

Pcs.update(true);
