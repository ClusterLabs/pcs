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
  permissions_page: function() {
    if (this.cur_page == "permissions") return "display: table-row;";
    else return "display: none;";
  }.property("cur_page"),
  wizards_page: function() {
    if (this.cur_page == "wizards") return "display: table-row;";
    else return "display: none;";
  }.property("cur_page"),

  getResourcesFromID: function(resources) {
    var retArray = [];
    var resource_map = Pcs.resourcesContainer.get('resource_map');
    $.each(resources, function(_, resource_id) {
      if (resource_id in resource_map && !resource_map[resource_id].get('stonith')) {
        retArray.pushObject(resource_map[resource_id]);
      }
    });
    return retArray;
  },
  updater: null,

  update: function() {
    Pcs.get('updater').update();
  },

  _update: function(first_run) {
    if (window.location.pathname.lastIndexOf('/manage', 0) !== 0) {
      return;
    }
    if (first_run) {
      show_loading_screen();
    }
    var self = Pcs;
    var cluster_name = self.cluster_name;
    if (cluster_name == null) {
      if (location.pathname.indexOf("/manage") != 0) {
        return;
      }
      Ember.debug("Empty Cluster Name");
      $.ajax({
        url: "/clusters_overview",
        dataType: "json",
        timeout: 20000,
        success: function(data) {
          Pcs.clusterController.update(data);
          if (Pcs.clusterController.get('cur_cluster')) {
            Pcs.clusterController.update_cur_cluster(Pcs.clusterController.get('cur_cluster').get('name'));
          }
          if (data["not_current_data"]) {
            self.update();
          }
          hide_loading_screen();
        },
        error: function(jqhxr,b,c) {
          if (jqhxr.responseText) {
            try {
              var obj = $.parseJSON(jqhxr.responseText);
              if (obj.notauthorized == "true") {
                location.reload();
              }
            } catch(e) {
              console.log("Error: Unable to parse json for clusters_overview");
            }
          }
          hide_loading_screen();
        },
        complete: function() {
          Pcs.get('updater').update_finished();
        }
      });
      return;
    }
    $.ajax({
      url: "cluster_status",
      dataType: "json",
      success: function(data) {
        Pcs.resourcesContainer.update(data);
        Pcs.nodesController.update(data);
        Pcs.settingsController.update(data);
        Pcs.aclsController.update(data);
        Pcs.set("cluster_settings",data.cluster_settings);
        Pcs.set('need_ring1_address', false);
        Pcs.set('is_cman_with_udpu_transport', false);
        if (data['need_ring1_address']) {
          Pcs.set('need_ring1_address', true);
        }
        if (data['is_cman_with_udpu_transport']) {
          Pcs.set('is_cman_with_udpu_transport', true);
        }
        var fence_change = false;
        var resource_change = false;
        Ember.run.next(function () {
          var self = Pcs.resourcesContainer;
          var cur_fence = self.get('cur_fence');
          var cur_resource = self.get('cur_resource');
          var resource_map = self.get('resource_map');
          if (first_run) {
            setup_node_links();
            Pcs.nodesController.load_node($('#node_list_row').find('.node_selected').first(),true);
            Pcs.aclsController.load_role($('#acls_list_row').find('.node_selected').first(), true);
            if (self.get("fence_id_to_load")) {
              cur_fence = self.get_resource_by_id(self.get("fence_id_to_load"));
              fence_change = true;
            }
            if (self.get("resource_id_to_load")) {
              cur_resource = self.get_resource_by_id(self.get("resource_id_to_load"));
              resource_change = true;
            }
          }

          if (cur_fence && cur_fence.get('id') in resource_map) {
            if (resource_map[cur_fence.get('id')] !== cur_fence) {
              cur_fence = resource_map[cur_fence.get('id')];
            }
          } else {
            if (self.get('fence_list').length > 0) {
              cur_fence = self.get('fence_list')[0];
            } else {
              cur_fence = null;
            }
            fence_change = true;
          }

          if (cur_resource && cur_resource.get('id') in resource_map) {
            if (resource_map[cur_resource.get('id')] !== cur_resource) {
              cur_resource = resource_map[cur_resource.get('id')];
            }
          } else {
            if (self.get('resource_list').length > 0) {
              cur_resource = self.get('resource_list')[0];
            } else {
              cur_resource = null;
            }
            resource_change = true;
          }

          self.set('cur_fence', cur_fence);
          self.set('cur_resource', cur_resource);

          Ember.run.scheduleOnce('afterRender', Pcs, function () {
            if (self.get('cur_fence')) {
              if (fence_change)
                tree_view_onclick(self.get('cur_fence').get('id'), true);
              else
                tree_view_select(self.get('cur_fence').get('id'));
            }
            if (self.get('cur_resource')) {
              if (resource_change)
                tree_view_onclick(self.get('cur_resource').get('id'), true);
              else
                tree_view_select(self.get('cur_resource').get('id'));
            }
            Pcs.selectedNodeController.reset();
            disable_checkbox_clicks();
          });
        });
      },
      error: function(jqhxr,b,c) {
        try {
          var obj = $.parseJSON(jqhxr.responseText);
          if (obj.notauthorized == "true") {
            location.reload();
          }
        } catch(e) {
          console.log("Error: Unable to parse json for cluster_status")
        }
      },
      complete: function() {
        hide_loading_screen();
        Pcs.get('updater').update_finished();
      }
    });
  }
});

