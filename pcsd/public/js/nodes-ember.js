Pcs = Ember.Application.createWithMixins({
  LOG_TRANSITIONS: true,
  cluster_name: get_cluster_name(),
  cluster_settings: null,
  cur_page: "",
  opening_resource: "",
  opening_node: "",
  resource_page: function() {
    if (this.cur_page == "resources") return "display: table-row;";
    else return "display: none;";
  }.property("cur_page"),
  node_page: function() {
    if (this.cur_page == "nodes") return "display: table-row;";
    else return "display: none;";
  }.property("cur_page"),
  stonith_page: function() {
    if (this.cur_page == "stonith") return "display: table-row;";
    else return "display: none;";
  }.property("cur_page"),
  configure_page: function() {
    if (this.cur_page == "configure") return "display: table-row;";
    else return "display: none;";
  }.property("cur_page"),
  manage_page: function() {
    if (this.cur_page == "manage") return "display: table-row;";
    else return "display: none;";
  }.property("cur_page"),
  wizards_page: function() {
    if (this.cur_page == "wizards") return "display: table-row;";
    else return "display: none;";
  }.property("cur_page"),

  getResourcesFromID: function(resources) {
    retArray = [];
    for (var i=0; i < resources.length; i++) {
      $.each(this.resourcesController.content, function(ind,v) { 
      	if (v.name == resources[i]) {
      	  retArray.push(v);
	}
      });
    }
    return retArray;
  },
  update_timeout: null,
  update: function(first_run) {
    if (first_run)
      show_loading_screen();
    if (this.cluster_name == null) {
      Ember.debug("Empty Cluster Name");
      hide_loading_screen();
      return;
    }
    $.ajax({
      url:  "status_all",
//      url: "/test_status.json",
      dataType: "json",
      success: function(data) {
	Pcs.resourcesController.update(data);
	Pcs.nodesController.update(data);
	Pcs.settingsController.update(data);
	Pcs.set("cluster_settings",data[Object.keys(data)[0]].cluster_settings);
	Ember.run.next(this,disable_checkbox_clicks);
	if (first_run) {
	    Ember.run.next(this,function () {
	      Pcs.resourcesController.load_resource($('#resource_list_row').find('.node_selected').first(),true);
	      Pcs.resourcesController.load_stonith($('#stonith_list_row').find('.node_selected').first(),true);
	      Pcs.nodesController.load_node($('#node_list_row').find('.node_selected').first(),true);
	    });
	    Pcs.selectedNodeController.reset();
	    setup_node_links();
	    setup_resource_links();
	} 
	hide_loading_screen();
	clearTimeout(Pcs.update_timeout);
	Pcs.update_timeout = window.setTimeout(Pcs.update,20000);
      },
      error: function(a,b,c) {
	hide_loading_screen();
      }

    });
  }
});

Pcs.Router.map(function() {
  this.route("Configuration", { path: "configure"});
  this.resource("Fence Devices", {path: "fencedevices/:stonith_id"}, function () {
    this.route('new');
  });
  this.route("Fence Devices", { path: "fencedevices"});
  this.resource("Resources", {path: "resources/:resource_id"}, function () {
    this.route('new');
  });
  this.route("Resources", { path: "resources"});
  this.resource("Nodes", {path: "nodes/:node_id"}, function () {
    this.route('new');
  });
  this.route("Nodes", { path: "nodes"});
//  this.resource("Resource", {path: 'resources/:resource_id'});
  this.route("Manage", {path: "manage"});
  this.route("Wizards", {path: "wizards"});
  this.route("Default Route", { path: "*x" });
});

Pcs.ManageRoute = Ember.Route.extend({
  setupController: function(controller, model) {
    select_menu("MANAGE");
  }
});

Pcs.WizardsRoute = Ember.Route.extend({
  setupController: function(controller, model) {
    select_menu("WIZARDS");
  }
});

Pcs.IndexRoute = Ember.Route.extend({
  setupController: function(controller, model) {
    if (window.location.pathname == "/manage")
      select_menu("MANAGE");
    else
      select_menu("NODES");
  }
});

Pcs.DefaultRouteRoute = Ember.Route.extend({
  setupController: function(controller, model) {
    if (window.location.pathname.substring(0,7) == "/manage")
      select_menu("MANAGE");
    else
      select_menu("NODES");
  }
});

