var pcs_timeout = 6000;

function curResource() {
  return Pcs.resourcesController.cur_resource.name
}

function curStonith() {
  return Pcs.resourcesController.cur_resource.name
}

function configure_menu_show(item) {
  $("#configure-"+item).show();
  $(".configure-"+item).addClass("selected");
}

function menu_show(item,show) {
  if (show) {
    $("#" + item + "_menu").addClass("active");
  } else {
    $("#" + item + "_menu").removeClass("active");
  }
}

// Changes the visible change when another menu is selected
// If item is specified, we load that item as well
// If initial is set to true, we load default (first item) on other pages
// and load the default item on the specified page if item is set
function select_menu(menu, item, initial) {
  if (menu == "NODES") {
    Pcs.set('cur_page',"nodes")
    if (item)
      Pcs.nodesController.load_node($('[nodeID='+item+']'));
    menu_show("node", true);
  } else {
    menu_show("node", false);
  }

  if (menu == "RESOURCES") {
    Pcs.set('cur_page',"resources")
    Pcs.resourcesController.set("cur_resource",Pcs.resourcesController.cur_resource_res);
    if (item)
      Pcs.resourcesController.load_resource($('[nodeID="'+item+'"]'));
    menu_show("resource", true);
  } else {
    menu_show("resource", false);
  }

  if (menu == "FENCE DEVICES") {
    Pcs.set('cur_page',"stonith");
    Pcs.resourcesController.set("cur_resource",Pcs.resourcesController.cur_resource_ston);
    if (item)
      Pcs.resourcesController.load_stonith($('[nodeID='+item+']'));
    menu_show("stonith", true);
  } else {
    menu_show("stonith", false);
  }

  if (menu == "MANAGE") {
    Pcs.set('cur_page',"manage");
    menu_show("cluster", true);
  } else {
    menu_show("cluster", false);
  }

  if (menu == "CONFIGURE") {
    Pcs.set('cur_page',"configure");
    menu_show("configure", true);
  } else {
    menu_show("configure", false);
  }

  if (menu == "WIZARDS") {
    Pcs.set('cur_page',"wizards");
    menu_show("wizards", true);
  } else {
    menu_show("wizards", false);
  }
}

function create_group() {
  var num_nodes = 0;
  var node_names = "";
  $("#resource_list :checked").parent().parent().each(function (index,element) {
    num_nodes++;
    node_names += element.getAttribute("nodeID") + " "
  });

  if (num_nodes == 0) {
    alert("You must select at least one resource to add to a group");
  } else {
    $("#resources_to_add_to_group").val(node_names);
    $("#add_group").dialog({title: 'Create Group',
      modal: true, resizable: false, 
      buttons: {
	"Create Group": function() {
	  var data = $('#add_group > form').serialize();
	  var url = get_cluster_remote_url() + "add_group";
	  $.ajax({
	    type: "POST",
	    url: url,
	    data: data,
	    success: function() {
	      Pcs.update();
	      $("#add_group").dialog("close");
	    },
	    error: function() {
	      alert("Unable to create group");
	      $("#add_group").dialog("close");
	    }
	  });
	},
      Cancel: function() {
	$(this).dialog("close");
      }}
    });
  }
}

// If update is set to true we update the resource instead of create it
// if stonith is set to true we update/create a stonith agent
function create_resource(form, update, stonith) {
  dataString = $(form).serialize();
  url = get_cluster_remote_url() + $(form).attr("action");
  var name;
  if (stonith)
    name = "fence device";
    else name = "resource"
  $.ajax({
    type: "POST",
    url: url,
    data: dataString,
    success: function() {
      if (!update) {
	if (stonith)
	  $('#add_stonith').dialog('close');
	else
	  $('#add_resource').dialog('close');
      }
      Pcs.update();
    },
    error: function() {
      if (update)
	alert("Unable to update " + name);
      else
	alert("Unable to add " + name);
    }
  });
}

