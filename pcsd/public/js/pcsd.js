var pcs_timeout = 30000;

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

  if (menu == "ACLS") {
    Pcs.set('cur_page',"acls");
    menu_show("acls", true);
  } else {
    menu_show("acls", false);
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
    if (element.getAttribute("nodeID")) {
      num_nodes++;
      node_names += element.getAttribute("nodeID") + " "
    }
  });

  if (num_nodes == 0) {
    alert("You must select at least one resource to add to a group");
  } else {
    $("#resources_to_add_to_group").val(node_names);
    $("#add_group").dialog({title: 'Create Group',
      modal: true, resizable: false, 
      buttons: {
	Cancel: function() {
	  $(this).dialog("close");
	},
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
	      reload_current_resource();
	    },
	    error: function (xhr, status, error) {
	      alert(xhr.responseText);
	      $("#add_group").dialog("close");
	    }
	  });
	}
      }
    });
  }
}

function add_node_dialog() {
  var buttonOpts = [
    {
      text: "Add Node",
      id: "add_node_submit_btn",
      click: function() {
        $("#add_node_submit_btn").button("option", "disabled", true);
        checkAddingNode();
      }
    },
    {
      text: "Cancel",
      click: function() {
        $(this).dialog("close");
      }
    }
  ];

  buttonOpts["Cancel"] = function() {
    $(this).dialog("close");
  };

  // If you hit enter it triggers the first button: Add Node
  $('#add_node').keypress(function(e) {
    if (e.keyCode == $.ui.keyCode.ENTER && !$("#add_node_submit_btn").button("option", "disabled")) {
        $("#add_node_submit_btn").trigger("click");
      return false;
    }
  });

  $('#add_node').dialog({
    title: 'Add Node',
    modal:true,
    resizable: false,
    width: 'auto',
    buttons: buttonOpts
  });
}

function checkAddingNode(){
  var nodeName = $("#add_node").children("form").find("[name='new_nodename']").val().trim();
  if (nodeName == "") {
    $("#add_node_submit_btn").button("option", "disabled", false);
    return false;
  }

  $.ajax({
    type: 'POST',
    url: '/remote/check_gui_status',
    data: {"nodes": nodeName},
    timeout: pcs_timeout,
    success: function (data) {
      var mydata = jQuery.parseJSON(data);
      if (mydata[nodeName] == "Unable to authenticate") {
        auth_nodes_dialog([nodeName], function(){$("#add_node_submit_btn").trigger("click");});
        $("#add_node_submit_btn").button("option", "disabled", false);
      } else if (mydata[nodeName] == "Offline") {
        alert("Unable to contact node '" + nodeName + "'");
        $("#add_node_submit_btn").button("option", "disabled", false);
      } else {
        create_node($("#add_node").children("form"));
      }
    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
      alert("ERROR: Unable to contact server");
      $("#add_node_submit_btn").button("option", "disabled", false);
    }
  });
}

function create_node(form) {
  var dataString = $(form).serialize();
  dataString += "&clustername=" + get_cluster_name();
  $.ajax({
    type: "POST",
    url: "/remote/add_node_to_cluster",
    data: dataString,
    success: function(returnValue) {
      $("#add_node_submit_btn").button("option", "disabled", false);
      $('#add_node').dialog('close');
      Pcs.update();
    },
    error: function(error) {
      alert(error.responseText);
      $("#add_node_submit_btn").button("option", "disabled", false);
    }
  });
}

