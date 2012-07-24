Pcs = Ember.Application.create({
  mm: 'Andy',
  totalNodes: 0
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
    else
      return "Hi";
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
  }.property("cur_node")
});

myNode = Pcs.Clusternode.create({
  name: "FirstNode",
  up: true
});

Pcs.nodesController = Ember.ArrayController.create({
//  content: [{name: "tname"}],
  content: [],
  cur_node: null,
  init: function(){
    this._super();
    node = Pcs.Clusternode.create({
      name: "1 Node",
      up: true,
      cur_node:true,
      url: "window.location='/nodes/rh7-1'"
    });
    node2 = Pcs.Clusternode.create({
      name: "2 Node",
      up: false,
      cur_node:false,
      url: "window.location='/nodes/rh7-2'"
    });
    node3 = Pcs.Clusternode.create({
      name: "3 Node",
      up: true,
      cur_node:false,
      url: "window.location='/nodes/rh7-3'"
    });
//    this.pushObject(node);
 //   this.pushObject(node2);
   // this.pushObject(node3);
    //this.update();
  },

  load_node: function(node_row){
    hover_over(node_row);
    $(node_row).siblings().each(function(key,sib) {
      hover_out(sib);
    });
    node_name = $(node_row).attr("nodeID");
    var self = this;
    $.each(self.content, function(key, node) {
      if (node.name == node_name) {
	self.set("cur_node",node);
	node.set("cur_node", true);
      } else {
	self.content[key].set("cur_node",false);
      }
    });
  },

  update: function(){
    var self = this;
    $.ajax({
      url: "/remote/status_all",
      dataType: "json",
      success: function(data) {
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
	$.each(data, function(node, node_info) {
	  resources_on_nodes[node] = [];
	  if (node_info["resources"])
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
      }
    });
  }
});

function myUpdate() {
  Pcs.nodesController.update();
//  window.setTimeout(myUpdate,4000);
}

myUpdate();