// Don't allow spaces in input fields
function disable_spaces(item) {
  myitem = item;
  $(item).find("input").on("keydown", function (e) {
    return e.which !== 32;
  });
}

function load_resource_form(item, ra, stonith) {
  data = { "new": true, resourcename: ra};
  if (!stonith)
    command = "resource_metadata";
  else
    command = "fence_device_metadata";
  
  item.load(get_cluster_remote_url() + command, data, function() {
    disable_spaces(this);
  });
}

function verify_remove(rem_type, error_message, ok_message, title_message, resource_id, post_location) {
  if (!error_message)
    error_message = "You must select at least one resource.";
  if (!ok_message)
    ok_message = "Remove resource(s)";
  if (!title_message)
    title_message = "Resource Removal";
  if (!post_location)
    post_location = "/resourcerm";

  var buttonOpts = {}
  buttonOpts[ok_message] = function() {
    if (resource_id) {
      if (rem_type == "cluster")
	remove_cluster([resource_id]);
      else
	remove_resource([resource_id]);
    } else {
      ids = []
      $.each($('#'+rem_type+'_list :checked'), function (i,e) {
	ids.push($(e).parent().parent().attr("nodeID"))
      });
      if (ids.length > 0) {
	if (rem_type == "cluster")
	  remove_cluster(ids);
	else
	  remove_resource(ids);
      }
    }
    $(this).dialog("close");
//    if (rem_type == "cluster")
 //     document.location.reload();
  };
  buttonOpts["Cancel"] = function() {
    $(this).dialog("close");
  };

  var list_of_nodes = "<ul>";
  var nodes_to_remove = 0;

  if (resource_id) {
    list_of_nodes += "<li>" + resource_id +"</li>";
    nodes_to_remove++;
  } else {
    $("#"+rem_type+"_list :checked").each(function (index,element) {
      if ($(element).is(':visible')) {
	list_of_nodes += "<li>" + $(element).parent().parent().attr("nodeID")+"</li>";
	nodes_to_remove++;
      }
    });
  }
  list_of_nodes += "</ul>";
  if (nodes_to_remove != 0) {
    $("#resource_to_remove").html(list_of_nodes);
    $("#verify_remove").dialog({title: title_message,
      modal: true, resizable: false,
      buttons: buttonOpts
    });
  } else {
    alert(error_message);
  }
}

function remote_node_update() {
  node = $('#node_info_header_title_name').first().text();
  $.ajax({
    type: 'GET',
    url: '/remote/status_all',
    timeout: pcs_timeout,
    success: function (data) {

      data = jQuery.parseJSON(data);
      node_data = data[node];

      local_node_update(node, data);
//      window.setTimeout(remote_node_update,pcs_timeout);
    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
//      window.setTimeout(remote_node_update, 60000);
    }
  });
}

function local_node_update(node, data) {
  node_data = data[node];

  for (var n in data) {
    if (data[n].pacemaker_online && (jQuery.inArray(n, data[n].pacemaker_online) != -1)) {
	setNodeStatus(n, true);
    } else {
    	setNodeStatus(n,false);
    }
  }
}

function disable_checkbox_clicks() {
  $('.node_list_check input[type=checkbox]').click(function(e) {
    e.stopPropagation();
  });
}

// TODO: REMOVE
function resource_list_update() {
  resource = $('#node_info_header_title_name').first().text();

  // If resources are checked we need to keep them selected on refresh
  var checkedResources = new Array();
  $('.node_list_check :checked').each(function(i,e) {
    checkedResources.push($(e).attr("res_id"));
  });

  $.ajax({
    type: 'GET',
    url: '/resource_list/'+resource,
    timeout: pcs_timeout,
    success: function(data) {
      try {
	newdata = $(data);
      } catch(err) {
	newdata = $("");
      }
      newdata.find('.node_list_check input[type=checkbox]').each( function(i,e) {
	var res_id = $(e).attr("res_id");
	for (var i=checkedResources.length-1; i>= 0; --i) {
	  if (checkedResources[i] == res_id) {
	    $(e).prop("checked",true);
	  }
	}
      });
      
      $("#node_list").html(newdata);
      disable_checkbox_clicks();
      window.setTimeout(resource_list_update, pcs_timeout);
    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
      window.setTimeout(resource_list_update, 60000);
    }
  });
}