// If update is set to true we update the resource instead of create it
// if stonith is set to true we update/create a stonith agent
function create_resource(form, update, stonith) {
  dataString = $(form).serialize();
  var resourceID = $(form).find("[name='name']").val(); 
  url = get_cluster_remote_url() + $(form).attr("action");
  var name;

  if (stonith)
    name = "fence device";
  else
    name = "resource"

  $.ajax({
    type: "POST",
    url: url,
    data: dataString,
    dataType: "json",
    success: function(returnValue) {
      $('input.apply_changes').show();
      if (returnValue["error"] == "true") {
	alert(returnValue["stderr"]);
      } else {
	Pcs.update();
	if (!update) {
	  if (stonith)
	    $('#add_stonith').dialog('close');
	  else
	    $('#add_resource').dialog('close');
	} else { 
	  reload_current_resource();
	}
      }
    },
    error: function() {
      if (update)
	alert("Unable to update " + name);
      else
	alert("Unable to add " + name);
      $('#apply_changes').fadeIn();
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

function update_resource_form_groups(form, group_list) {
  var select = $(form).find("select[name='resource_group']").first();
  if (select.length < 1) {
    return;
  }
  var selected = select.val();
  var selected_valid = false;
  var select_new = select.clone();
  select_new.empty();
  select_new.append('<option value="">None</options>');
  $.each(group_list, function(index, group) {
    select_new.append('<option value="' + group + '">' + group + '</options>');
    if (selected == group) {
      selected_valid = true;
    }
  });
  if (selected_valid) {
    select_new.val(selected);
  }
  select.replaceWith(select_new);
}

function verify_remove(remove_func, forceable, checklist_id, dialog_id, label, ok_text, title, remove_id) {
  var remove_id_list = new Array();
  if (remove_id) {
    remove_id_list = [remove_id];
  }
  else {
    remove_id_list = get_checked_ids_from_nodelist(checklist_id);
  }
  if (remove_id_list.length < 1) {
    alert("You must select at least one " + label + " to remove.");
    return;
  }

  var buttonOpts = [
    {
      text: ok_text,
      id: "verify_remove_submit_btn",
      click: function() {
        if (remove_id_list.length < 1) {
          return;
        }
        $("#verify_remove_submit_btn").button("option", "disabled", true);
        if (forceable) {
          force = $("#" + dialog_id + " :checked").length > 0
          remove_func(remove_id_list, force);
        }
        else {
          remove_func(remove_id_list);
        }
      }
    },
    {
      text: "Cancel",
      id: "verify_remove_cancel_btn",
      click: function() {
        $(this).dialog("destroy");
        if (forceable) {
          $("#" + dialog_id + " input[name=force]").attr("checked", false);
        }
      }
    }
  ];

  var name_list = "<ul>";
  $.each(remove_id_list, function(key, remid) {
    name_list += "<li>" + remid + "</li>";
  });
  name_list += "</ul>";
  $("#" + dialog_id + " .name_list").html(name_list);
  $("#" + dialog_id).dialog({
    title: title,
    modal: true,
    resizable: false,
    buttons: buttonOpts
  });
}

function verify_remove_clusters(cluster_id) {
  verify_remove(
    remove_cluster, false, "cluster_list", "dialog_verify_remove_clusters",
    "cluster", "Remove Cluster(s)", "Cluster Removal", cluster_id
  );
}

function verify_remove_nodes(node_id) {
  verify_remove(
    remove_nodes, false, "node_list", "dialog_verify_remove_nodes",
    "node", "Remove Node(s)", "Remove Node", node_id
  );
}

function verify_remove_resources(resource_id) {
  verify_remove(
    remove_resource, true, "resource_list", "dialog_verify_remove_resources",
    "resource", "Remove resource(s)", "Resurce Removal", resource_id
  );
}

function verify_remove_fence_devices(resource_id) {
  verify_remove(
    remove_resource, false, "stonith_list", "dialog_verify_remove_resources",
    "fence device", "Remove device(s)", "Fence Device Removal", resource_id
  );
}

function verify_remove_acl_roles(role_id) {
  verify_remove(
    remove_acl_roles, false, "acls_roles_list", "dialog_verify_remove_acl_roles",
    "ACL role", "Remove Role(s)", "Remove ACL Role", role_id
  );
}

function get_checked_ids_from_nodelist(nodelist_id) {
  var ids = new Array()
  $("#" + nodelist_id + " .node_list_check :checked").each(function (index, element) {
    if($(element).parent().parent().attr("nodeID")) {
      ids.push($(element).parent().parent().attr("nodeID"));
    }
  });
  return ids;
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
    node_stop($.trim(node), false);
  });
  $("#node_restart").click(function() {
    node = $("#node_info_header_title_name").text();
    fade_in_out("#node_restart");
    $.post('/remote/node_restart', {"name": $.trim(node)});
  });
  $("#node_standby").click(function() {
    node = $("#node_info_header_title_name").text();
    fade_in_out("#node_standby");
    $.post('/remote/node_standby', {"name": $.trim(node)});
  });
  $("#node_unstandby").click(function() {
    node = $("#node_info_header_title_name").text();
    fade_in_out("#node_unstandby");
    $.post('/remote/node_unstandby', {"name": $.trim(node)});
  });
}

function node_stop(node, force) {
  var data = {};
  data["name"] = node;
  if (force) {
    data["force"] = force;
  }
  $.ajax({
    type: 'POST',
    url: '/remote/cluster_stop',
    data: data,
    timeout: pcs_timeout,
    success: function() {
    },
    error: function(xhr, status, error) {
      if ((status == "timeout") || ($.trim(error) == "timeout")) {
        /*
         We are not interested in timeout because:
         - it can take minutes to stop a node (resources running on it have
           to be stopped/moved and we do not need to wait for that)
         - if pcs is not able to stop a node it returns an (forceable) error
           immediatelly
        */
        return;
      }
      var message = "Unable to stop node '" + node + "' (" + $.trim(error) + ")";
      message += "\n" + xhr.responseText;
      if (message.indexOf('--force') == -1) {
        alert(message);
      }
      else {
        message = message.replace(', use --force to override', '');
        if (confirm(message + "\n\nDo you want to force the operation?")) {
          node_stop(node, true);
        }
      }
    }
  });
}

function setup_resource_links(link_type) {
  Ember.debug("Setup resource links");
  $("#resource_delete_link").click(function () {
    verify_remove_resources(curResource());
  });
  $("#stonith_delete_link").click(function () {
    verify_remove_fence_devices(curStonith());
  });
  $("#resource_stop_link").click(function () {
    fade_in_out("#resource_stop_link");
    $.post(get_cluster_remote_url() + 'resource_stop',"resource="+curResource());
    Pcs.resourcesController.cur_resource.set("disabled",true);
  });
  $("#resource_start_link").click(function () {
    fade_in_out("#resource_start_link");
    $.post(get_cluster_remote_url() + 'resource_start',"resource="+curResource());
    Pcs.resourcesController.cur_resource.set("disabled",false);
  });
  $("#resource_cleanup_link").click(function () {
    fade_in_out("#resource_cleanup_link");
    $.post(get_cluster_remote_url() + 'resource_cleanup',"resource="+curResource());
  });
  $("#stonith_cleanup_link").click(function () {
    fade_in_out("#stonith_cleanup_link");
    $.post(get_cluster_remote_url() + 'resource_cleanup',"resource="+curResource());
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
      $.ajax({
        type: 'POST',
        url: '/remote/get_sw_versions',
        data: {"nodes": nodes.join(",")},
        timeout: pcs_timeout,
        success: function(data) {
          versions = jQuery.parseJSON(data);
          update_create_cluster_dialog(mydata, versions);
        },
        error: function (XMLHttpRequest, textStatus, errorThrown) {
          alert("ERROR: Unable to contact server");
        }
      });
    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
      alert("ERROR: Unable to contact server");
    }
  });
}

function auth_nodes() {
  $("#auth_failed_error_msg").hide();
  $.ajax({
    type: 'POST',
    url: '/remote/auth_nodes',
    data: $("#auth_nodes_form").serialize(),
    timeout: pcs_timeout,
    success: function (data) {
      mydata = jQuery.parseJSON(data);
      auth_nodes_dialog_update(mydata);
    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
      alert("ERROR: Unable to contact server");
    }
  });
}

function auth_nodes_dialog_update(data) {
  var unauth_nodes = [];
  var node;
  for (node in data) {
    if (data[node] != 0) {
      unauth_nodes.push(node);
    }
  }

  var callback_one = $("#auth_nodes").dialog("option", "callback_success_one_");
  if (unauth_nodes.length == 0) {
    $("#authenticate_submit_btn").button("option", "disabled", false);
    $("#auth_failed_error_msg").hide();
    if (callback_one !== null)
      callback_one();
    var callback = $("#auth_nodes").dialog("option", "callback_success_");
    $("#auth_nodes").dialog("close");
    if (callback !== null)
      callback();
    return unauth_nodes;
  } else {
    $("#auth_failed_error_msg").show();
  }

  if (unauth_nodes.length == 1) {
    $("#same_pass").hide();
    $('#auth_nodes_list').find('input:password').each(function(){$(this).show()});
  }

  var one_success = false;
  $("input:password[name$=-pass]").each(function() {
    node = $(this).attr("name");
    node = node.substring(0, node.length - 5);
    if (unauth_nodes.indexOf(node) == -1) {
      $(this).parent().parent().remove();
      one_success = true;
    } else {
      $(this).parent().parent().css("color", "red");
    }
  });

  if (one_success && callback_one !== null)
    callback_one();

  $("#authenticate_submit_btn").button("option", "disabled", false);
  return unauth_nodes;
}

function auth_nodes_dialog(unauth_nodes, callback_success, callback_success_one) {
  callback_success = typeof callback_success !== 'undefined' ? callback_success : null;
  callback_success_one = typeof callback_success_one !== 'undefined' ? callback_success_one : null;

  $("#auth_failed_error_msg").hide();
  var buttonsOpts = [
    {
      text: "Authenticate",
      id: "authenticate_submit_btn",
      click: function() {
        $("#authenticate_submit_btn").button("option", "disabled", true);
        $("#auth_nodes").find("table.err_msg_table").find("span[id$=_error_msg]").hide();
        auth_nodes();
      }
    },
    {
      text:"Cancel",
      click: function () {
        $(this).dialog("close");
      }
    }
  ];

  // If you hit enter it triggers the submit button
  $('#auth_nodes').keypress(function(e) {
    if (e.keyCode == $.ui.keyCode.ENTER && !$("#authenticate_submit_btn").button("option", "disabled")) {
      $("#authenticate_submit_btn").trigger("click");
      return false;
    }
  });

  if (unauth_nodes.length == 0) {
    if (callback_success !== null) {
      callback_success();
    }
    return;
  }

  if (unauth_nodes.length == 1) {
    $("#same_pass").hide();
  } else {
    $("#same_pass").show();
    $("input:checkbox[name=all]").prop("checked", false);
    $("#pass_for_all").val("");
    $("#pass_for_all").hide();
  }

  $('#auth_nodes_list').empty();
  unauth_nodes.forEach(function(node) {
    $('#auth_nodes_list').append("\t\t\t<tr><td>" + node + '</td><td><input type="password" name="' + node + '-pass"></td></tr>\n');
  });

  $("#auth_nodes").dialog({title: 'Authentification of nodes',
    modal: true, resizable: false,
    width: 'auto',
    buttons: buttonsOpts,
    callback_success_: callback_success,
    callback_success_one_: callback_success_one
  });
}

function add_existing_dialog() {
  var buttonOpts = [
    {
      text: "Add Existing",
      id: "add_existing_submit_btn",
      click: function () {
        $("#add_existing_cluster").find("table.err_msg_table").find("span[id$=_error_msg]").hide();
        $("#add_existing_submit_btn").button("option", "disabled", true);
        checkExistingNode();
      }
    },
    {
      text: "Cancel",
      click: function() {
        $(this).dialog("close");
      }
    }
  ];

  // If you hit enter it triggers the first button: Add Existing
  $('#add_existing_cluster').keypress(function(e) {
    if (e.keyCode == $.ui.keyCode.ENTER && !$("#add_existing_submit_btn").button("option", "disabled")) {
      $(this).parent().find("button:eq(1)").trigger("click");
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
    } else if (data[i] == "Unable to authenticate") {
      auth_nodes_dialog([i], function() {$("#add_existing_submit_btn").trigger("click");});
      $("#add_existing_submit_btn").button("option", "disabled", false);
      return;
    }
    break;
  }
  if (data.length > 0) {
    $('#add_existing_cluster_error_msg').html(i + ": " + data[i]);
    $('#add_existing_cluster_error_msg').show();
  }
  $('#unable_to_connect_error_msg_ae').show();
  $("#add_existing_submit_btn").button("option", "disabled", false);
}

function update_create_cluster_dialog(nodes, version_info) {
  var keys = [];
  for (var i in nodes) {
    if (nodes.hasOwnProperty(i)) {
      keys.push(i);
    }
  }

  var cant_connect_nodes = 0;
  var cant_auth_nodes = [];
  var good_nodes = 0;
  var addr1_match = 1;
  var ring0_nodes = [];
  var ring1_nodes = [];
  var cman_nodes = [];
  var noncman_nodes = [];
  var rhel_versions = [];
  var versions_check_ok = 1;
  var cluster_name = $('input[name^="clustername"]').val()
  var transport = $("#create_new_cluster select[name='config-transport']").val()

    $('#create_new_cluster input[name^="node-"]').each(function() {
      if ($(this).val() == "") {
	$(this).parent().prev().css("background-color", "");
	return;
      }
      for (var i = 0; i < keys.length; i++) {
	if ($(this).val() == keys[i]) {
	  if (nodes[keys[i]] != "Online") {
	    if (nodes[keys[i]] == "Unable to authenticate") {
	      cant_auth_nodes.push(keys[i]);
	    } else {
	      $(this).parent().prev().css("background-color", "red");
	      cant_connect_nodes++;
	    }
	  } else {
	    $(this).parent().prev().css("background-color", "");
	    good_nodes++;
	  }
	}
      }
    });

    if (cant_auth_nodes.length > 0) {
      auth_nodes_dialog(cant_auth_nodes, function(){$("#create_cluster_submit_btn").trigger("click")});
      $("#create_cluster_submit_btn").button("option", "disabled", false);
      return;
    }

  if (transport == "udpu") {
    $('#create_new_cluster input[name^="node-"]').each(function() {
      if ($(this).val().trim() != "") {
        ring0_nodes.push($(this).attr("name"));
      }
    });
    $('#create_new_cluster input[name^="ring1-node-"]').each(function() {
      if ($(this).val().trim() != "") {
        ring1_nodes.push($(this).attr("name").substr("ring1-".length));
      }
    });
    if (ring1_nodes.length > 0) {
      if (ring0_nodes.length != ring1_nodes.length) {
        addr1_match = 0
      }
      else {
        for (var i = 0; i < ring0_nodes.length; i++) {
          if (ring0_nodes[i] != ring1_nodes[i]) {
            addr1_match = 0;
            break;
          }
        }
      }
    }
  }

  if(version_info) {
    $.each(version_info, function(node, versions) {
      if(! versions["pcs"]) {
        // we do not have valid info for this node
        return;
      }
      if(versions["cman"]) {
        cman_nodes.push(node);
      }
      else {
        noncman_nodes.push(node);
      }
      if(versions["rhel"]) {
        if($.inArray(versions["rhel"].join("."), rhel_versions) == -1) {
          rhel_versions.push(versions["rhel"].join("."))
        }
      }
    });
  }

  if (cant_connect_nodes != 0) {
    $("#unable_to_connect_error_msg").show();
  } else {
    $("#unable_to_connect_error_msg").hide();
  }

  if (good_nodes == 0 && cant_connect_nodes == 0) {
    $("#at_least_one_node_error_msg").show();
  } else {
    $("#at_least_one_node_error_msg").hide();
  }

  if (cluster_name == "") {
    $("#bad_cluster_name_error_msg").show();
  } else {
    $("#bad_cluster_name_error_msg").hide();
  }

  if (addr1_match == 0) {
    $("#addr0_addr1_mismatch_error_msg").show();
  }
  else {
    $("#addr0_addr1_mismatch_error_msg").hide();
  }

  if(versions) {
    if(cman_nodes.length > 0 && transport == "udpu") {
      if(noncman_nodes.length < 1 && ring1_nodes.length < 1) {
        transport = "udp";
        $("#create_new_cluster select[name='config-transport']").val(transport);
        create_cluster_display_rrp(transport);
      }
      else {
        versions_check_ok = 0;
        $("#cman_udpu_transport_error_msg").show();
      }
    }
    else {
      $("#cman_udpu_transport_error_msg").hide();
    }

    if(cman_nodes.length > 1 && noncman_nodes.length > 1) {
      versions_check_ok = 0;
      $("#cman_mismatch_error_msg").show();
    }
    else {
      $("#cman_mismatch_error_msg").hide();
    }

    if(rhel_versions.length > 1) {
      versions_check_ok = 0;
      $("#rhel_version_mismatch_error_msg").show();
    }
    else {
      $("#rhel_version_mismatch_error_msg").hide();
    }
  }
  else {
    $("#cman_udpu_transport_error_msg").hide();
    $("#cman_mismatch_error_msg").hide();
    $("#rhel_version_mismatch_error_msg").hide();
  }

  if (good_nodes != 0 && cant_connect_nodes == 0 && cant_auth_nodes.length == 0 && cluster_name != "" && addr1_match == 1 && versions_check_ok == 1) {
    $('#create_new_cluster_form').submit();
  } else {
    $("#create_cluster_submit_btn").button("option", "disabled", false);
  }

}

function create_cluster_dialog() {
  var buttonOpts = [{
    text: "Create Cluster",
    id: "create_cluster_submit_btn",
    click: function() {
      $("#create_new_cluster").find("table.err_msg_table").find("span[id$=_error_msg]").hide();
      $("#create_cluster_submit_btn").button("option", "disabled", true);
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
  var ring1_node_list = $("#create_new_cluster_form tr").has(
    "input[name^='ring1-node-']"
  );
  cur_num_nodes = node_list.length;

  first_node = node_list.eq(0);
  new_node = first_node.clone();
  $("input",new_node).attr("name", "node-"+(cur_num_nodes+1));
  $("input",new_node).val("");
  $("td", new_node).first().text("Node " + (cur_num_nodes+1)+ ":");
  new_node.insertAfter(node_list.last());

  var ring1_first_node = ring1_node_list.eq(0);
  var ring1_new_node = ring1_first_node.clone();
  $("input", ring1_new_node).attr("name", "ring1-node-" + (cur_num_nodes + 1));
  $("input", ring1_new_node).val("");
  $("td", ring1_new_node).first().text(
    "Node " + (cur_num_nodes+1) + " (Ring 1):"
  );
  ring1_new_node.insertAfter(ring1_node_list.last());

  if (node_list.length == 7)
    $("#create_new_cluster_form tr").has("input[name^='node-']").last().next().remove();
}

function create_cluster_display_rrp(transport) {
  if(transport == 'udp') {
    $('#rrp_udp_transport').show();
    $('#rrp_udpu_transport').hide();
  }
  else {
    $('#rrp_udp_transport').hide();
    $('#rrp_udpu_transport').show();
  };
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
  $(o).addClass("node_selected");
}

function hover_out(o) {
  $(o).removeClass("node_selected");
}

function reload_current_resource() {
  load_row_by_id(Pcs.resourcesController.cur_resource.name);
}

function load_row_by_id(resource_id) {
  row = $("[nodeid='"+resource_id+"']");
  if (row.parents("#resource_list").length != 0) {
    load_agent_form(row, false);
    load_row(row, Pcs.resourcesController, 'cur_resource', '#resource_info_div', 'cur_resource_res');
  } else if (row.parents("#stonith_list").length != 0) {
    load_agent_form(row, true);
    load_row(row, Pcs.resourcesController, 'cur_resource', "#stonith_info_div", 'cur_resource_ston');
  } else
    alert("Unable to make " + resource_id + " active, doesn't appear to be resource or stonith");
}

function load_row(node_row, ac, cur_elem, containing_elem, also_set, initial_load){
  hover_over(node_row);
  $(node_row).siblings().each(function(key,sib) {
    hover_out(sib);
  });
  var self = ac;
  $(containing_elem).fadeTo(500, .01,function() {
    node_name = $(node_row).attr("nodeID");
    $.each(self.content, function(key, node) {
      if (node.name == node_name) {
	if (!initial_load) {self.set(cur_elem,node);}
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
  destroy_tooltips();
}

function destroy_tooltips() {
  $("div[id^=ui-tooltip-]").remove();
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
        $("#dialog_verify_remove_clusters.ui-dialog-content").each(function(key, item) {$(item).dialog("destroy")});
        location.reload();
      },
      error: function (xhr, status, error) {
        alert("Unable to remove cluster: " + res + " ("+error+")");
        $("#dialog_verify_remove_clusters.ui-dialog-content").each(function(key, item) {$(item).dialog("destroy")});
      }
    });
  }
}

function remove_nodes(ids, force) {
  var data = {};
  for (var i=0; i<ids.length; i++) {
    data["nodename-"+i] = ids[i];
  }
  if (force) {
    data["force"] = force;
  }

  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'remove_nodes',
    data: data,
    timeout: pcs_timeout*3,
    success: function(data,textStatus) {
      $("#dialog_verify_remove_nodes.ui-dialog-content").each(function(key, item) {$(item).dialog("destroy")});
      if (data == "No More Nodes") {
        window.location.href = "/manage";
      } else {
        Pcs.update();
      }
    },
    error: function (xhr, status, error) {
      $("#dialog_verify_remove_nodes.ui-dialog-content").each(function(key, item) {$(item).dialog("destroy")});
      if ((status == "timeout") || ($.trim(error) == "timeout")) {
        /*
         We are not interested in timeout because:
         - it can take minutes to stop a node (resources running on it have
           to be stopped/moved and we do not need to wait for that)
         - if pcs is not able to stop a node it returns an (forceable) error
           immediatelly
        */
        return;
      }
      var message = "Unable to remove nodes (" + $.trim(error) + ")";
      message += "\n" + xhr.responseText;
      if (message.indexOf('--force') == -1) {
        alert(message);
      }
      else {
        message = message.replace(', use --force to override', '');
        if (confirm(message + "\n\nDo you want to force the operation?")) {
          remove_nodes(ids, true);
        }
      }
    }
  });
}

function remove_resource(ids, force) {
  var data = {};
  if (force) {
    data["force"] = force;
  }
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
    timeout: pcs_timeout*3,
    success: function () {
      $("#dialog_verify_remove_resources.ui-dialog-content").each(function(key, item) {$(item).dialog("destroy")});
      $("#dialog_verify_remove_resources input[name=force]").attr("checked", false);
      Pcs.update();
    },
    error: function (xhr, status, error) {
      var message = "Unable to remove resources (" + error + ")";
      if (xhr.responseText.substring(0,6) == "Error:") {
        message += "\n" + xhr.responseText.replace("--force", "'Enforce removal'");
      }
      alert(message);
      $("#dialog_verify_remove_resources.ui-dialog-content").each(function(key, item) {$(item).dialog("destroy")});
      $("#dialog_verify_remove_resources input[name=force]").attr("checked", false);
      Pcs.update();
    }
  });
}

function add_remove_fence_level(parent_id,remove) {
  var data = {};
  if (remove == true) {
    data["remove"] = true;
    data["level"] = parent_id.attr("fence_level");
    data["node"] = Pcs.nodesController.cur_node.name;
    data["devices"] = parent_id.attr("fence_devices");
  } else {
    data["level"] = parent_id.parent().find("input[name='new_level_level']").val();
    data["devices"] = parent_id.parent().find("select[name='new_level_value']").val();
    data["node"] = Pcs.nodesController.cur_node.name;
  }
  fade_in_out(parent_id.parent());
  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'add_fence_level_remote',
    data: data,
    timeout: pcs_timeout,
    success: function() {
//      Pcs.nodesController.remove_fence_level();
      if (!remove)
	$(parent_id.parent()).find("input").val("");
	$(parent_id.parent()).find("select").val("");
      Pcs.update();
    },
    error: function (xhr, status, error) {
      if (remove)
        alert("Unable to remove fence level: ("+xhr.responseText+")");
      else
        if (xhr.responseText.substring(0,6) == "Error:") {
          alert(xhr.responseText);
        } else {
          alert("Unable to add fence level: ("+xhr.responseText+")");
        }
    }
  });
}

