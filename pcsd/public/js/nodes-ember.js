Pcs = Ember.Application.createWithMixins({
  LOG_TRANSITIONS: true,
  cluster_name: get_cluster_name(),
  cluster_settings: null,
  cur_page: "",
  opening_resource: "",
  opening_node: "",
  opening_aclrole: "",
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
  acls_page: function() {
    if (this.cur_page == "acls") return "display: table-row;";
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
	if (v.name == resources[i] && v.stonith == false) {
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
	Pcs.aclsController.update(data);
	Pcs.set("cluster_settings",data[Object.keys(data)[0]].cluster_settings);
        Pcs.set('need_ring1_address', false)
        Pcs.set('is_cman_with_udpu_transport', false)
        $.each(data, function(node, node_data) {
          $.each(node_data, function(key, value) {
            if (key == 'need_ring1_address' && value) {
              Pcs.set('need_ring1_address', true);
            }
            if (key == 'is_cman_with_udpu_transport' && value) {
              Pcs.set('is_cman_with_udpu_transport', true);
            }
          });
        });
	Ember.run.next(this,disable_checkbox_clicks);
	if (first_run) {
	    Ember.run.next(this,function () {
	      Pcs.resourcesController.load_resource($('#resource_list_row').find('.node_selected').first(),true);
	      Pcs.resourcesController.load_stonith($('#stonith_list_row').find('.node_selected').first(),true);
	      Pcs.nodesController.load_node($('#node_list_row').find('.node_selected').first(),true);
        Pcs.aclsController.load_role($('#acls_list_row').find('.node_selected').first(), true);
	    });
	    Pcs.selectedNodeController.reset();
	    setup_node_links();
	    setup_resource_links();
	} 
	hide_loading_screen();
	clearTimeout(Pcs.update_timeout);
	Pcs.update_timeout = window.setTimeout(Pcs.update,20000);
      },
      error: function(jqhxr,b,c) {
	if (jqhxr.responseText) {
	  try {
	    var obj = $.parseJSON(jqhxr.responseText);
	    if (obj.notauthorized == "true") {
	      location.reload();
	    }
	  } catch(e) {
	    console.log("Error: Unable to parse json for status_all")
	  }
	}
	hide_loading_screen();
      }

    });
  }
});