Pcs.FenceDevicesRoute = Ember.Route.extend({
  setupController: function(controller, model) {
    select_menu("FENCE DEVICES");
    if (model) {
      Pcs.resourcesController.set("cur_resource",model);
      Pcs.resourcesController.update_cur_resource();
    }
  },
  model: function(params) {
    Ember.debug("Router FD: " + params.stonith_id);
    Pcs.opening_resource = params.stonith_id;
    return null;
  }
});

Pcs.NodesRoute = Ember.Route.extend({
  setupController: function(controller, model) {
    select_menu("NODES");
  },
  model: function(params) {
    Pcs.opening_node = params.node_id;
    return null;
  }
});

Pcs.ConfigurationRoute = Ember.Route.extend({
  setupController: function(controller, model) {
    select_menu("CONFIGURE"); 
  }
});

Pcs.ResourcesRoute = Ember.Route.extend({
  setupController: function(controller, model) {
    select_menu("RESOURCES"); 
    if (model) {
      Pcs.resourcesController.set("cur_resource",model);
      Pcs.resourcesController.update_cur_resource();
    }
  },
  model: function(params) {
    Ember.debug("Router Resource: " + params.resource_id);
    Pcs.opening_resource = params.resource_id;
    return null;
  }
});

Pcs.Setting = Ember.Object.extend({
  name: null,
  value: null,
  type: null
});