function remove_node_attr(parent_id) {
  var data = {};
  data["node"] = Pcs.nodesController.cur_node.name;
  data["key"] = parent_id.attr("node_attr_key");
  data["value"] = ""; // empty value will remove attribute
  fade_in_out(parent_id.parent());

  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'add_node_attr_remote',
    data: data,
    timeout: pcs_timeout,
    success: function() {
//      Pcs.nodesController.remove_node_attr(data["res_id"], data["key"]);
      Pcs.update();
    },
    error: function (xhr, status, error) {
      alert("Unable to add meta attribute: ("+error+")");
    }
  });
}

function add_node_attr(parent_id) {
  var data = {};
  data["node"] = Pcs.nodesController.cur_node.name;
  data["key"] = $(parent_id + " input[name='new_node_attr_key']").val();
  data["value"] = $(parent_id + " input[name='new_node_attr_value']").val();
  fade_in_out($(parent_id));

  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'add_node_attr_remote',
    data: data,
    timeout: pcs_timeout,
    success: function() {
      $(parent_id + " input").val("");
//      Pcs.nodesController.add_node_attr(data["res_id"], data["key"], data["value"]);
      Pcs.update();
    },
    error: function (xhr, status, error) {
      alert("Unable to add node attribute: ("+error+")");
    }
  });
}