Pcs.UtilizationTableComponent = Ember.Component.extend({
  entity: null,
  type: "node", // node or resource
  form_id: Ember.computed("type", function() {
    return "new_" + this.get("type") + "_utilization";
  }),
  show_content: false,
  utilization: [],
  last_count: 0,
  util_count: function() {
    var l = 0;
    if (this.utilization) {
      l = this.utilization.length;
    }
    //this is needed for not showing/hiding table on each update
    if (this.last_count != l) {
      if (l > 0) {
        this.set('show_content', true);
      } else {
        this.set('show_content', false);
      }
    }
    this.set("last_count", l);
    return l;
  }.property("utilization"),
  actions: {
    toggleBody: function() {
      this.toggleProperty('show_content');
    },
    remove: function(name) {
      set_utilization(this.type, this.entity.get("id"), name, "");
    },
    add: function(form_id) {
      var id = "#" + form_id;
      var name = $(id + " input[name='new_utilization_name']").val();
      if (name == "") {
        return;
      }
      var value = $(id + " input[name='new_utilization_value']").val().trim();
      if (!is_integer(value)) {
        alert("Value of utilization attribute has to be integer.");
        return;
      }
      set_utilization(
        this.type,
        this.entity.get("id"),
        name,
        value
      );
      fade_in_out($(id));
      $(id + " input").val("");
    }
  }
});

Pcs.Updater = Ember.Object.extend({
  timeout: 20000,
  first_run: true,
  async: true,
  autostart: true,
  started: false,
  in_progress: false,
  waiting: false,
  update_function: null,
  update_target: null,
  timer: null,

  start: function() {
    this.set('started', true);
    this.update();
  },

  stop: function() {
    this.set('started', false);
    this.cancel_timer();
  },

  cancel_timer: function() {
    var self = this;
    var timer = self.get('timer');
    if (timer) {
      self.set('timer', null);
      Ember.run.cancel(timer);
    }
  },

  update: function() {
    var self = this;
    if (!self.get('update_function')) {
      console.log('No update_function defined!');
      return;
    }
    self.cancel_timer();
    self.set('waiting', false);
    if (self.get('in_progress')) {
      self.set('waiting', true);
    } else {
      self.set('in_progress', true);
      self.get('update_function').apply(self.get('update_target'), [self.get('first_run')]);
      self.set('first_run', false);
      if (!self.get('async')) {
        self.update_finished();
      }
    }
  },

  update_finished: function() {
    var self = this;
    if (self.get('waiting')) {
      Ember.run.next(self, self.update);
    } else if (self.get('started')) {
      self.set('timer', Ember.run.later(self, self.update, self.get('timeout')));
    }
    self.set('in_progress', false);
  },

  init: function() {
    var self = this;
    if (!self.get('update_target')) {
      self.set('update_target', self);
    }
    if (self.get('autostart')) {
      self.start();
    }
  }
});