// TODO: REMOVE
function resource_update() {
  resource = $('#node_info_header_title_name').first().text();
  $.ajax({
    type: 'GET',
    url: '/remote/resource_status?resource='+resource,
    timeout: pcs_timeout,
    success: function(data) {
      data = jQuery.parseJSON(data);
      $("#cur_res_loc").html(data.location);
      $("#res_status").html(data.status);
      if (data.status == "Running") {
	setStatus($("#res_status"), 0);
      } else {
	setStatus($("#res_status"), 1);
      }
      window.setTimeout(resource_update, pcs_timeout);
    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
      window.setTimeout(resource_update, 60000);
    }
  });
}

// Set the status of a service
// 0 = Running (green)
// 1 = Stopped (red)
// 2 = Unknown (gray)
function setStatus(item, status, message) {
  if (status == 0) {
    item.removeClass();
    item.addClass('status');
  } else if (status == 1) {
    item.removeClass();
    item.addClass('status-offline');
  } else if (status == 2) {
    item.removeClass();
    item.addClass('status-unknown');
  }

  if (typeof message !== 'undefined')
    item.html(message)
}

// Set the node in the node list blue or red depending on
// whether pacemaker is connected or not
function setNodeStatus(node, running) {
  if (running) {
    $('.node_name:contains("'+node+'")').css('color','');
  } else {
    $('.node_name:contains("'+node+'")').css('color','red');
  }
}
  

function fade_in_out(id) {
  $(id).fadeTo(1000, 0.01, function() {
    $(id).fadeTo(1000, 1);
  });
}

function setup_node_links() {
  Ember.debug("Setup node links");
  $("#node_start").click(function() {
    node = $("#node_info_header_title_name").text();
    fade_in_out("#node_start");
    $.post('/remote/cluster_start',{"name": $.trim(node)});
  });
  $("#node_stop").click(function() {
    node = $("#node_info_header_title_name").text();
    fade_in_out("#node_stop");
    $.post('/remote/cluster_stop', {"name": $.trim(node)});
  });
  $("#node_restart").click(function() {
    node = $("#node_info_header_title_name").text();
    fade_in_out("#node_restart");
    $.post('/remote/node_restart', {"name": $.trim(node)});
  });
  $("#node_standby").click(function() {
    node = $("#node_info_header_title_name").text();
    fade_in_out("#node_standby");
    $.post('/remote/node_standby', {"node": $.trim(node)});
  });
  $("#node_unstandby").click(function() {
    node = $("#node_info_header_title_name").text();
    fade_in_out("#node_unstandby");
    $.post('/remote/node_unstandby', {"node": $.trim(node)});
  });
}

function setup_resource_links(link_type) {
  Ember.debug("Setup resource links");
  $("#resource_delete_link").click(function () {
    verify_remove("resource", null, "Remove resource", "Resource Removal", curResource(), "/resourcerm");
  });
  $("#stonith_delete_link").click(function () {
    verify_remove("stonith", null, "Remove fence device", "Fence Device Removal", curStonith(), "/fencerm")
  });
  $("#resource_stop_link").click(function () {
    fade_in_out("#resource_stop_link");
    $.post(get_cluster_remote_url() + 'resource_stop',"resource="+curResource());
  });
  $("#resource_start_link").click(function () {
    fade_in_out("#resource_start_link");
    $.post(get_cluster_remote_url() + 'resource_start',"resource="+curResource());
  });
  $("#resource_move_link").click(function () {
    alert("Not Yet Implemented");
  });
  $("#resource_history_link").click(function () {
    alert("Not Yet Implemented");
  });
}