function remove_meta_attr(parent_id) {
  var data = {};
  data["res_id"] = parent_id.attr("meta_attr_res");
  data["key"] = parent_id.attr("meta_attr_key");
  data["value"] = "";
  fade_in_out(parent_id.parent());

  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'add_meta_attr_remote',
    data: data,
    timeout: pcs_timeout,
    success: function() {
      Pcs.resourcesController.add_meta_attr(data["res_id"], data["key"], data["value"]);
      Pcs.update();
    },
    error: function (xhr, status, error) {
      alert("Unable to add meta attribute: ("+error+")");
    }
  });
}

function add_meta_attr(parent_id) {
  var data = {};
  data["res_id"] = Pcs.resourcesController.cur_resource.name
  data["key"] = $(parent_id + " input[name='new_meta_key']").val();
  data["value"] = $(parent_id + " input[name='new_meta_value']").val();
  fade_in_out($(parent_id));

  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'add_meta_attr_remote',
    data: data,
    timeout: pcs_timeout,
    success: function() {
      $(parent_id + " input").val("");
      Pcs.resourcesController.add_meta_attr(data["res_id"], data["key"], data["value"]);
      Pcs.update();
    },
    error: function (xhr, status, error) {
      alert("Unable to add meta attribute: ("+error+")");
    }
  });
}