Pcs.Router.map(function() {
  this.route("Configuration", { path: "configure"});
  this.resource("ACLs", {path: "acls/:aclrole_id"}, function () {
    this.route("new");
  });
  this.route("ACLs", {path: "acls"});
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
    if (window.location.pathname == "/manage" || window.location.pathname == "/manage/")
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

Pcs.ACLsRoute = Ember.Route.extend({
  setupController: function(controller, model) {
    select_menu("ACLS");
  },
  model: function(params) {
    Pcs.opening_aclrole = params.aclrole_id;
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
    if (model) {
      select_menu("RESOURCES",model.name); 
    } else {
      select_menu("RESOURCES"); 
    }
  },
  model: function(params) {
    Pcs.opening_resource = params.resource_id;
    return params.resource_id;
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
  }.property("name","ms","clone"),
  cur_resource: false,
  checked: false,
  nodes_running: [],
  up: function() {
    return this.active;
  }.property("active"),
  resource_name_style: function() {
    if (this.active && !this.failed) {
      return "";
    } else {
      return "color:red";
    }
  }.property("active", "failed"),

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
  corosync_startup: function() {
    if (this.corosync_enabled)
      return "Enabled";
    else
      return "Disabled";
  }.property("corosync_enabled"),
  pacemaker_startup: function() {
    if (this.pacemaker_enabled)
      return "Enabled";
    else
      return "Disabled";
  }.property("pacemaker_enabled"),
  pcsd_startup: function() {
    if (this.pcsd_enabled)
      return "Enabled";
    else
      return "Disabled";
  }.property("pcsd_enabled"),
  location_constraints: null
});

Pcs.Aclrole = Ember.Object.extend({
  name: null,
  cur_role: false,
  checked: false,
  description: "",
  user_list: null,
  group_list: null,
  trclass: function() {
    return this.cur_role ? "node_selected" : "";
  }.property("cur_role"),
  onmouseover: function() {
    return this.cur_role ? "" : "hover_over(this);"
  }.property("cur_role"),
  onmouseout: function() {
    return this.cur_role ? "" : "hover_out(this);"
  }.property("cur_role"),
  showArrow: function(){
    return this.cur_role ? "" : "display:none";
  }.property("cur_role"),
});

Pcs.aclsController = Ember.ArrayController.createWithMixins({
  content: [],
  cur_role: null,
  role_list: function() {
    if (this.get("roles"))
      return Object.keys(this.get("roles"));
    return [];
  }.property("roles"),
  user_list: function() {
    if (this.get("users"))
      return Object.keys(this.get("users"));
    return [];
  }.property("users"),
  group_list: function() {
    if (this.get("groups"))
      return Object.keys(this.get("groups"));
    return [];
  }.property("groups"),
  load_role: function(role_row, dont_update_hash) {
    load_row(role_row, this, 'cur_role', '#role_info_div');
    if (!dont_update_hash) {
      window.location.hash = "/acls/" + $(role_row).attr("nodeID");
    }
  },
  update: function(data) {
    var self = this;
    self.set('content',[]);
    var my_groups = {}, my_users = {}, my_roles = {};
    var cur_role_holder = "";
    var cur_role_name = "";
    $.each(data, function(key, value) {
      if (value["acls"]) {
        if (value["acls"]["group"]) {
          $.each(value["acls"]["group"], function (k2,v2) {
            my_groups[k2] = v2;
          });
        }
        if (value["acls"]["user"]) {
          $.each(value["acls"]["user"], function (k2,v2) {
            my_users[k2] = v2;
          });
        }
        if (value["acls"]["role"]) {
          $.each(value["acls"]["role"], function (k2,v2) {
            my_roles[k2] = v2;
          });
        }
      }
    });
    self.set('roles',my_roles);
    self.set('users',my_users);
    self.set('groups',my_groups);

    cur_role_holder = self.cur_role ? self.cur_role.name : "";

    $.each(my_roles, function(role_name, role_data) {
      var found = false;
      var role = null;
      $.each(self.content, function(key, pre_existing_role) {
        if(pre_existing_role && pre_existing_role.name == role_name) {
          found = true;
          role = pre_existing_role;
          role.set("name", role_name);
          role.set("cur_role", false);
          role.set("description", role_data["description"]);
        }
      });
      if (!found) {
        role = Pcs.Aclrole.create({
          name: role_name,
          cur_role: false,
          description: role_data["description"],
        });
      }
      if (role_data["permissions"]) {
        $.each(role_data["permissions"], function(key, permission) {
          var parsed = permission.match(/(\S+)\s+(\S+)\s+(.+)\((.*)\)/);
          role["permissions"] = role["permissions"] || [];
          role["permissions"].push({
            type: parsed[1],
            xpath_id: parsed[2],
            query_id: parsed[3],
            permission_id: parsed[4],
          });
        });
      }

      if (cur_role_holder == "") {
        cur_role_name = Pcs.opening_aclrole;
      }
      else {
        cur_role_name = cur_role_holder;
      }
      if (role.name == cur_role_name) {
        role.set("cur_role", true);
        self.set("cur_role", role);
      }

      if (!found) {
        self.pushObject(role);
      }
    });

    if (self.content && self.content.length > 0 && self.cur_role == null) {
      self.set("cur_role", self.content[0]);
      self.content[0].set("cur_role", true);
    }

    $.each(my_users, function(user_name, role_list) {
      $.each(role_list, function(key1, role_name) {
        $.each(self.content, function(key2, existing_role) {
          if (existing_role.name == role_name) {
            if (!existing_role.user_list) {
              existing_role.user_list = [user_name];
            }
            else if (existing_role.user_list.indexOf(user_name) == -1) {
              existing_role.user_list.push(user_name);
            }
          }
        });
      });
    });
    $.each(my_groups, function(group_name, role_list) {
      $.each(role_list, function(key1, role_name) {
        $.each(self.content, function(key2, existing_role) {
          if (existing_role.name == role_name) {
            if (!existing_role.group_list) {
              existing_role.group_list = [group_name];
            }
            else if (existing_role.group_list.indexOf(group_name) == -1) {
              existing_role.group_list.push(group_name);
            }
          }
        });
      });
    });
  }
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
  parentIDMapping: {},
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
  cur_resource_info_style: function () {
    if (typeof this.cur_resource != 'undefined' && this.cur_resource != null)
      return "";
    else
      return "opacity:0";
  }.property("cur_resource"),
  stonith_resource_list: function () {
    var list = [];
    this.content.map(function (item) {
      if (item.stonith)
        list.push(item.name);
    });
    return list;
  }.property("@each.content"),
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
    this.auto_show_hide_constraints();
  },
    
  load_resource: function(resource_row, dont_update_hash) {
    if (resource_row.length == 0)
      return;
    load_agent_form(resource_row, false);
    if (!dont_update_hash)
      window.location.hash = "/resources/" + $(resource_row).attr("nodeID");

    if (Pcs.cur_page == "resources")
      load_row(resource_row, this, 'cur_resource', "#resource_info_div", 'cur_resource_res', false);
    else
      load_row(resource_row, this, 'cur_resource', "#resource_info_div", 'cur_resource_res', true);
  },

  load_stonith: function(resource_row, dont_update_hash) {
    if (resource_row.length == 0)
      return;

    load_agent_form(resource_row, true);
    if (!dont_update_hash)
      window.location.hash = "/fencedevices/" + $(resource_row).attr("nodeID");

    if (Pcs.cur_page == "stonith")
      load_row(resource_row, this, 'cur_resource', "#stonith_info_div", 'cur_resource_ston', false);
    else
      load_row(resource_row, this, 'cur_resource', "#stonith_info_div", 'cur_resource_ston', true);
  },

  auto_show_hide_constraints: function() {
    var cont = ["location_constraints", "ordering_constraints", "ordering_set_constraints", "colocation_constraints", "meta_attr"];
    cont.forEach(function(name) {
    var elem = $("#" + name)[0];
    var resource = Pcs.resourcesController.get("cur_resource_res");
      if (elem && resource) {
        var visible = $(elem).children("span")[0].style.display != 'none';
        if (visible && (!resource.get(name) || resource[name].length == 0))
          show_hide_constraints(elem);
        else if (!visible && resource.get(name) && resource[name].length > 0)
          show_hide_constraints(elem);
      }
    });
  },

  add_meta_attr: function(res_id, mkey, mvalue) {
    $.each(this.content, function(key, value) {
      if (value.name == res_id) {
	var meta_attrs = [];
	if (value.meta_attr) {
	  meta_attrs = value.meta_attr;
	}

	var found = false;
	$.each(meta_attrs, function (index,attr) {
	  if (attr.key == mkey) {
	    attr.value = mvalue;
	    found = true;
	  }
	});

	if (!found) {
	  meta_attrs.pushObject({key: mkey, value: mvalue})
	}
	value.set("meta_attr", meta_attrs);
      }
    });
  },

  add_loc_constraint: function(res_id, constraint_id, node_id, score) {
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

  add_ord_constraint: function(res_id, constraint_id, target_res_id, res_action, target_action, order, score) {
    new_ord_constraint = {}
    new_ord_constraint["id"] = constraint_id;
    new_ord_constraint["res_id"] = res_id;
    new_ord_constraint["order"] = order;
    new_ord_constraint["score"] = score;
    new_ord_constraint["other_rsc"] = target_res_id;
    new_ord_constraint["temp"] = true;
    if (order == "before") {
      new_ord_constraint["before"] = true;
      new_ord_constraint["first"] = target_res_id;
      new_ord_constraint["then"] = res_id;
      new_ord_constraint["first-action"] = target_action;
      new_ord_constraint["then-action"] = res_action;
    }
    else {
      new_ord_constraint["first"] = res_id;
      new_ord_constraint["then"] = target_res_id;
      new_ord_constraint["first-action"] = res_action;
      new_ord_constraint["then-action"] = target_action;
    }

    $.each(this.content, function(key, value) {
      if (value.name == res_id) {
	if (value.get("ordering_constraints")) {
	  var res_ord_constraints = {};
	  $.each(value.get("ordering_constraints"), function (key, value) {
	    if (res_id in res_ord_constraints)
	      res_ord_constraints[res_id].push(value);
	    else res_ord_constraints[res_id] = [value];
	  });
	  if (res_id in res_ord_constraints) {
	    res_ord_constraints[res_id].push(new_ord_constraint);
	  }
	  else {
	    res_ord_constraints[res_id] = [new_ord_constraint];
	  }
	  value.set("ordering_constraints", res_ord_constraints[res_id]);
	} else {
	  value.set("ordering_constraints", [new_ord_constraint]);
	}
      }
    });
  },

  add_ord_set_constraint: function(res_id_list, constraint_id, set_id) {
    var new_constraint = {};
    new_constraint['id'] = constraint_id;
    new_constraint['sets'] = [{
      'id': set_id,
      'resources': res_id_list,
    }];

    $.each(this.content, function(key, value) {
      if (res_id_list.indexOf(value.name) != -1) {
        if (value.get('ordering_set_constraints')) {
          var res_id = value.name;
          var res_ord_set_constraints = {};
          $.each(value.get('ordering_set_constraints'), function(key, value) {
            if (res_id in res_ord_set_constraints) {
              res_ord_set_constraints[res_id].push(value);
            }
            else {
              res_ord_set_constraints[res_id] = [value]
            }
          });
          if (res_id in res_ord_set_constraints) {
            res_ord_set_constraints[res_id].push(new_constraint);
          }
          else {
            res_ord_set_constraints[res_id] = [new_constraint];
          }
          value.set('ordering_set_constraints', res_ord_set_constraints[res_id]);
        }
        else {
          value.set('ordering_set_constraints', [new_constraint]);
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
      $.each(
        [
          "location_constraints",
          "ordering_constraints", "ordering_set_constraints",
          "colocation_constraints",
        ],
        function(constraint_key, constraint_type) {
          if (value[constraint_type]) {
            value.set(
              constraint_type,
              $.grep(
                value[constraint_type],
                function(value2, key) { return value2.id != constraint_id; }
              )
            );
          }
        }
      );
    });
  },


  update: function(data) {
    var self = this;
    var resources = {};
    var resource_clone_nodes = {};
    var ord_con = {}
    var loc_con = {}
    var col_con = {}
    var ord_set_con = {}
    var res_loc_constraints = {};
    var res_ord_constraints = {};
    var res_ord_set_constraints = {};
    var res_col_constraints = {};
    var group_list = [];
    self.parentIDMapping = {};
    $.each(data, function(key, value) {
      if (value["resources"]) {
	$.each(value["resources"], function(k2, v2) {
	  // Use resource_clone_nodes to handle resources with multiple ndoes
	  if (!(v2["id"] in resource_clone_nodes)) {
	    resource_clone_nodes[v2["id"]] = [];
	  }

	  if ("nodes" in v2) {
	    $.each(v2["nodes"], function(node_num, node_name) {
	      if ($.inArray(node_name, resource_clone_nodes[v2["id"]]) == -1) {
		resource_clone_nodes[v2["id"]].push(node_name);
	      }
	    });
	  }

	  resources[v2["id"]] = v2;
	  if ((msg_id = v2["group"]) || (msg_id = v2["clone_id"]) || (msg_id = v2["ms_id"])) {
	    self.parentIDMapping[msg_id] = self.parentIDMapping[msg_id] || [];
	    if (self.parentIDMapping[msg_id].indexOf(v2["id"]) == -1) {
	      self.parentIDMapping[msg_id].push(v2["id"]);
	    }
	  }
	  resources[v2["id"]]["nodes"] = resource_clone_nodes[v2["id"]].sort();
	});
      }

      if (value["groups"]) {
        $.each(value["groups"], function(index, group) {
          if (group_list.indexOf(group) == -1) {
            group_list.push(group);
          }
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
	    if (value["sets"]) {
	      ord_set_con[value["id"]] = value;
	    }
	    else {
	      ord_con[value["id"]] = value;
	    }
	  });
	}
	if (value["constraints"]["rsc_colocation"]) {
	  $.each(value["constraints"]["rsc_colocation"], function (key, value) {
	    col_con[value["id"]] = value;
	  });
	}
      }
    });

    update_resource_form_groups($("#new_resource_agent"), group_list.sort());

    $.each(loc_con, function (key, value) {
      res_loc_constraints[value["rsc"]] = res_loc_constraints[value["rsc"]] || [];
      res_loc_constraints[value["rsc"]].push(value);
      if (self.parentIDMapping[value["rsc"]]) {
	$.each(self.parentIDMapping[value["rsc"]], function(index,map) {
	  res_loc_constraints[map] = res_loc_constraints[map] || [];
	  res_loc_constraints[map].push(value);
	});
      }
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

      if (self.parentIDMapping[value["first"]]) {
	$.each(self.parentIDMapping[value["first"]], function(index,map) {
	  res_ord_constraints[map] = res_ord_constraints[map] || [];
	  res_ord_constraints[map].push(first);
	});
      }
      if (self.parentIDMapping[value["then"]]) {
	$.each(self.parentIDMapping[value["then"]], function(index,map) {
	  res_ord_constraints[map] = res_ord_constraints[map] || [];
	  res_ord_constraints[map].push(then);
	});
      }
    });

    $.each(ord_set_con, function(key, set_con) {
      $.each(set_con["sets"], function(key, set) {
        $.each(set["resources"], function(key, resource) {
          res_ord_set_constraints[resource] = res_ord_set_constraints[resource] || [];
          if (res_ord_set_constraints[resource].indexOf(set_con) != -1) {
            return;
          }
          res_ord_set_constraints[resource].push(set_con);
          if (self.parentIDMapping[resource]) {
            $.each(self.parentIDMapping[resource], function(index, map) {
              res_ord_set_constraints[map] = res_ord_set_constraints[map] || [];
              res_ord_set_constraints[map].push(set_con);
            });
          }
        })
      })
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

      if (self.parentIDMapping[value["rsc"]]) {
	$.each(self.parentIDMapping[value["rsc"]], function(index,map) {
	  res_col_constraints[map] = res_col_constraints[map] || [];
	  res_col_constraints[map].push(first);
	});
      }
      if (self.parentIDMapping[value["with-rsc"]]) {
	$.each(self.parentIDMapping[value["with-rsc"]], function(index,map) {
	  res_col_constraints[map] = res_col_constraints[map] || [];
	  res_col_constraints[map].push(second);
	});
      }
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
	  resource.set("disabled", value["disabled"]);
	  resource.set("nodes", value["nodes"]);
	  resource.set("node_list", value["nodes"].join(", "));
	  resource.set("group", value["group"]);
	  resource.set("clone", value["clone"]);
	  resource.set("ms", value["ms"]);
	  resource.set("failed", value["failed"]);
	  resource.set("orphaned", value["orphaned"]);
	  resource.set("options", value["options"]);
	  resource.set("location_constraints", res_loc_constraints[value["id"]]);
	  resource.set("ordering_constraints", res_ord_constraints[value["id"]]);
	  resource.set("ordering_set_constraints", res_ord_set_constraints[value["id"]]);
	  resource.set("colocation_constraints", res_col_constraints[value["id"]]);
	  resource.set("stonith", value["stonith"]);
	  resource.set("meta_attr", value["meta_attr"]);
	}
      });
      if (found == false) {
	resource = Pcs.Resource.create({
	  name: value["id"],
	  agentname: value["agentname"],
	  active: value["active"],
	  disabled: value["disabled"],
	  nodes: value["nodes"],
	  node_list: value["nodes"].join(", "),
	  group: value["group"],
	  clone: value["clone"],
	  ms: value["ms"],
	  failed: value["failed"],
	  orphaned: value["orphaned"],
	  options: value["options"],
	  location_constraints: res_loc_constraints[value["id"]],
	  ordering_constraints: res_ord_constraints[value["id"]],
	  ordering_set_constraints: res_ord_set_constraints[value["id"]],
	  colocation_constraints: res_col_constraints[value["id"]],
	  stonith: value["stonith"],
	  meta_attr: value["meta_attr"]
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
	if (Pcs.cur_page == "resources") { self.set("cur_resource_res", resource);}
	if (Pcs.cur_page == "stonith") { self.set("cur_resource_stonith", resource);}
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

    // Set defaults if not resources are set
    if (self.content && self.content.length > 0) {
      if (self.cur_resource_ston == null) {
	for (var i=0; i< self.content.length; i++) {
	  if (self.content[i].stonith) {
	    self.set("cur_resource_ston", self.content[i]);
	    self.content[i].set("cur_resource",true);
	    break;
	  }
	}
      }
      if (self.cur_resource_res == null) {
	for (var i=0; i< self.content.length; i++) {
	  if (!self.content[i].stonith) {
	    self.set("cur_resource_res", self.content[i]);
	    self.content[i].set("cur_resource",true);
	    break;
	  }
	}
      }
      if (self.cur_resource == null) {
	if (Pcs.cur_page == "resources") {
	  self.set("cur_resource", self.cur_resource_res);
	}
	if (Pcs.cur_page == "stonith") {
	  self.set("cur_resource", self.cur_resource_ston);
	}
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
  cur_node_attr: function () {
    var ret_val = [];
    var nc = this;
    $.each(this.content, function(node, value) {
      if ("node_attrs" in value && nc.cur_node && value["node_attrs"]) {
        if (nc.cur_node.name in value["node_attrs"]) {
          ret_val = ret_val.concat(value["node_attrs"][nc.cur_node.name]);
        }
        return false;
      }
    });
    return ret_val;
  }.property("cur_node", "content.@each.node_attrs"),
  cur_node_fence_levels: function () {
    var ret_val = [];
    var nc = this;
    $.each(this.content, function(node, value) {
      if ("fence_levels" in value && nc.cur_node && value["fence_levels"]) {
        if (nc.cur_node.name in value["fence_levels"]) {
          ret_val = ret_val.concat(value["fence_levels"][nc.cur_node.name]);
        }
        return false;
      }
    });
    return ret_val;
  }.property("cur_node", "content.@each.fence_levels"),
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

      if (data[node_id]["notauthorized"] == "true" || data[node_id]["notoken"] == true) {
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
	  node.set("corosync_enabled", data[node_id]["corosync_enabled"]);
	  node.set("pacemaker_daemon", data[node_id]["pacemaker"]);
	  node.set("pacemaker_enabled", data[node_id]["pacemaker_enabled"]);
	  node.set("pcsd_enabled", data[node_id]["pcsd_enabled"]);
	  node.set("corosync", corosync_online);
	  node.set("pacemaker", pacemaker_online);
	  node.set("pacemaker_standby", pacemaker_standby);
	  node.set("cur_node",false);
	  node.set("running_resources", Pcs.getResourcesFromID($.unique(resources_on_nodes[node_id].sort().reverse())));
	  node.set("location_constraints", lc_on_nodes[node_id].sort());
	  node.set("uptime", data[node_id]["uptime"]);
	  node.set("node_id", data[node_id]["node_id"]);
	  node.set("node_attrs", data[node_id]["node_attr"]);
	  node.set("fence_levels", data[node_id]["fence_levels"]);
	}
      });

      if (found == false) {
	var node = Pcs.Clusternode.create({
	  name: node_id,
	  authorized:  authorized,
	  up: up_status,
	  pcsd: pcsd_daemon && authorized,
	  corosync_daemon: data[node_id]["corosync"],
	  corosync_enabled: data[node_id]["corosync_enabled"],
	  pacemaker_daemon: data[node_id]["pacemaker"],
	  pacemaker_enabled: data[node_id]["pacemaker_enabled"],
	  pcsd_enabled: data[node_id]["pcsd_enabled"],
	  corosync: corosync_online,
	  pacemaker: pacemaker_online,
	  pacemaker_standby: pacemaker_standby,
	  cur_node: false,
	  running_resources: Pcs.getResourcesFromID($.unique(resources_on_nodes[node_id].sort().reverse())),
	  location_constraints: lc_on_nodes[node_id].sort(),
	  uptime: data[node_id]["uptime"],
	  node_id: data[node_id]["node_id"],
	  node_attrs: data[node_id]["node_attr"],
	  fence_levels: data[node_id]["fence_levels"]
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

    nodesToRemove = [];
    $.each(self.content, function (key, node) {
      found = false;
      $.each(nodes, function (k,v) {
	if (v == node.name)
	  found = true;
      });
      if (!found) {
	nodesToRemove.push(node);
      }
    });

    $.each(nodesToRemove, function(k,v) {
      self.content.removeObject(v);
    });
  }
});

function myUpdate() {
  Pcs.update();
//  window.setTimeout(myUpdate,4000);
}

Pcs.update(true);