function checkExistingNode() {
  var node = "";
  $('input[name="node-name"]').each(function(i,e) {
    node = e.value;
  });

  $.ajax({
    type: 'POST',
    url: '/remote/check_gui_status',
    data: {"nodes": node},
    timeout: pcs_timeout,
    success: function (data) {
      mydata = jQuery.parseJSON(data);
      update_existing_cluster_dialog(mydata);

    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
      alert("ERROR: Unable to contact server");
    }
  });
}

function checkClusterNodes() {
  var nodes = [];
  $('input[name^="node-"]').each(function(i,e) {
    if (e.value != "") {
      nodes.push(e.value)
    }
  });

  $.ajax({
    type: 'POST',
    url: '/remote/check_gui_status',
    data: {"nodes": nodes.join(",")},
    timeout: pcs_timeout,
    success: function (data) {
      mydata = jQuery.parseJSON(data);
      update_create_cluster_dialog(mydata);

    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
      alert("ERROR: Unable to contact server");
    }
  });
}

function add_existing_dialog() {
  var buttonOpts = {}

  buttonOpts["Add Existing"] = function() {
          checkExistingNode();
  };

  buttonOpts["Cancel"] = function() {
    $(this).dialog("close");
  };

  // If you hit enter it triggers the first button: Add Existing
  $('#add_existing_cluster').keypress(function(e) {
    if (e.keyCode == $.ui.keyCode.ENTER) {
      $(this).parent().find("button:eq(0)").trigger("click");
      return false;
    }
  });

  $("#add_existing_cluster").dialog({title: 'Add Existing Cluster',
    modal: false, resizable: false,
    width: 'auto',
    buttons: buttonOpts
  });
}

function update_existing_cluster_dialog(data) {
  for (var i in data) {
    if (data[i] == "Online") {
      $('#add_existing_cluster_form').submit();
      return;
    }
    break;
  }
  $('#unable_to_connect_error_msg_ae').show();
}

function update_create_cluster_dialog(nodes) {
  var keys = [];
  for (var i in nodes) {
    if (nodes.hasOwnProperty(i)) {
      keys.push(i);
    }
  }

  var bad_nodes = 0;
  var good_nodes = 0;
  var cluster_name = $('input[name^="clustername"]').val()
    $('#create_new_cluster input[name^="node-"]').each(function() {
      if ($(this).val() == "") {
	$(this).parent().prev().css("background-color", "");
	return;
      }
      for (var i = 0; i < keys.length; i++) {
	if ($(this).val() == keys[i]) {
	  if (nodes[keys[i]] != "Online") {
	    $(this).parent().prev().css("background-color", "red");
	    bad_nodes++;
	  } else {
	    $(this).parent().prev().css("background-color", "");
	    good_nodes++;
	  }
	}
      }
    });
  if (bad_nodes != 0) {
    $("#unable_to_connect_error_msg").show();
  } else {
    $("#unable_to_connect_error_msg").hide();
  }

  if (good_nodes == 0 && bad_nodes == 0) {
    $("#at_least_one_node_error_msg").show();
  } else {
    $("#at_least_one_node_error_msg").hide();
  }

  if (cluster_name == "") {
    $("#bad_cluster_name_error_msg").show();
  } else {
    $("#bad_cluster_name_error_msg").hide();
  }


  if (good_nodes != 0 && bad_nodes == 0 && cluster_name != "") {
    $('#create_new_cluster_form').submit();
  }

}

function create_cluster_dialog() {
  var buttonOpts = [{
    text: "Create Cluster",
    id: "create_cluster_submit_btn",
    click: function() {
      checkClusterNodes();
    }
  },
  {
    text: "Cancel",
    id: "create_cluster_cancel_btn",
    click: function() {
      $(this).dialog("close");
    }
  }]

  $("#create_new_cluster").dialog({title: 'Create Cluster',
    modal: false, resizable: false,
    width: 'auto',
    buttons: buttonOpts
  });
}