function add_constraint(parent_id, c_type, force) {
  var data = {};
  data["res_id"] = Pcs.resourcesController.cur_resource.name
  data["node_id"] = $(parent_id + " input[name='node_id']").val();
  data["rule"] = $(parent_id + " input[name='node_id']").val();
  data["score"] = $(parent_id + " input[name='score']").val();
  data["target_res_id"] = $(parent_id + " input[name='target_res_id']").val();
  data["order"] = $(parent_id + " select[name='order']").val();
  data["target_action"] = $(parent_id + " select[name='target_action']").val();
  data["res_action"] = $(parent_id + " select[name='res_action']").val();
  data["colocation_type"] = $(parent_id + " select[name='colocate']").val();
  data["c_type"] = c_type;
  if (force) {
    data["force"] = force;
  }
  fade_in_out($(parent_id));

  $.ajax({ 
    type: 'POST',
    url: get_cluster_remote_url() + (
      data['node_id'] && (data['node_id'].trim().indexOf(' ') != -1)
      ? 'add_constraint_rule_remote'
      : 'add_constraint_remote'
    ),
    data: data,
    timeout: pcs_timeout,
    success: function() {
      $(parent_id + " input").val("");
      if (c_type == "loc")
	Pcs.resourcesController.add_loc_constraint(data["res_id"],"temp-cons-id",
						   data["node_id"], data["score"]);
      else if (c_type == "ord")
        Pcs.resourcesController.add_ord_constraint(
          data["res_id"], "temp-cons-id", data["target_res_id"],
          data['res_action'], data['target_action'], data["order"],
          data["score"]
        );
      else if (c_type == "col")
	Pcs.resourcesController.add_col_constraint(data["res_id"],"temp-cons-id",
						   data["target_res_id"],
						   data["colocation_type"], data["score"]);
      Pcs.update();
    },
    error: function (xhr, status, error) {
      var message = "Unable to add constraints: (" + error + ")";
      var error_prefix = 'Error adding constraint: ';
      if (
        xhr.responseText.indexOf(error_prefix) == 0
        &&
        xhr.responseText.indexOf('cib_replace failed') == -1
      ) {
        message += "\n" + xhr.responseText.slice(error_prefix.length);
      }
      if (message.indexOf('--force') == -1) {
        alert(message);
      }
      else {
        message = message.replace(', use --force to override', '');
        if (confirm(message + "\n\nDo you want to force the operation?")) {
          add_constraint(parent_id, c_type, true);
        }
      }
    }
  });
}