Pcs.resourcesContainer = Ember.Object.create({
  resource_map: {},
  top_level_resource_map: {},
  fence_list: [],
  resource_list: [],
  resource_id_to_load: null,
  fence_id_to_load: null,
  cur_resource: null,
  cur_fence: null,
  constraints: {},
  group_list: [],
  data_version: null,

  get_resource_by_id: function(resource_id) {
    var resource_map = this.get('resource_map');
    if (resource_id in resource_map)
      return resource_map[resource_id];
    return null;
  },

  get_family_list: function(parent) {
    var family = [];
    family.push(parent);
    switch (parent["class_type"]) {
      case "group":
        $.each(parent.get('members'), function(index, member) {
          family = family.concat(Pcs.resourcesContainer.get_family_list(member));
        });
        break;
      case "clone":
      case "master":
        family = family.concat(Pcs.resourcesContainer.get_family_list(parent.get('member')));
        break;
    }
    return family;
  },

  get_constraints: function(cons) {
    var ord_con = {};
    var loc_con = {};
    var col_con = {};
    var ord_set_con = {};
    var res_loc_constraints = {};
    var res_ord_constraints = {};
    var res_ord_set_constraints = {};
    var res_col_constraints = {};
    if (cons) {
      if (cons["rsc_location"]) {
        $.each(cons["rsc_location"], function (key, value) {
          loc_con[value["id"]] = value;
        });
      }
      if (cons["rsc_order"]) {
        $.each(cons["rsc_order"], function (key, value) {
          if (value["sets"]) {
            ord_set_con[value["id"]] = value;
          }
          else {
            ord_con[value["id"]] = value;
          }
        });
      }
      if (cons["rsc_colocation"]) {
        $.each(cons["rsc_colocation"], function (key, value) {
          col_con[value["id"]] = value;
        });
      }
    }

    $.each(loc_con, function (key, value) {
      res_loc_constraints[value["rsc"]] = res_loc_constraints[value["rsc"]] || [];
      res_loc_constraints[value["rsc"]].push(value);
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

    $.each(ord_set_con, function(key, set_con) {
      $.each(set_con["sets"], function(key, set) {
        $.each(set["resources"], function(key, resource) {
          res_ord_set_constraints[resource] = res_ord_set_constraints[resource] || [];
          if (res_ord_set_constraints[resource].indexOf(set_con) != -1) {
            return;
          }
          res_ord_set_constraints[resource].push(set_con);
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
    });
    return {
      "location_constraints": res_loc_constraints,
      "ordering_constraints": res_ord_constraints,
      "ordering_set_constraints": res_ord_set_constraints,
      "colocation_constraints": res_col_constraints
    };
  },

  update_meta_attr: function(resource_id, attr, value) {
    value = typeof value !== 'undefined' ? value.trim() : "";
    var data = {
      res_id: resource_id,
      key: attr,
      value: value
    };

    $.ajax({
      type: 'POST',
      url: get_cluster_remote_url() + 'add_meta_attr_remote',
      data: data,
      timeout: pcs_timeout,
      error: function (xhr, status, error) {
        alert(
          "Unable to update meta attribute '" + attr + "' "
          + ajax_simple_error(xhr, status, error)
        );
      },
      complete: function() {
        Pcs.update();
      }
    });
  },

  enable_resource: function(resource_id) {
    $.ajax({
      type: 'POST',
      url: get_cluster_remote_url() + 'resource_start',
      data: {resource: resource_id},
      timeout: pcs_timeout,
      success: function(data) {
        if (data['error']) {
          alert("Unable to enable resource '" + resource_id + "': (" + data['stderr'] + ")");
        }
      },
      error: function(xhr, status, error) {
        alert(
          "Unable to enable resource '" + resource_id + "' "
          + ajax_simple_error(xhr, status, error)
        );
      },
      complete: function() {
        Pcs.update();
      }
    });
  },

  disable_resource: function(resource_id) {
    $.ajax({
      type: 'POST',
      url: get_cluster_remote_url() + 'resource_stop',
      data: {resource: resource_id},
      timeout: pcs_timeout,
      success: function(data) {
        if (data['error']) {
          alert("Unable to disable resource '" + resource_id + "': (" + data['stderr'] + ")");
        }
      },
      error: function(xhr, status, error) {
        alert(
          "Unable to disable resource '" + resource_id + "' "
          + ajax_simple_error(xhr, status, error)
        );
      },
      complete: function() {
        Pcs.update();
      }
    });
  },

  delete_resources: function(type, resource_list) {
    var self = this;
    var list = self.get(type);
    $.each(resource_list, function(i, resource) {
      list.removeObject(resource);
    });
  },

  delete_unused_resources: function(type, used_map) {
    var self = this;
    var to_delete = [];
    var list = self.get(type);
    $.each(list, function(i, resource) {
      if (!(resource.get('id') in used_map)) {
        to_delete.push(resource);
      }
    });
    self.delete_resources(type, to_delete);
  },

  update: function(data) {
    var self = this;
    self.set('group_list', data['groups']);
    self.set("data_version", data['status_version']);
    var resources = data["resource_list"];
    var resource_obj = null;
    var resource_id;
    var new_resource_map = {};
    var top_resource_map = {};
    $.each(resources, function(index, resource) {
      var update = false;
      resource_id = resource.id;
      if (resource_id in self.get('top_level_resource_map')) {
        resource_obj = self.get('top_level_resource_map')[resource_id];
        resource_obj.update(resource_obj, resource);
        update = true;
      } else {
        switch (resource["class_type"]) {
          case "primitive":
            resource_obj = Pcs.PrimitiveObj.create(resource);
            break;
          case "group":
            resource_obj = Pcs.GroupObj.create(resource);
            break;
          case "clone":
            resource_obj = Pcs.CloneObj.create(resource);
            break;
          case "master":
            resource_obj = Pcs.MasterSlaveObj.create(resource);
            break;
        }
      }

      top_resource_map[resource_obj.get('id')] = resource_obj;
      $.each(self.get_family_list(resource_obj), function(index, resource) {
        new_resource_map[resource.get('id')] = resource;
      });

      if (!update) {
        if (resource_obj.stonith) {
          self.get('fence_list').pushObject(resource_obj);
        } else {
          self.get('resource_list').pushObject(resource_obj);
        }
      }
    });

    self.set('top_level_resource_map', top_resource_map);
    self.set('resource_map', new_resource_map);

    self.delete_unused_resources("fence_list", top_resource_map);
    self.delete_unused_resources("resource_list", top_resource_map);

    var constraints = self.get_constraints(data["constraints"]);
    self.set('constraints', constraints);
    var resource_map = self.get('resource_map');
    update_resource_form_groups($("#new_resource_agent"), self.get('group_list').sort());
    $.each(constraints, function(const_type, cons) {
      $.each(resource_map, function(resource_id, resource_obj) {
        if (resource_id in cons) {
          resource_obj.set(const_type, cons[resource_id]);
        } else {
          resource_obj.set(const_type, []);
        }
      });
    });
    $.each(resource_map, function(resource_id, resource_obj) {
      resource_obj.set('group_list', self.get('group_list'));
    });
    self.set('resource_list', Ember.copy(self.get('resource_list')).sort(function(a,b){return a.get('id').localeCompare(b.get('id'))}));
    self.set('fence_list', Ember.copy(self.get('fence_list')).sort(function(a,b){return a.get('id').localeCompare(b.get('id'))}));
  }
});

Pcs.resourcesContainer.reopen({
  is_version_1: function() {
    return (this.get("data_version") == '1');
  }.property('data_version')
});

Pcs.ResourceObj = Ember.Object.extend({
  id: null,
  _id: Ember.computed.alias('id'),
  name: Ember.computed.alias('id'),
  parent: null,
  meta_attr: [],
  meta_attributes: Ember.computed.alias('meta_attr'),
  disabled: false,
  error_list: [],
  warning_list: [],
  group_list: [],
  get_group_id: function() {
    var self = this;
    var p = self.get('parent');
    if (p && p.get('class_type') == 'group') {
      return p.get('id');
    }
    return null;
  }.property('parent'),
  group_selector: function() {
    var self = this;
    var cur_group = self.get('get_group_id');
    var html = '<select>\n<option value="">None</option>\n';
    $.each(self.get('group_list'), function(_, group) {
      html += '<option value="' + group + '"';
      if (cur_group === group) {
        html += 'selected';
      }
      html += '>' + group + '</option>\n';
    });
    html += '</select><input type="button" value="Change group" onclick="resource_change_group(curResource(), $(this).prev().prop(\'value\'));">';
    return html;
  }.property('group_list', 'get_group_id'),
  status: "unknown",
  class_type: null, // property to determine type of the resource
  resource_type: function() { // this property is just for displaying resource type in GUI
    var t = this.get("class_type");
    return t[0].toUpperCase() + t.slice(1);
  }.property("class_type"),
  res_type: Ember.computed.alias('resource_type'),
  status_icon: function() {
    var icon_class = get_status_icon_class(this.get("status_val"));
    return "<div style=\"float:left;margin-right:6px;height:16px;\" class=\"" + icon_class + " sprites\"></div>";
  }.property("status_val"),
  status_val: function() {
    var status_val = get_status_value(this.get('status'));
    if (this.get('warning_list').length && status_val != get_status_value('disabled'))
      status_val = get_status_value("warning");
    if (this.get('error_list').length)
      status_val = get_status_value("error");
    if ((get_status_value(this.get('status')) - status_val) < 0) {
      return get_status_value(this.get('status'));
    } else {
      return status_val;
    }
  }.property('status', 'error_list.@each.message', 'warning_list.@each.message'),
  status_color: function() {
    return get_status_color(this.get("status_val"));
  }.property("status_val"),
  status_style: function() {
    var color = get_status_color(this.get("status_val"));
    return "color: " + color + ((color != "green")? "; font-weight: bold;" : "");
  }.property("status_val"),
  show_status: function() {
    return '<span style="' + this.get('status_style') + '">' + this.get('status') + '</span>';
  }.property("status_style", "disabled"),
  status_class: function() {
    var show = ((Pcs.clusterController.get("show_all_resources"))? "" : "hidden ");
    return ((this.get("status_val") == get_status_value("ok") || this.status == "disabled") ? show + "default-hidden" : "");
  }.property("status_val"),
  status_class_fence: function() {
    var show = ((Pcs.clusterController.get("show_all_fence"))? "" : "hidden ");
    return ((this.get("status_val") == get_status_value("ok")) ? show + "default-hidden" : "");
  }.property("status", "status_val"),
  tooltip: function() {
    var self = this;
    var out = "";
    if (self.error_list.length > 0) {
      out += "<span style='color: red;  font-weight: bold;'>ERRORS:</span><br>\n";
      out += get_formated_html_list(self.error_list);
    }
    if (self.warning_list.length > 0) {
      out += "<span style='color: orange;  font-weight: bold;'>WARNINGS:</span><br>\n";
      out += get_formated_html_list(self.warning_list);
    }
    return out;
  }.property("error_list.@each", "warning_list.@each"),
  span_class: function() {
    switch (this.get("status_val")) {
      case get_status_value("failed"):
        return "status-error";
      case get_status_value("warning"):
      case get_status_value("disabled"):
        return "status-warning";
      default:
        return "";
    }
  }.property("status_val"),

  location_constraints: [],
  ordering_constraints: [],
  ordering_set_constraints: [],
  colocation_constraints: [],

  get_map: function() {
    var self = this;
    var map = {};
    map[self.get('id')] = self;
    return map;
  },

  get_full_warning_list: function() {
    var self = this;
    var warning_list = [];
    $.each(self.get_map(), function(name, resource){
      warning_list = warning_list.concat(resource.get('warning_list'));
    });
    return warning_list;
  },

  get_full_error_list: function() {
    var self = this;
    var error_list = [];
    $.each(self.get_map(), function(name, resource){
      error_list = error_list.concat(resource.get('error_list'));
    });
    return error_list;
  },

  update: function(self, data) {
    $.each(data, function(k, v) {
      self.set(k, v);
    });
    self.refresh();
  }
});

Pcs.ResourceStatusObj = Ember.Object.extend({
  id: null,
  resource_agent: null,
  managed: false,
  failed: false,
  role: null,
  active: false,
  orphaned: false,
  failure_ignored: false,
  nodes_running_on: 0,
  pending: null,
  node: null
});

Pcs.ResourceOperationObj = Ember.Object.extend({
  call_id: 0,
  crm_debug_origin: null,
  crm_feature_set: null,
  exec_time: 0,
  exit_reason: null,
  id: null,
  interval: 0,
  last_rc_change: 0,
  last_run: 0,
  on_node: null,
  op_digest: null,
  operation: null,
  operation_key: null,
  op_force_restart: null,
  op_restart_digest: null,
  op_status: 0,
  queue_time: 0,
  rc_code: 0,
  transition_key: null,
  transition_magic: null
});

Pcs.PrimitiveObj = Pcs.ResourceObj.extend({
  agentname: null,
  provider: null,
  type: null,
  stonith: false,
  instance_attr: [],
  instance_status: [],
  operations: [],
  utilization: [],
  resource_type: Ember.computed.alias('agentname'),
  is_primitive: true,
  nodes_running_on: function() {
    var self = this;
    var nodes = [];
    var node = null;
    $.each(self.get('instance_status'), function(index, status) {
      node = status.get('node');
      if (node)
        nodes.push(node.name);
    });
    return nodes;
  }.property('instance_status.@each.node'),
  is_in_group: function() {
    var self = this;
    var p = self.get('parent');
    return (p && p.get('class_type') == 'group');
  }.property('parent'),
  nodes_running_on_string: function() {
    return this.get('nodes_running_on').join(', ');
  }.property('nodes_running_on'),

  refresh: function() {
    var self = this;
    var stat = self.get("crm_status");
    var new_stat = [];
    $.each(stat, function(i,v) {
      new_stat.push(Pcs.ResourceStatusObj.create(v));
    });
    var ops = self.get("operations");
    var new_ops = [];
    $.each(ops, function(i,v) {
      new_ops.push(Pcs.ResourceOperationObj.create(v));
    });
    self.set("instance_status", new_stat);
    self.set("operations", new_ops);
    self.set("crm_status", null);
  },

  init: function() {
    this.refresh();
  }
});

Pcs.GroupObj = Pcs.ResourceObj.extend({
  members: [],
  is_group: true,
  children: Ember.computed.alias('members'),

  init: function() {
    this.refresh();
  },

  get_map: function() {
    var self = this;
    var map = self._super();
    var members = self.get('members');
    $.each(members, function(i, m){
      $.extend(map, m.get_map());
    });
    return map;
  },

  refresh: function() {
    var self = this;
    var members = self.get("members");
    var member;
    var new_members = [];
    $.each(members, function(i,v) {
      member = Pcs.PrimitiveObj.create(v);
      member.set('parent', self);
      new_members.push(member);
    });
    self.set("members", new_members);
  }
});

Pcs.MultiInstanceObj = Pcs.ResourceObj.extend({
  member: null,
  children: function() {
    return [this.get('member')];
  }.property('member'),
  unique: false,
  managed: false,
  failed: false,
  failure_ignored: false,
  is_multi_instance: true,

  get_map: function() {
    var self = this;
    var map = self._super();
    $.extend(map, self.get('member').get_map());
    return map;
  },

  init: function() {
    this.refresh();
  },

  refresh: function() {
    var self = this;
    var member = self.get("member");
    var new_member = null;
    switch (member.class_type) {
      case "primitive":
        new_member = Pcs.PrimitiveObj.create(member);
        break;
      case "group":
        new_member = Pcs.GroupObj.create(member);
    }
    new_member.set('parent', self);
    self.set("member", new_member);
  }
});

Pcs.CloneObj = Pcs.MultiInstanceObj.extend({
  is_clone: true
});

Pcs.MasterSlaveObj = Pcs.MultiInstanceObj.extend({
  masters: [],
  slaves: [],
  resource_type: 'Master/Slave'
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
    if (
      window.location.pathname == "/manage"
      ||
      window.location.pathname == "/manage/"
    ) {
      select_menu("MANAGE");
    }
    else if (
      window.location.pathname == "/permissions"
      ||
      window.location.pathname == "/permissions/"
    ) {
      select_menu("PERMISSIONS");
      Ember.run.scheduleOnce('afterRender', this, permissions_load_all);
    }
    else {
      select_menu("NODES");
    }
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
    Pcs.resourcesContainer.set('fence_id_to_load', params.stonith_id);
    return params.stonith_id;
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
    Pcs.resourcesContainer.set('resource_id_to_load', params.resource_id);
    return params.resource_id;
  }
});

Pcs.Setting = Ember.Object.extend({
  name: null,
  value: null,
  type: null
});

Pcs.Clusternode = Ember.Object.extend({
  name: null,
  id: Ember.computed.alias("name"),
  status: null,
  status_unknown: function() {
    return this.get('status') == "unknown";
  }.property("status"),
  status_val: function() {
    var status_val = get_status_value(this.get('status'));
    if (this.get('warning_list').length)
      status_val = get_status_value("warning");
    if (this.get('error_list').length)
      status_val = get_status_value("error");
    if ((get_status_value(this.get('status')) - status_val) < 0) {
      return get_status_value(this.get('status'));
    } else {
      return status_val;
    }
  }.property('status', 'error_list.@each.message', 'warning_list.@each.message'),
  status_style: function() {
    var color = get_status_color(this.get("status_val"));
    return "color: " + color + ((color != "green")? "; font-weight: bold;" : "");
  }.property("status_val"),
  status_class: function() {
    var show = ((Pcs.clusterController.get("show_all_nodes"))? "" : "hidden ");
    return (
      (this.get("status_val") == get_status_value("ok") || this.status == "standby" ||
      this.status == "maintenance")
        ? show + "default-hidden" : ""
    );
  }.property("status_val"),
  status_icon: function() {
    var icon_class = get_status_icon_class(this.get("status_val"));
    return "<div style=\"float:left;margin-right:6px;\" class=\"" + icon_class + " sprites\"></div>";
  }.property("status_val"),
  error_list: [],
  warning_list: [],
  tooltip: function() {
    var self = this;
    var out = "";
    if (self.error_list && self.error_list.length > 0) {
      out += "<span style='color: red;  font-weight: bold;'>ERRORS:</span><br>\n";
      out += get_formated_html_list(self.error_list);
    }
    if (self.warning_list && self.warning_list.length > 0) {
      out += "<span style='color: orange;  font-weight: bold;'>WARNINGS:</span><br>\n";
      out += get_formated_html_list(self.warning_list);
    }
    return out;
  }.property("error_list", "warning_list"),
  quorum: null,
  quorum_show: function() {
    if (this.status == "unknown" || this.status == "offline" || this.get('quorum') === null) {
      return '<span style="color: orange; font-weight: bold;">unknown</span>';
    } else if (this.quorum) {
      return '<span style="color: green;">YES</span>';
    } else {
      return '<span style="color: red; font-weight: bold;">NO</span>';
    }
  }.property("status", "quorum"),
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
    if (this.up && !this.get('pacemaker_maintenance')) {
      return "";
    } else {
      if (this.get("pacemaker_standby") || this.get("pacemaker_maintenance"))
        return "color: #ff6600";
      else
        return "color:red";
    }
  }.property("up","pacemaker_standby","pacemaker_maintenance"),
  pacemaker_standby: null,
  pacemaker_maintenance: Ember.computed.alias('is_in_maintenance'),
  corosync_enabled: null,
  pacemaker_enabled: null,
  pcsd_enabled: null,
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
  location_constraints: null,
  node_attrs: [],
  utilization: [],
  is_in_maintenance: function() {
    var self = this;
    var result = false;
    $.each(self.get('node_attrs'), function(_, attr) {
      if (attr["name"] == "maintenance") {
        result = is_cib_true(attr["value"]);
        return false; // break foreach loop
      }
    });
    return result;
  }.property('node_attrs'),
  fence_levels: [],
  pcsd: null,
  corosync_daemon: null,
  pacemaker_daemon: null,
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

Pcs.Cluster = Ember.Object.extend({
  name: null,
  url_link: function(){return get_cluster_remote_url(this.name) + "main";}.property("name"),
  input_name: function(){return "clusterid-" + this.name;}.property("name"),
  div_id: function(){return "cluster_info_" + this.name}.property("name"),
  status: "unknown",
  status_unknown: function() {
    return this.status == "unknown";
  }.property("status"),
  forbidden: function() {
    var out = false;
    $.each(this.get("error_list"), function(key, value) {
      if ("forbidden" == value["type"]) {
        out = true;
      }
    });
    return out;
  }.property("error_list"),
  status_icon: function() {
    var icon_class = get_status_icon_class(get_status_value(this.get('status')));
    return "<div style=\"float:left;margin-right:6px;\" class=\"" + icon_class + " sprites\"></div>";
  }.property("status"),
  quorum_show: function() {
    if (this.get('status') == "unknown") {
      return "<span style='color:orange'>(quorate unknown)</span>"
    } else if (!this.get('quorate')) {
      return "<span style='color: red'>(doesn't have quorum)</span>"
    } else {
      return ""
    }
  }.property("status", "quorate"),
  nodes: [],
  nodes_failed: 0,
  resource_list: [],
  resources_failed: 0,
  fence_list: [],
  fence_failed: 0,
  error_list: [],
  warning_list: [],
  need_reauth: false,
  quorate: false,

  get_num_of_failed: function(type) {
    var num = 0;
    $.each(this.get(type), function(key, value) {
      if (value.get("status_val") < get_status_value("ok") &&
        value.status != "disabled" && value.status != "standby" &&
        value.status != "maintenance"
      ) {
        num++;
      }
    });
    return num;
  },

  status_sort: function(a,b) {
    if (a.get("status_val") == b.get("status_val"))
      return ((a.status == b.status) ? a.get('name').localeCompare(b.get('name')) : ((a.status > b.status) ? 1 : -1));
    return status_comparator(a.status, b.status)
  },

  add_resources: function(data) {
    var self = this;
    var resources = [];
    var fence = [];
    var resource_obj;
    $.each(data, function (index, resource) {
      switch (resource["class_type"]) {
        case "primitive":
          resource_obj = Pcs.PrimitiveObj.create(resource);
          break;
        case "group":
          resource_obj = Pcs.GroupObj.create(resource);
          break;
        case "clone":
          resource_obj = Pcs.CloneObj.create(resource);
          break;
        case "master":
          resource_obj = Pcs.MasterSlaveObj.create(resource);
          break;
      }

      var url_link = get_cluster_remote_url(self.get('name')) + "main#/" +
        (resource_obj.get('stonith') ? "fencedevices/" : "resources/") +
        resource_obj.get('id');
      resource_obj.set('url_link', url_link);

      resource_obj.set('warning_list', resource_obj.get_full_warning_list());
      resource_obj.set('error_list', resource_obj.get_full_error_list());

      if (resource_obj.stonith) {
        fence.pushObject(resource_obj);
      } else {
        resources.pushObject(resource_obj);
      }
    });
    resources.sort(self.status_sort);
    fence.sort(self.status_sort);
    self.set('fence_list', fence);
    self.set('resource_list', resources);
  },

  add_nodes: function(data, node_attrs) {
    var self = this;
    self.set("need_reauth", false);
    var nodes = [];
    var node;
    $.each(data, function(key, val) {
      if (val["warning_list"]) {
        $.each(val["warning_list"], function (key, value) {
          if (self.get('need_reauth'))
            return false;
          if (typeof(value.type) !== 'undefined' && value.type == "nodes_not_authorized") {
            self.set("need_reauth", true);
          }
        });
      }

      var attrs = [];
      if (node_attrs && val["name"] in node_attrs) {
        attrs = node_attrs[val["name"]];
      }

      node = Pcs.Clusternode.create({
        name: val["name"],
        url_link: get_cluster_remote_url(self.name) + "main#/nodes/" + val["name"],
        status: val["status"],
        quorum: val["quorum"],
        error_list: val["error_list"],
        warning_list: val["warning_list"]
      });
      node.set("node_attrs", attrs);
      if (node.get("is_in_maintenance") && node.get('status_val') > get_status_value("maintenance")) {
        node.set("status", "maintenance");
      }
      nodes.push(node);
    });
    nodes.sort(self.status_sort);
    self.set("nodes", nodes);
  }
});

Pcs.clusterController = Ember.Object.create({
  cluster_list: Ember.ArrayController.create({
    content: Ember.A(),
    sortProperties: ['name'],
    sortAscending: true
  }),
  cur_cluster: null,
  show_all_nodes: false,
  show_all_resources: false,
  show_all_fence: false,
  num_ok: 0,
  num_error: 0,
  num_warning: 0,
  num_unknown: 0,

  update_cur_cluster: function(cluster_name) {
    var self = this;
    $("#clusters_list div.arrow").hide();
    var selected_cluster = null;

    $.each(self.get('cluster_list').get('content'), function(key, cluster) {
      if (cluster.get("name") == cluster_name) {
        selected_cluster = cluster;
        return false;
      }
    });

    self.set('cur_cluster', selected_cluster);
    if (selected_cluster) {
      Ember.run.next(function() {
        $("#clusters_list tr[nodeID=" + cluster_name + "] div.arrow").show();
        correct_visibility_dashboard(self.get('cur_cluster'));
      });
    }
  },

  update: function(data) {
    var self = this;
    var clusters = data["cluster_list"];
    var cluster_name_list = [];
    self.set("num_ok", 0);
    self.set("num_error", 0);
    self.set("num_warning", 0);
    self.set("num_unknown", 0);

    $.each(clusters, function(key, value) {
      cluster_name_list.push(value["cluster_name"]);
      var found = false;
      var cluster = null;

      $.each(self.get('cluster_list').get('content'), function(key, pre_existing_cluster) {
        if (pre_existing_cluster && pre_existing_cluster.get('name') == value["cluster_name"]) {
          found = true;
          cluster = pre_existing_cluster;
          cluster.set("status", value["status"]);
          cluster.set("quorate",value["quorate"]);
          cluster.set("error_list",value["error_list"]);
          cluster.set("warning_list",value["warning_list"]);
        }
      });

      if (!found) {
        cluster = Pcs.Cluster.create({
          name: value["cluster_name"],
          status: value["status"],
          quorate: value["quorate"],
          error_list: value["error_list"],
          warning_list: value["warning_list"]
        });
      }

      cluster.add_nodes(value["node_list"], value["node_attr"]);
      cluster.add_resources(value["resource_list"]);
      cluster.set("nodes_failed", cluster.get_num_of_failed("nodes"));
      cluster.set("resources_failed", cluster.get_num_of_failed("resource_list"));
      cluster.set("fence_failed", cluster.get_num_of_failed("fence_list"));

      if (cluster.get('status') == "ok") {
        $.each(cluster.get('fence_list').concat(cluster.get('resource_list')), function(index, res) {
          if (res.get('warning_list').length > 0) {
            cluster.set("status", "warning");
            return false;
          }
        });
      }

      var nodes_to_auth = [];
      $.each(cluster.get('warning_list'), function(key, val){
        if (val.hasOwnProperty("type") && val.type == "nodes_not_authorized"){
          nodes_to_auth = nodes_to_auth.concat(val['node_list']);
        }
      });
      nodes_to_auth = $.unique(nodes_to_auth);

      if (cluster.get('need_reauth') || nodes_to_auth.length > 0) {
        cluster.get('warning_list').pushObject({
          message: "There are few authentication problems. To fix them, click <a href='#' onclick='auth_nodes_dialog(" + JSON.stringify(nodes_to_auth) + ", null, function() {fix_auth_of_cluster();})'>here</a>.",
          type: "nodes_not_authorized",
          node_list: self.nodes_to_auth
        });
      }

      if (!found) {
        self.get('cluster_list').pushObject(cluster);
      }

      if (cluster.get_num_of_failed("nodes") == cluster.nodes.length) {
        if (cluster.get('status') != "unknown")
          cluster.get('warning_list').pushObject({
            message: "Cluster is offline"
          });

        cluster.set("status", "unknown");
      }

      switch (get_status_value(cluster.get('status'))) {
        case get_status_value("ok"):
          self.incrementProperty('num_ok');
          break;
        case get_status_value("error"):
          self.incrementProperty('num_error');
          break;
        case get_status_value("warning"):
          self.incrementProperty('num_warning');
          break;
        default:
          self.incrementProperty('num_unknown');
          break;
      }
    });

    var to_remove = [];
    $.each(self.get('cluster_list').get('content'), function(key,val) {
      if (cluster_name_list.indexOf(val.get('name')) == -1) {
        to_remove.pushObject(val);
      }
    });

    $.each(to_remove, function(index, val) {
      self.get('cluster_list').removeObject(val);
    });
  }
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
    if (data["acls"]) {
      if (data["acls"]["group"]) {
        $.each(data["acls"]["group"], function (k2,v2) {
          my_groups[k2] = v2;
        });
      }
      if (data["acls"]["user"]) {
        $.each(data["acls"]["user"], function (k2,v2) {
          my_users[k2] = v2;
        });
      }
      if (data["acls"]["role"]) {
        $.each(data["acls"]["role"], function (k2,v2) {
          my_roles[k2] = v2;
        });
      }
    }
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
    if (data["cluster_settings"]) {
      $.each(data["cluster_settings"], function(k2, v2) {
        var setting = Pcs.Setting.create({
          name: k2,
          value: v2
        });
        self.pushObject(setting);
      });
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
  utilization_support: false,
  cur_node: null,
  cur_node_attr: function () {
    var nc = this;
    if (nc.get('cur_node')) {
      return nc.get('cur_node').get('node_attrs');
    }
    return [];
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
    var corosync_nodes_online = data["corosync_online"];
    var pacemaker_nodes_online = data["pacemaker_online"];
    var pacemaker_nodes_standby = data["pacemaker_standby"];

    var resources_on_nodes = {};
    var lc_on_nodes = {};
    $.each(data['node_list'], function(index, node) {
      nodes.push(node.name);

      resources_on_nodes[node.name] = [];
      $.each(Pcs.resourcesContainer.get('resource_map'), function(resource_id, resource_obj) {
        var nodes_running_on = resource_obj.get('nodes_running_on');
        if (nodes_running_on) {
          $.each(nodes_running_on, function(index, node_name) {
            if (node.name == node_name) {
              resources_on_nodes[node.name].push(resource_id);
            }
          });
        }
      });

      lc_on_nodes[node.name] = [];
      if (data["constraints"] && data["constraints"]["rsc_location"]) {
        $.each(data["constraints"]["rsc_location"], function(key, constraint) {
          if (constraint["node"] == node.name)
            lc_on_nodes[node.name].push(constraint)
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

    if (data["nodes_utilization"]) {
      self.set("utilization_support", true);
    } else {
      self.set("utilization_support", false);
    }

    $.each(data['node_list'], function(_, node_obj) {
      var node_id = node_obj.name;
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

      if (node_obj["status"] == 'unknown') {
        pcsd_daemon = false
      } else {
        pcsd_daemon = true
      }

      if (node_obj["notauthorized"] == "true" || node_obj["notoken"] == true) {
        authorized = false;
      } else {
        authorized = true;
      }

      if (node_obj["corosync"] && node_obj["pacemaker"] &&
        pacemaker_online && corosync_online) {
        up_status = true;
      } else {
        up_status = false;
      }

      var node_attr = [];
      if (data["node_attr"] && data["node_attr"][node_id]) {
        node_attr = data["node_attr"][node_id];
      }

      var utilization = [];
      if (data["nodes_utilization"] && data["nodes_utilization"][node_id]) {
        utilization = data["nodes_utilization"][node_id];
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
          node.set("corosync_daemon", node_obj["corosync"]);
          node.set("corosync_enabled", node_obj["corosync_enabled"]);
          node.set("pacemaker_daemon", node_obj["pacemaker"]);
          node.set("pacemaker_enabled", node_obj["pacemaker_enabled"]);
          node.set("pcsd_enabled", node_obj["pcsd_enabled"]);
          node.set("corosync", corosync_online);
          node.set("pacemaker", pacemaker_online);
          node.set("pacemaker_standby", pacemaker_standby);
          node.set("cur_node",false);
          node.set("running_resources", Pcs.getResourcesFromID($.unique(resources_on_nodes[node_id].sort().reverse())));
          node.set("location_constraints", lc_on_nodes[node_id].sort());
          node.set("uptime", node_obj["uptime"]);
          node.set("node_id", node_obj["id"]);
          node.set("node_attrs", node_attr);
          node.set("fence_levels", data["fence_levels"]);
          node.set("status", node_obj["status"]);
          node.set("utilization", utilization);
        }
      });

      if (found == false) {
        var node = Pcs.Clusternode.create({
          name: node_id,
          authorized:  authorized,
          up: up_status,
          pcsd: pcsd_daemon && authorized,
          corosync_daemon: node_obj["corosync"],
          corosync_enabled: node_obj["corosync_enabled"],
          pacemaker_daemon: node_obj["pacemaker"],
          pacemaker_enabled: node_obj["pacemaker_enabled"],
          pcsd_enabled: node_obj["pcsd_enabled"],
          corosync: corosync_online,
          pacemaker: pacemaker_online,
          pacemaker_standby: pacemaker_standby,
          cur_node: false,
          running_resources: Pcs.getResourcesFromID($.unique(resources_on_nodes[node_id].sort().reverse())),
          location_constraints: lc_on_nodes[node_id].sort(),
          uptime: node_obj["uptime"],
          node_id: node_obj["id"],
          node_attrs: node_attr,
          fence_levels: data["fence_levels"],
          status: node_obj["status"],
          utilization: utilization
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
    self.set('content', Ember.copy(self.get('content').sort(function(a,b){return a.get('name').localeCompare(b.get('name'))})));
  }
});

function myUpdate() {
  Pcs.update();
//  window.setTimeout(myUpdate,4000);
}

Pcs.set('updater', Pcs.Updater.create({
  timeout: 20000,
  update_function: Pcs._update,
  update_target: Pcs
}));