function create_cluster_add_nodes() {
  node_list = $("#create_new_cluster_form tr").has("input[name^='node-']");;
  cur_num_nodes = node_list.length;
  first_node = node_list.eq(0);
  new_node = first_node.clone();
  $("input",new_node).attr("name", "node-"+(cur_num_nodes+1));
  $("input",new_node).val("");
  $("td", new_node).first().text("Node " + (cur_num_nodes+1)+ ":");
  new_node.insertAfter(node_list.last());
  if (node_list.length == 7)
    $("#create_new_cluster_form tr").has("input[name^='node-']").last().next().remove();
}

function show_hide_constraints(element) {
  //$(element).parent().siblings().each (function(index,element) {
  $(element).parent().nextUntil(".stop").toggle();
  $(element).children("span, p").toggle();
}

function show_hide_constraint_tables(element) {
  $(element).siblings().hide();
  $("#add_constraint_" + $(element).val()).show();
}

function hover_over(o) {
  $(o).find('td').last().css('display','');
  $(o).addClass("node_selected");
}

function hover_out(o) {
  $(o).find('td').last().css('display','none');
  $(o).removeClass("node_selected");
}

function load_row(node_row, ac, cur_elem, containing_elem, also_set){
  hover_over(node_row);
  $(node_row).siblings().each(function(key,sib) {
    hover_out(sib);
  });
  var self = ac;
  $(containing_elem).fadeTo(500, .01,function() {
    node_name = $(node_row).attr("nodeID");
    $.each(self.content, function(key, node) {
      if (node.name == node_name) {
	self.set(cur_elem,node);
	node.set(cur_elem, true);
	if (also_set)
	  self.set(also_set, node);
      } else {
	if (self.cur_resource_ston &&
	    self.cur_resource_ston.name == node.name)
	  self.content[key].set(cur_elem,true);
	else if (self.cur_resource_res &&
		 self.cur_resource_res.name == node.name)
	  self.content[key].set(cur_elem,true);
	else
	  self.content[key].set(cur_elem,false);
      }
    });
    Pcs.resourcesController.update_cur_resource();
    $(containing_elem).fadeTo(500,1);
  });
}

function load_agent_form(resource_row, stonith) {
  resource_name = $(resource_row).attr("nodeID");
  var url;
  var form;
  var data = {resource: resource_name};
  if (stonith) {
    form = $("#stonith_agent_form");
    url = '/managec/' + Pcs.cluster_name + '/fence_device_form';
  } else {
    form = $("#resource_agent_form");
    url = '/managec/' + Pcs.cluster_name + '/resource_form';
  }

  form.empty();

  $.ajax({
    type: 'GET',
    url: url,
    data: data,
    timeout: pcs_timeout,
    success: function (data) {
      form.html(data);
      disable_spaces(form);
      myform = form;
    }
  });
}

function show_loading_screen() {
  $("#loading_screen_progress_bar").progressbar({ value: 100});
  $("#loading_screen").dialog({
    modal: true,
    title: "Loading",
    height: 100,
    width: 250,
    hide: {
      effect: 'fade',
      direction: 'down',
      speed: 750
    }
  });
}

function hide_loading_screen() {
  $("#loading_screen").dialog('close');
}

function remove_cluster(ids) {
  for (var i=0; i<ids.length; i++) {
    var cluster = ids[i];
    var clusterid_name = "clusterid-"+ids[i];
    var data = {}
    data[clusterid_name] = true;
    $.ajax({
      type: 'POST',
      url: '/manage/removecluster',
      data: data,
      timeout: pcs_timeout,
      success: function () {
      	location.reload();
      },
      error: function (xhr, status, error) {
	alert("Unable to remove resource: " + res + " ("+error+")");
      }
    });
  }
}

function remove_resource(ids) {
  var data = {};
  var res = "";
  for (var i=0; i<ids.length; i++) {
    res += ids[i] + ", ";
    var resid_name = "resid-" + ids[i];
    data[resid_name] = true;
  }
  res = res.slice(0,-2);

  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'remove_resource',
    data: data,
    timeout: pcs_timeout,
    success: function () {
      Pcs.update();
    },
    error: function (xhr, status, error) {
      alert("Unable to remove resources: " + res + " ("+error+")");
    }
  });
}