function add_constraint_set(parent_id, c_type, force) {
  var data = {'resources': []};
  $(parent_id + " input[name='resource_ids[]']").each(function(index, element) {
    var resources = element.value.trim();
    if (resources.length > 0) {
      data['resources'].push(resources.split(/\s+/));
    }
  });
  data["c_type"] = c_type;
  if (force) {
    data["force"] = force;
  }
  if (data['resources'].length < 1) {
    return;
  }
  fade_in_out($(parent_id))

  $.ajax({
    type: "POST",
    url: get_cluster_remote_url() + "add_constraint_set_remote",
    data: data,
    timeout: pcs_timeout,
    success: function() {
      reset_constraint_set_form(parent_id);
      if (c_type == "ord") {
        Pcs.resourcesController.add_ord_set_constraint(
          data["resources"], "temp-cons-id", "temp-cons-set-id"
        );
      }
      Pcs.update();
    },
    error: function (xhr, status, error){
      var message = "Unable to add constraints: (" + error + ")";
      var error_prefix = 'Error adding constraint: ';
      if (
        xhr.responseText.indexOf(error_prefix) == 0
        &&
        xhr.responseText.indexOf('cib_replace failed') == -1
      ) {
        message += "\n" + xhr.responseText.slice(error_prefix.length);
      }
      if (message.indexOf('--force') == -1) {
        alert(message);
      }
      else {
        message = message.replace(', use --force to override', '');
        if (confirm(message + "\n\nDo you want to force the operation?")) {
          add_constraint_set(parent_id, c_type, true);
        }
      }
    },
  });
}