Pcs.Resource = Ember.Object.extend({
  name: null,
  id: function() {
    return this.name;
  }.property("name"),
  ms: false,
  clone: false,
  full_name: function() {
    if (this.ms)
      return this.name + " (M/S)";
    if (this.clone)
      return this.name + " (Clone)";
    return this.name;
  }.property("name"),
  cur_resource: false,
  checked: false,
  nodes_running: [],
  up: function() {
    return this.active;
  }.property("active"),
  resource_name_style: function() {
    if (this.active) {
      return "";
    } else {
      return "color:red";
    }
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
  res_class: function() {
    cpt = this.agentname.split(":");
    return cpt[0];
  }.property("agentname"),
  res_provider: function() {
    cpt = this.agentname.split(":");
    return cpt[2];
  }.property("agentname"),
  res_type: function() {
    cpt = this.agentname.split(":");
    if (this.stonith) 
      return cpt[1];
    return cpt[3];
  }.property("agentname"),
  showArrow: function(){
    if (this.cur_resource != true)
      return "display:none;"
    else
      return ""
  }.property("cur_resource")
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
  node_name_style: function() {
    if (this.up) {
      return "";
    } else {
      if (this.pacemaker_standby)
      	return "color: #ff6600";
      else
	return "color:red";
    }
  }.property("up","pacemaker_standby"),
  standby_style: function () {
    if (this.pacemaker_standby)
      return "display: none;";
    else
      return "";
  }.property("pacemaker_standby"),
  unstandby_style: function() {
    if (this.pacemaker_standby)
      return "";
    else
      return "display: none;";
  }.property("pacemaker_standby"),
  location_constraints: null
});

Pcs.settingsController = Ember.ArrayController.create({
  content: [],
  update: function(data) {
    var self = this;
    var settings = {};
    self.set('content',[]);
    $.each(data, function(key, value) {
      if (value["cluster_settings"]) {
	$.each(value["cluster_settings"], function(k2, v2) {
	  var setting = Pcs.Setting.create({
	    name: k2,
	    value: v2
	  });
	  self.pushObject(setting);
	});
      }
    });
  }
});

Pcs.resourcesController = Ember.ArrayController.createWithMixins({
  content: [],
  sortProperties: ['name'],
  sortAscending: true,
  no_resources: function () {
    if (this.content.length == 0)
      return true;
    else
      return false;
  }.property("@each.content"),
  cur_resource: null,
  cur_resource_res: null,
  cur_resource_ston: null,
  init: function(){
    this._super();
  },

  update_cur_resource: function() {
    if (this.get("cur_resource")) { 
      cr = this.get("cur_resource").name;
      $.each(this.content, function(key, value) {
	if (value.name == cr)
	  value.set("cur_resource", true);
	else
	  value.set("cur_resource", false);
      });
    }
  },
    
  load_resource: function(resource_row, dont_update_hash) {
    if (resource_row.length == 0)
      return;
    var temp_cur_resource = Pcs.resourcesController.cur_resource;
    load_row(resource_row, this, 'cur_resource', "#resource_info_div", 'cur_resource_res');
    load_agent_form(resource_row, false);
    if (!dont_update_hash)
      window.location.hash = "/resources/" + $(resource_row).attr("nodeID");

    // If we're not on the resource page, we don't update the cur_resource
    if (Pcs.cur_page != "resources") {
      Pcs.resourcesController.set('cur_resource',temp_cur_resource);
    }
  },

  load_stonith: function(resource_row, dont_update_hash) {
    if (resource_row.length == 0)
      return;
    var temp_cur_resource = Pcs.resourcesController.cur_resource;
    load_row(resource_row, this, 'cur_resource', "#stonith_info_div", 'cur_resource_ston');
    load_agent_form(resource_row, true);
    if (!dont_update_hash)
      window.location.hash = "/fencedevices/" + $(resource_row).attr("nodeID");

    // If we're not on the stonith page, we don't update the cur_resource
    if (Pcs.cur_page != "stonith")
      Pcs.resourcesController.set('cur_resource',temp_cur_resource);
  },

  add_loc_constraint: function(res_id, constraint_id, node_id, score, stickyness) {
    new_loc_constraint = {}
    new_loc_constraint["id"] = constraint_id;
    new_loc_constraint["rsc"] = res_id;
    new_loc_constraint["node"] = node_id;
    new_loc_constraint["score"] = score;
    new_loc_constraint["temp"] = true;

    $.each(this.content, function(key, value) {
      if (value.name == res_id) {
	if (value.get("location_constraints")) {
	  var res_loc_constraints = {};
	  $.each(value.get("location_constraints"), function (key, value) {
	    if (res_id in res_loc_constraints)
	      res_loc_constraints[res_id].push(value);
	    else res_loc_constraints[res_id] = [value];
	  });
	  res_loc_constraints[res_id].push(new_loc_constraint);
	  value.set("location_constraints", res_loc_constraints[res_id]);
	} else {
	  value.set("location_constraints", [new_loc_constraint]);
	}
      }
    });
  },

  add_ord_constraint: function(res_id, constraint_id, target_res_id, order, score) {
    new_ord_constraint = {}
    new_ord_constraint["id"] = constraint_id;
    new_ord_constraint["res_id"] = res_id;
    new_ord_constraint["first"] = res_id;
    new_ord_constraint["then"] = res_id;
    new_ord_constraint["order"] = order;
    new_ord_constraint["score"] = score;
    new_ord_constraint["other_rsc"] = target_res_id;

    new_ord_constraint["temp"] = true;
    if (order == "before") new_ord_constraint["before"] = true;

    $.each(this.content, function(key, value) {
      if (value.name == res_id) {
	if (value.get("ordering_constraints")) {
	  var res_ord_constraints = {};
	  $.each(value.get("ordering_constraints"), function (key, value) {
	    if (res_id in res_ord_constraints)
	      res_ord_constraints[res_id].push(value);
	    else res_ord_constraints[res_id] = [value];
	  });
	  res_ord_constraints[res_id].push(new_ord_constraint);
	  value.set("ordering_constraints", res_ord_constraints[res_id]);
	} else {
	  value.set("ordering_constraints", [new_ord_constraint]);
	}
      }
    });
  },

  add_col_constraint: function(res_id, constraint_id, target_res_id, colocation_type, score) {
    new_col_constraint = {}
    new_col_constraint["id"] = constraint_id;
    new_col_constraint["res_id"] = res_id;
    new_col_constraint["score"] = score;
    new_col_constraint["other_rsc"] = target_res_id;
    if (colocation_type == "apart")
      new_col_constraint["together"] = "Apart";
    else
      new_col_constraint["together"] = "Together";

    new_col_constraint["temp"] = true;

    $.each(this.content, function(key, value) {
      if (value.name == res_id) {
	if (value.get("colocation_constraints") && value.get("colocation_constraints").length > 0) {
	  var res_col_constraints = {};
	  $.each(value.get("colocation_constraints"), function (key, value) {
	    if (res_id in res_col_constraints)
	      res_col_constraints[res_id].push(value);
	    else res_col_constraints[res_id] = [value];
	  });
	  res_col_constraints[res_id].push(new_col_constraint);
	  value.set("colocation_constraints", res_col_constraints[res_id]);
	} else {
	  value.set("colocation_constraints", [new_col_constraint]);
	}
      }
    });
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
    var cur_res_holder_res = "";
    var cur_res_holder_ston = "";
    if (self.cur_resource)
      cur_res_holder = self.cur_resource.name;
    if (self.cur_resource_res)
      cur_res_holder_res = self.cur_resource_res.name;
    if (self.cur_resource_ston)
      cur_res_holder_ston = self.cur_resource_ston.name;

    self.set("cur_resource",null);
    self.set("cur_resource_res",null);
    self.set("cur_resource_ston",null);

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

//    self.set('content',[]);
    $.each(resources, function(key, value) {
      found = false;
      var resource = null;
      $.each(self.content, function(key, pre_existing_resource) {
	if (pre_existing_resource && pre_existing_resource.name == value["id"]) {
	  found = true;
	  resource = pre_existing_resource;
	  resource.set("agentname", value["agentname"]);
	  resource.set("active", value["active"]);
	  resource.set("nodes", value["nodes"]);
	  resource.set("group", value["group"]);
	  resource.set("clone", value["clone"]);
	  resource.set("ms", value["ms"]);
	  resource.set("failed", value["failed"]);
	  resource.set("orphaned", value["orphaned"]);
	  resource.set("options", value["options"]);
	  resource.set("location_constraints", res_loc_constraints[value["id"]]);
	  resource.set("ordering_constraints", res_ord_constraints[value["id"]]);
	  resource.set("colocation_constraints", res_col_constraints[value["id"]]);
	  resource.set("stonith", value["stonith"]);
	}
      });
      if (found == false) {
	resource = Pcs.Resource.create({
	  name: value["id"],
	  agentname: value["agentname"],
	  active: value["active"],
	  nodes: value["nodes"],
	  group: value["group"],
	  clone: value["clone"],
	  ms: value["ms"],
	  failed: value["failed"],
	  orphaned: value["orphaned"],
	  options: value["options"],
	  location_constraints: res_loc_constraints[value["id"]],
	  ordering_constraints: res_ord_constraints[value["id"]],
	  colocation_constraints: res_col_constraints[value["id"]],
	  stonith: value["stonith"]
	});
      }
      var pathname = window.location.pathname.split('/');

      if (cur_res_holder == "") {
	cur_res_name = Pcs.opening_resource;
      } else {
	cur_res_name = cur_res_holder;
      }
      if (resource.name == cur_res_name) {
	resource.set("cur_resource",true);
	self.set("cur_resource", resource);
      }

      if (resource.name == cur_res_holder_res) {
	resource.set("cur_resource",true);
	self.set("cur_resource_res", resource);
      }

      if (resource.name == cur_res_holder_ston) {
	resource.set("cur_resource",true);
	self.set("cur_resource_ston", resource);
      }

      if (resources_checked[resource.name])
	resource.set('checked', true);

      if (found == false)
	self.pushObject(resource);
    });
    
    var resourcesToRemove = [];
    $.each(self.content, function(key, res) {
      found = false;
      $.each(resources, function(k2, res2) {
      	if (res && res2["id"] == res.name) {
      	  found = true;
	}
      });
      if (!found && res) {
	resourcesToRemove.push(res);
      }
    });

    // If any resources have been renamed or removed we remove them content
    $.each(resourcesToRemove, function(k, v) {
      self.content.removeObject(v);
    });

    if (self.content && self.content.length > 0 && self.cur_resource == null) {
      for (var i=0; i< self.content.length; i++) {
	if (self.content[i].stonith) {
	  self.set("cur_resource_ston", self.content[i]);
	  self.content[i].set("cur_resource",true);
	  break;
	}
      }
      for (var i=0; i< self.content.length; i++) {
	if (!self.content[i].stonith) {
	  self.set("cur_resource_res", self.content[i]);
	  self.content[i].set("cur_resource",true);
	  break;
	}
      }
      if (Pcs.cur_page == "resources")
	self.set("cur_resource", self.cur_resource_res);
      if (Pcs.cur_page == "stonith") {
	self.set("cur_resource", self.cur_resource_ston);
      }
    }
  }
});

Pcs.selectedNodeController = Ember.Object.createWithMixins({
  node: null,
  reset: function() {
    if (Pcs.nodesController)
      this.set('node', Pcs.nodesController.objectAt(0));
  }
});

Pcs.nodesController = Ember.ArrayController.createWithMixins({
  content: [],
  cur_node: null,
  init: function(){
    this._super();
  },

  load_node: function(node_row, dont_update_hash){
    load_row(node_row, this, 'cur_node', '#node_info_div');
    if (!dont_update_hash)
      window.location.hash = "/nodes/" + $(node_row).attr("nodeID");
  },

  update: function(data){
    var self = this;
    var nodes = [];
    corosync_nodes_online = [];
    pacemaker_nodes_online = [];
    pacemaker_nodes_standby = [];
    $.each(data, function(key, value) {
      nodes.push(key);
      if (value["corosync_online"])
	corosync_nodes_online = corosync_nodes_online.concat(value["corosync_online"]);
      if (value["pacemaker_online"])
	pacemaker_nodes_online = pacemaker_nodes_online.concat(value["pacemaker_online"]);
      if (value["pacemaker_standby"])
	pacemaker_nodes_standby = pacemaker_nodes_standby.concat(value["pacemaker_standby"]);
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
	      resources_on_nodes[resource_on_node].push(resource["id"]);
	    else
	      resources_on_nodes[resource_on_node] = [resource["id"]];
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

//    self.set('content',[]);
    $.each(nodes, function(key, node_id) {
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

      if ($.inArray(node_id, pacemaker_nodes_standby) > -1) {
	pacemaker_standby = true;
      } else {
	pacemaker_standby = false;
      }

      if (data[node_id]["noresponse"] == true) {
	pcsd_daemon = false
      } else {
	pcsd_daemon = true
      }

      if (data[node_id]["notauthorized"] == "true") {
	authorized = false;
      } else {
	authorized = true;
      }

      if (data[node_id]["corosync"] && data[node_id]["pacemaker"] &&
		pacemaker_online && corosync_online) {
	up_status = true;
      } else {
       up_status = false;
      }       

      found = false;
      var node = null;
      $.each(self.content, function(key, pre_existing_node) {
	if (pre_existing_node && pre_existing_node.name == node_id) {
	  node = pre_existing_node;
	  found = true;
	  node.set("authorized",authorized);
	  node.set("up",up_status);
	  node.set("pcsd",pcsd_daemon && authorized);
	  node.set("corosync_daemon", data[node_id]["corosync"]);
	  node.set("pacemaker_daemon", data[node_id]["pacemaker"]);
	  node.set("corosync", corosync_online);
	  node.set("pacemaker", pacemaker_online);
	  node.set("pacemaker_standby", pacemaker_standby);
	  node.set("cur_node",false);
	  node.set("running_resources", Pcs.getResourcesFromID($.unique(resources_on_nodes[node_id].sort().reverse())));
	  node.set("location_constraints", lc_on_nodes[node_id].sort());
	  node.set("uptime", data[node_id]["uptime"]);
	  node.set("node_id", data[node_id]["node_id"]);
	}
      });

      if (found == false) {
	var node = Pcs.Clusternode.create({
	  name: node_id,
	  authorized:  authorized,
	  up: up_status,
	  pcsd: pcsd_daemon && authorized,
	  corosync_daemon: data[node_id]["corosync"],
	  pacemaker_daemon: data[node_id]["pacemaker"],
	  corosync: corosync_online,
	  pacemaker: pacemaker_online,
	  pacemaker_standby: pacemaker_standby,
	  cur_node: false,
	  running_resources: Pcs.getResourcesFromID($.unique(resources_on_nodes[node_id].sort().reverse())),
	  location_constraints: lc_on_nodes[node_id].sort(),
	  uptime: data[node_id]["uptime"],
	  node_id: data[node_id]["node_id"]
	});
      }
      var pathname = window.location.pathname.split('/');

      if (cur_node_holder == "") {
	cur_node_name = Pcs.opening_node;
      } else {
	cur_node_name = cur_node_holder;
      }
      if (node.name == cur_node_name) {
	node.set("cur_node",true);
	self.set("cur_node", node);
      }

      if (nodes_checked[node.name])
	node.set("checked",true);

      if (found == false)
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