function add_constraint(parent_id, c_type) {
  var data = {};
  data["res_id"] = Pcs.resourcesController.cur_resource.name
  data["node_id"] = $(parent_id + " input[name='node_id']").val();
  data["score"] = $(parent_id + " input[name='score']").val();
  data["stickyness"] = $(parent_id + " input[name='stickyness']").val();
  data["target_res_id"] = $(parent_id + " input[name='target_res_id']").val();
  data["order"] = $(parent_id + " select[name='order']").val();
  data["colocation_type"] = $(parent_id + " select[name='colocate']").val();
  data["c_type"] = c_type;
  fade_in_out($(parent_id));

  $.ajax({ 
    type: 'POST',
    url: get_cluster_remote_url() + 'add_constraint_remote',
    data: data,
    timeout: pcs_timeout,
    success: function() {
      $(parent_id + " input").val("");
      if (c_type == "loc")
	Pcs.resourcesController.add_loc_constraint(data["res_id"],"temp-cons-id",
						   data["node_id"], data["score"],
						   data["sticky"]);
      else if (c_type == "ord")
	Pcs.resourcesController.add_ord_constraint(data["res_id"],"temp-cons-id",
						   data["target_res_id"],
						   data["order"], data["score"]);
      else if (c_type == "col")
	Pcs.resourcesController.add_col_constraint(data["res_id"],"temp-cons-id",
						   data["target_res_id"],
						   data["colocation_type"], data["score"]);
      Pcs.update();
    },
    error: function (xhr, status, error) {
      alert("Unable to add constraints: ("+error+")");
    }
  });
}
  
function remove_constraint(id) {
  fade_in_out($("[constraint_id='"+id+"']").parent());
  $.ajax({
    type: 'POST',
    url: '/resource_cmd/rm_constraint',
    data: {"constraint_id": id},
    timeout: pcs_timeout,
    success: function (data) {
      Pcs.resourcesController.remove_constraint(id);
    },
    error: function (xhr, status, error) {
      alert("Error removing constraint: ("+error+")");
    }
  });
}

function show_cluster_info(row) {
  cluster_name = $(row).attr("nodeID");

  $("#node_sub_info").children().each(function (i, val) {
    if ($(val).attr("id") == ("cluster_info_" + cluster_name))
      $(val).show();
    else
      $(val).hide();
  });

}

function update_cluster_settings(form) {
  var data = form.serialize();
  $('html, body, form, :input, :submit').css("cursor","wait");
  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'update_cluster_settings',
    data: data,
    timeout: pcs_timeout,
    success: function() {
      window.location.reload();
    },
    error: function (xhr, status, error) {
      alert("Error updating configuration: ("+error+")");
      $('html, body, form, :input, :submit').css("cursor","auto");
    }
  });
}

// Pull currently managed cluster name out of URL
function get_cluster_name() {
  cluster_name = location.pathname.match("/managec/(.*)/");
  if (cluster_name && cluster_name.length >= 2) {
    Ember.debug("Cluster Name: " + cluster_name[1]);
    cluster_name = cluster_name[1];
    return cluster_name;
  }
  Ember.debug("Cluster Name is 'null'");
  cluster_name = null;
  return cluster_name;
}

function get_cluster_remote_url() {
    return '/managec/' + Pcs.cluster_name + "/";
}

function checkBoxToggle(cb) {
  cbs = $(cb).closest("tr").next().find(".node_list_check input[type=checkbox]")
  if ($(cb).prop('checked'))
    cbs.prop('checked',true);
  else
    cbs.prop('checked',false);
}

function loadWizard(item) {
  wizard_name = $(item).val();
  data = {wizard: wizard_name};

  $("#wizard_location").load(
   get_cluster_remote_url() + 'get_wizard',
   data);
}

function wizard_submit(form) {
  data = $(form).serialize();
  $("#wizard_location").load(
    get_cluster_remote_url() + 'wizard_submit',
    data);
}