function new_constraint_set_row(parent_id) {
  $(parent_id + " td").first().append(
    '<br>Set: <input type="text" name="resource_ids[]">'
  );
}

function reset_constraint_set_form(parent_id) {
  $(parent_id + " td").first().html(
    'Set: <input type="text" name="resource_ids[]">'
  );
}

function remove_constraint(id) {
  fade_in_out($("[constraint_id='"+id+"']").parent());
  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'remove_constraint_remote',
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

function remove_constraint_rule(id) {
  fade_in_out($("[rule_id='"+id+"']").parent());
  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'remove_constraint_rule_remote',
    data: {"rule_id": id},
    timeout: pcs_timeout,
    success: function (data) {
      Pcs.resourcesController.remove_constraint(id);
    },
    error: function (xhr, status, error) {
      alert("Error removing constraint rule: ("+error+")");
    }
  });
}

function add_acl_role(form) {
  var data = {}
  data["name"] = $(form).find("input[name='name']").val().trim();
  data["description"] = $(form).find("input[name='description']").val().trim();
  $.ajax({
    type: "POST",
    url: get_cluster_remote_url() + "add_acl_role",
    data: data,
    success: function(data) {
      Pcs.update();
      $(form).find("input").val("");
      $("#add_acl_role").dialog("close");
    },
    error: function(xhr, status, error) {
      alert(xhr.responseText);
    }
  });
}

function remove_acl_roles(ids) {
  var data = {};
  for (var i = 0; i < ids.length; i++) {
    data["role-" + i] = ids[i];
  }
  $.ajax({
    type: "POST",
    url: get_cluster_remote_url() + "remove_acl_roles",
    data: data,
    timeout: pcs_timeout*3,
    success: function(data,textStatus) {
      $("#dialog_verify_remove_acl_roles.ui-dialog-content").each(function(key, item) {$(item).dialog("destroy")});
      Pcs.update();
    },
    error: function (xhr, status, error) {
      alert(xhr.responseText);
      $("#dialog_verify_remove_acl_roles.ui-dialog-content").each(function(key, item) {$(item).dialog("destroy")});
    }
  });
}

function add_acl_item(parent_id, item_type) {
  var data = {};
  data["role_id"] = Pcs.aclsController.cur_role.name;
  switch (item_type) {
    case "perm":
      data["item"] = "permission";
      data["type"] = $(parent_id + " select[name='role_type']").val();
      data["xpath_id"] = $(parent_id + " select[name='role_xpath_id']").val();
      data["query_id"] = $(parent_id + " input[name='role_query_id']").val().trim();
      break;
    case "user":
    case "group":
      data["item"] = item_type;
      data["usergroup"] = $(parent_id + " input[name='role_assign_user']").val().trim();
      break;
  }
  fade_in_out($(parent_id));
  $.ajax({
    type: "POST",
    url: get_cluster_remote_url() + 'add_acl',
    data: data,
    timeout: pcs_timeout,
    success: function(data) {
      $(parent_id + " input").val("");
      Pcs.update();
    },
    error: function (xhr, status, error) {
      alert(xhr.responseText);
    }
  });
}

function remove_acl_item(id,item) {
  fade_in_out(id);
  var data = {};
  switch (item) {
    case "perm":
      data["item"] = "permission";
      data["acl_perm_id"] = id.attr("acl_perm_id");
      break;
    case "usergroup":
      data["item"] = "usergroup";
      data["usergroup_id"] = id.attr("usergroup_id")
      data["role_id"] = id.attr("role_id")
      break;
  }

  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'remove_acl',
    data: data,
    timeout: pcs_timeout,
    success: function (data) {
      Pcs.update();
//      Pcs.resourcesController.remove_constraint(id);
    },
    error: function (xhr, status, error) {
      alert(xhr.responseText);
    }
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
  var cluster_name = location.pathname.match("/managec/(.*)/");
  if (cluster_name && cluster_name.length >= 2) {
    Ember.debug("Cluster Name: " + cluster_name[1]);
    cluster_name = cluster_name[1];
    return cluster_name;
  }
  Ember.debug("Cluster Name is 'null'");
  cluster_name = null;
  return cluster_name;
}

function get_cluster_remote_url(cluster_name) {
  cluster_name = typeof cluster_name !== 'undefined' ? cluster_name : Pcs.cluster_name;
  return '/managec/' + cluster_name + "/";
}

function checkBoxToggle(cb,nodes) {
  if (nodes) {
    cbs = $('#node_list table').find(".node_list_check input[type=checkbox]");
  } else {
    cbs = $(cb).closest("tr").parent().find(".node_list_check input[type=checkbox]")
  }
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

function update_resource_type_options() {
  var cp = $("#resource_class_provider_selector").val();
  var target = $("#add_ra_type");
  var source = $("#all_ra_types");

  target.empty();
  source.find("option").each(function(i,v) {
    if ($(v).val().indexOf(cp) == 0) {
      new_option = $(v).clone();
      target.append(new_option);
    }
  });
  target.change();
}

function setup_resource_class_provider_selection() {
  $("#resource_class_provider_selector").change(function() {
    update_resource_type_options();
  });
  $("#resource_class_provider_selector").change();
}

function get_status_value(status) {
  var values = {
    failed: 1,
    error: 1,
    offline: 1,
    blocked: 1,
    warning: 2,
    standby: 2,
    disabled: 3,
    unknown: 3,
    ok: 4,
    running: 4,
    online: 4
  };
  return ((values.hasOwnProperty(status)) ? values[status] : -1);
}

function status_comparator(a,b) {
  var valA = get_status_value(a);
  var valB = get_status_value(b);
  if (valA == -1) return 1;
  if (valB == -1) return -1;
  return valA - valB;
}

function get_status_color(status_val) {
  if (status_val == get_status_value("ok")) {
    return "green";
  }
  else if (status_val == get_status_value("warning") || status_val == get_status_value("unknown")) {
    return "orange";
  }
  return "red";
}

function show_hide_dashboard(element, type) {
  var cluster = Pcs.clusterController.cur_cluster;
  if (Pcs.clusterController.get("show_all_" + type)) { // show only failed
    Pcs.clusterController.set("show_all_" + type, false);
  } else { // show all
    Pcs.clusterController.set("show_all_" + type, true);
  }
  correct_visibility_dashboard_type(cluster, type);
}

function correct_visibility_dashboard(cluster) {
  if (cluster == null)
    return;
  $.each(["nodes", "resources", "fence"], function(key, type) {
    correct_visibility_dashboard_type(cluster, type);
  });
}

function correct_visibility_dashboard_type(cluster, type) {
  if (cluster == null) {
    return;
  }
  destroy_tooltips();
  var listTable = $("#cluster_info_" + cluster.name).find("table." + type + "_list");
  var datatable = listTable.find("table.datatable");
  if (Pcs.clusterController.get("show_all_" + type)) {
    listTable.find("span.downarrow").show();
    listTable.find("span.rightarrow").hide();
    datatable.find("tr.default-hidden").removeClass("hidden");
  } else {
    listTable.find("span.downarrow").hide();
    listTable.find("span.rightarrow").show();
    datatable.find("tr.default-hidden").addClass("hidden");
  }
  if (cluster.get(type + "_failed") == 0 && !Pcs.clusterController.get("show_all_" + type)) {
    datatable.hide();
  } else {
    datatable.show();
  }
}

function get_formated_html_list(data) {
  if (data == null || data.length == 0) {
    return "";
  }
  var out = "<ul>";
  $.each(data, function(key, value) {
    out += "<li>" + htmlEncode(value.message) + "</li>";
  });
  out += "</ul>";
  return out;
}

function htmlEncode(s)
{
  return $("<div/>").text(s).html().replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function fix_auth_of_cluster() {
  show_loading_screen();
  var clustername = Pcs.clusterController.cur_cluster.name;
  $.ajax({
    url: "/remote/fix_auth_of_cluster",
    type: "POST",
    data: "clustername=" + clustername,
    success: function(data) {
      hide_loading_screen();
      Pcs.update();
    },
    error: function(jqhxr,b,c) {
      hide_loading_screen();
      Pcs.update();
      alert(jqhxr.responseText);
    }
  });
}
