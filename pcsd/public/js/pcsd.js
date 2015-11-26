var pcs_timeout = 30000;

function curResource() {
  return Pcs.resourcesContainer.get('cur_resource').get('id')
}

function curStonith() {
  return Pcs.resourcesContainer.get('cur_fence').get('id')
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
    Pcs.set('cur_page',"resources");
    menu_show("resource", true);
  } else {
    menu_show("resource", false);
  }

  if (menu == "FENCE DEVICES") {
    Pcs.set('cur_page',"stonith");
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

  if (menu == "PERMISSIONS") {
    Pcs.set('cur_page', "permissions");
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
    return;
  }

  $("#resources_to_add_to_group").val(node_names);
  $("#add_group").dialog({
    title: 'Create Group',
    modal: true,
    resizable: false,
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
          },
          error: function (xhr, status, error) {
            alert(
              "Error creating group "
              + ajax_simple_error(xhr, status, error)
            );
            $("#add_group").dialog("close");
          }
        });
      }
    }
  });
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
    error: function(xhr, status, error) {
      if (update) {
        alert(
          "Unable to update " + name + " "
          + ajax_simple_error(xhr, status, error)
        );
      }
      else {
        alert(
          "Unable to add " + name + " "
          + ajax_simple_error(xhr, status, error)
        );
      }
      $('input.apply_changes').show();
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
  var data = { new: true, resourcename: ra};
  var command;
  if (!stonith)
    command = "resource_metadata";
  else
    command = "fence_device_metadata";
  
  item.load(get_cluster_remote_url() + command, data);
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

function node_link_action(link_selector, url, label) {
  var node = $.trim($("#node_info_header_title_name").text());
  fade_in_out(link_selector);
  $.ajax({
    type: 'POST',
    url: url,
    data: {"name": node},
    success: function() {
    },
    error: function (xhr, status, error) {
      alert(
        "Unable to " + label + " node '" + node + "' "
        + ajax_simple_error(xhr, status, error)
      );
    }
  });
}

function setup_node_links() {
  Ember.debug("Setup node links");
  $("#node_start").click(function() {
    node_link_action("#node_start", "/remote/cluster_start", "start");
  });
  $("#node_stop").click(function() {
    var node = $.trim($("#node_info_header_title_name").text());
    fade_in_out("#node_stop");
    node_stop(node, false);
  });
  $("#node_restart").click(function() {
    node_link_action("#node_restart", "/remote/node_restart", "restart");
  });
  $("#node_standby").click(function() {
    node_link_action("#node_standby", "/remote/node_standby", "standby");
  });
  $("#node_unstandby").click(function() {
    node_link_action("#node_unstandby", "/remote/node_unstandby", "unstandby");
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
      var message = "Unable to stop node '" + node + " " + ajax_simple_error(
        xhr, status, error
      );
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

function enable_resource() {
  fade_in_out("#resource_start_link");
  Pcs.resourcesContainer.enable_resource(curResource());
}

function disable_resource() {
  fade_in_out("#resource_stop_link");
  Pcs.resourcesContainer.disable_resource(curResource());
}

function cleanup_resource() {
  var resource = curResource();
  fade_in_out("#resource_cleanup_link");
  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'resource_cleanup',
    data: {"resource": resource},
    success: function() {
    },
    error: function (xhr, status, error) {
      alert(
        "Unable to cleanup resource '" + resource + "' "
        + ajax_simple_error(xhr, status, error)
      );
    }
  });
}

function cleanup_stonith() {
  var resource = curStonith();
  fade_in_out("#stonith_cleanup_link");
  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'resource_cleanup',
    data: {"resource": resource},
    success: function() {
    },
    error: function (xhr, status, error) {
      alert(
        "Unable to cleanup resource '" + resource + "' "
        + ajax_simple_error(xhr, status, error)
      );
    }
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

function auth_nodes(dialog) {
  $("#auth_failed_error_msg").hide();
  $.ajax({
    type: 'POST',
    url: '/remote/auth_gui_against_nodes',
    data: dialog.find("#auth_nodes_form").serialize(),
    timeout: pcs_timeout,
    success: function (data) {
      mydata = jQuery.parseJSON(data);
      auth_nodes_dialog_update(dialog, mydata);
    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
      alert("ERROR: Unable to contact server");
    }
  });
}

function auth_nodes_dialog_update(dialog_obj, data) {
  var unauth_nodes = [];
  var node;
  if (data['node_auth_error']) {
    for (node in data['node_auth_error']) {
      if (data['node_auth_error'][node] != 0) {
        unauth_nodes.push(node);
      }
    }
  }

  var callback_one = dialog_obj.dialog("option", "callback_success_one_");
  var callback = dialog_obj.dialog("option", "callback_success_");
  if (unauth_nodes.length == 0) {
    dialog_obj.parent().find("#authenticate_submit_btn").button(
      "option", "disabled", false
    );
    dialog_obj.find("#auth_failed_error_msg").hide();
    dialog_obj.dialog("close");
    if (callback_one !== null)
      callback_one();
    if (callback !== null)
      callback();
    return unauth_nodes;
  } else {
    dialog_obj.find("#auth_failed_error_msg").show();
  }

  if (unauth_nodes.length == 1) {
    dialog_obj.find("#same_pass").hide();
    dialog_obj.find('#auth_nodes_list').find('input:password').each(
      function(){$(this).show()}
    );
  }

  var one_success = false;
  dialog_obj.find("input:password[name$=-pass]").each(function() {
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

  dialog_obj.parent().find("#authenticate_submit_btn").button(
    "option", "disabled", false
  );
  return unauth_nodes;
}

function auth_nodes_dialog(unauth_nodes, callback_success, callback_success_one) {
  callback_success = typeof callback_success !== 'undefined' ? callback_success : null;
  callback_success_one = typeof callback_success_one !== 'undefined' ? callback_success_one : null;

  var buttonsOpts = [
    {
      text: "Authenticate",
      id: "authenticate_submit_btn",
      click: function() {
        var dialog = $(this);
        dialog.parent().find("#authenticate_submit_btn").button(
          "option", "disabled", true
        );
        dialog.find("table.err_msg_table").find("span[id$=_error_msg]").hide();
        auth_nodes(dialog);
      }
    },
    {
      text:"Cancel",
      click: function () {
        $(this).dialog("close");
      }
    }
  ];
  var dialog_obj = $("#auth_nodes").dialog({title: 'Authentification of nodes',
    modal: true, resizable: false,
    width: 'auto',
    buttons: buttonsOpts,
    callback_success_: callback_success,
    callback_success_one_: callback_success_one
  });

  dialog_obj.find("#auth_failed_error_msg").hide();

  // If you hit enter it triggers the submit button
  dialog_obj.keypress(function(e) {
    if (e.keyCode == $.ui.keyCode.ENTER && !dialog_obj.parent().find("#authenticate_submit_btn").button("option", "disabled")) {
      dialog_obj.parent().find("#authenticate_submit_btn").trigger("click");
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
    dialog_obj.find("#same_pass").hide();
  } else {
    dialog_obj.find("#same_pass").show();
    dialog_obj.find("input:checkbox[name=all]").prop("checked", false);
    dialog_obj.find("#pass_for_all").val("");
    dialog_obj.find("#pass_for_all").hide();
  }

  dialog_obj.find('#auth_nodes_list').empty();
  unauth_nodes.forEach(function(node) {
    dialog_obj.find('#auth_nodes_list').append("\t\t\t<tr><td>" + node + '</td><td><input type="password" name="' + node + '-pass"></td></tr>\n');
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
  tree_view_onclick(curResource(), true);
  tree_view_onclick(curStonith(), true);
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
        if (!initial_load) {
          self.set(cur_elem,node);
        }
        node.set(cur_elem, true);
        if (also_set)
          self.set(also_set, node);
      } else {
        if (self.cur_resource_ston && self.cur_resource_ston.name == node.name)
          self.content[key].set(cur_elem,true);
        else if (self.cur_resource_res && self.cur_resource_res.name == node.name)
          self.content[key].set(cur_elem,true);
        else
          self.content[key].set(cur_elem,false);
      }
    });
    $(containing_elem).fadeTo(500,1);
  });
}

function load_agent_form(resource_id, stonith) {
  var url;
  var form;
  if (stonith) {
    form = $("#stonith_agent_form");
    url = '/managec/' + Pcs.cluster_name + '/fence_device_form';
  } else {
    form = $("#resource_agent_form");
    url = '/managec/' + Pcs.cluster_name + '/resource_form?version=2';
  }

  form.empty();

  var resource_obj = Pcs.resourcesContainer.get_resource_by_id(resource_id);
  if (!resource_obj || !resource_obj.get('is_primitive'))
    return;

  var data = {resource: resource_id};

  $.ajax({
    type: 'GET',
    url: url,
    data: data,
    timeout: pcs_timeout,
    success: function (data) {
      Ember.run.next(function(){form.html(data);});
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
  var data = {};
  $.each(ids, function(_, cluster) {
    data[ "clusterid-" + cluster] = true;
  });
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
  var data = {
    no_error_if_not_exists: true
  };
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
      error = $.trim(error)
      var message = "Unable to remove resources (" + error + ")";
      if (
        (xhr.responseText.substring(0,6) == "Error:") || ("Forbidden" == error)
      ) {
        message += "\n\n" + xhr.responseText.replace("--force", "'Enforce removal'");
      }
      alert(message);
      $("#dialog_verify_remove_resources.ui-dialog-content").each(
        function(key, item) { $(item).dialog("destroy"); }
      );
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
      if (!remove) {
        $(parent_id.parent()).find("input").val("");
        $(parent_id.parent()).find("select").val("");
      }
      Pcs.update();
    },
    error: function (xhr, status, error) {
      if (remove) {
        alert(
          "Unable to remove fence level "
          + ajax_simple_error(xhr, status, error)
        );
      }
      else {
        if (xhr.responseText.substring(0,6) == "Error:") {
          alert(xhr.responseText);
        } else {
          alert(
            "Unable to add fence level "
            + ajax_simple_error(xhr, status, error)
          );
        }
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
      alert(
        "Unable to remove node attribute "
        + ajax_simple_error(xhr, status, error)
      );
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
      alert(
        "Unable to add node attribute "
        + ajax_simple_error(xhr, status, error)
      );
    }
  });
}

function node_maintenance(node) {
  var data = {
    node: node,
    key: "maintenance",
    value: "on"
  };
  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'add_node_attr_remote',
    data: data,
    timeout: pcs_timeout,
    error: function (xhr, status, error) {
      alert(
        "Unable to put node '" + node + "' to maintenance mode. "
        + ajax_simple_error(xhr, status, error)
      );
    },
    complete: function() {
      Pcs.update();
    }
  });
}

function node_unmaintenance(node) {
  var data = {
    node: node,
    key: "maintenance",
    value: ""
  };
  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'add_node_attr_remote',
    data: data,
    timeout: pcs_timeout,
    error: function (xhr, status, error) {
      alert(
        "Unable to remove node '" + node + "' from maintenance mode. "
        + ajax_simple_error(xhr, status, error)
      );
    },
    complete: function() {
      Pcs.update();
    }
  });
}

function remove_meta_attr(parent_id) {
  var resource_id = curResource();
  var attr = parent_id.attr("meta_attr_key");
  fade_in_out(parent_id.parent());
  Pcs.resourcesContainer.update_meta_attr(resource_id, attr);
}

function add_meta_attr(parent_id) {
  var resource_id = curResource();
  var attr = $(parent_id + " input[name='new_meta_key']").val();
  var value = $(parent_id + " input[name='new_meta_value']").val();
  fade_in_out($(parent_id));
  $(parent_id + " input").val("");
  Pcs.resourcesContainer.update_meta_attr(resource_id, attr, value);
}

function add_constraint(parent_id, c_type, force) {
  var data = {};
  data["disable_autocorrect"] = true;
  data["res_id"] = Pcs.resourcesContainer.cur_resource.get('id');
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
      Pcs.update();
    },
    error: function (xhr, status, error) {
      var message = "Unable to add constraint (" + $.trim(error) + ")";
      var error_prefix = 'Error adding constraint: ';
      if (xhr.responseText.indexOf('cib_replace failed') == -1) {
        if (xhr.responseText.indexOf(error_prefix) == 0) {
          message += "\n\n" + xhr.responseText.slice(error_prefix.length);
        }
        else {
          message += "\n\n" + xhr.responseText;
        }
      }
      if (message.indexOf('--force') == -1) {
        alert(message);
        Pcs.update();
      }
      else {
        message = message.replace(', use --force to override', '');
        message = message.replace('Use --force to override.', '');
        if (confirm(message + "\n\nDo you want to force the operation?")) {
          add_constraint(parent_id, c_type, true);
        }
      }
    }
  });
}

function add_constraint_set(parent_id, c_type, force) {
  var data = {
    resources: [],
    disable_autocorrect: true
  };
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
      Pcs.update();
    },
    error: function (xhr, status, error){
      var message = "Unable to add constraint (" + $.trim(error) + ")";
      var error_prefix = 'Error adding constraint: ';
      if (xhr.responseText.indexOf('cib_replace failed') == -1) {
        if (xhr.responseText.indexOf(error_prefix) == 0) {
          message += "\n\n" + xhr.responseText.slice(error_prefix.length);
        }
        else {
          message += "\n\n" + xhr.responseText;
        }
      }
      if (message.indexOf('--force') == -1) {
        alert(message);
        Pcs.update();
      }
      else {
        message = message.replace(', use --force to override', '');
        message = message.replace('Use --force to override.', '');
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
    error: function (xhr, status, error) {
      alert(
        "Error removing constraint "
        + ajax_simple_error(xhr, status, error)
      );
    },
    complete: function() {
      Pcs.update();
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
    error: function (xhr, status, error) {
      alert(
        "Error removing constraint rule "
        + ajax_simple_error(xhr, status, error)
      );
    },
    complete: function() {
      Pcs.update();
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
      alert(
        "Error adding ACL role "
        + ajax_simple_error(xhr, status, error)
      );
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
      $("#dialog_verify_remove_acl_roles.ui-dialog-content").each(
        function(key, item) { $(item).dialog("destroy"); }
      );
      Pcs.update();
    },
    error: function (xhr, status, error) {
      alert(
        "Error removing ACL role "
        + ajax_simple_error(xhr, status, error)
      );
      $("#dialog_verify_remove_acl_roles.ui-dialog-content").each(
        function(key, item) { $(item).dialog("destroy"); }
      );
    }
  });
}

function add_acl_item(parent_id, item_type) {
  var data = {};
  data["role_id"] = Pcs.aclsController.cur_role.name;
  var item_label = "";
  switch (item_type) {
    case "perm":
      data["item"] = "permission";
      data["type"] = $(parent_id + " select[name='role_type']").val();
      data["xpath_id"] = $(parent_id + " select[name='role_xpath_id']").val();
      data["query_id"] = $(parent_id + " input[name='role_query_id']").val().trim();
      item_label = "permission"
      break;
    case "user":
    case "group":
      data["item"] = item_type;
      data["usergroup"] = $(parent_id + " input[name='role_assign_user']").val().trim();
      item_label = item_type
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
      alert(
        "Error adding " + item_label + " "
        + ajax_simple_error(xhr, status, error)
      );
    }
  });
}

function remove_acl_item(id,item) {
  fade_in_out(id);
  var data = {};
  var item_label = "";
  switch (item) {
    case "perm":
      data["item"] = "permission";
      data["acl_perm_id"] = id.attr("acl_perm_id");
      item_label = "permission"
      break;
    case "usergroup":
      data["item"] = "usergroup";
      data["usergroup_id"] = id.attr("usergroup_id")
      data["role_id"] = id.attr("role_id")
      item_label = "user / group"
      break;
  }

  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'remove_acl',
    data: data,
    timeout: pcs_timeout,
    success: function (data) {
      Pcs.update();
    },
    error: function (xhr, status, error) {
      alert(
        "Error removing " + item_label + " "
        + ajax_simple_error(xhr, status, error)
      );
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
      alert(
        "Error updating configuration "
        + ajax_simple_error(xhr, status, error)
      );
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
    cbs.prop('checked',true).change();
  else
    cbs.prop('checked',false).change();
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
    maintenance: 2,
    "partially running": 2,
    disabled: 3,
    unknown: 4,
    ok: 5,
    running: 5,
    online: 5
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

function get_status_icon_class(status_val) {
  switch (status_val) {
    case get_status_value("error"):
      return "error";
    case get_status_value("disabled"):
    case get_status_value("warning"):
      return "warning";
    case get_status_value("ok"):
      return "check";
    default:
      return "x";
  }
}

function get_status_color(status_val) {
  if (status_val == get_status_value("ok")) {
    return "green";
  }
  else if (status_val == get_status_value("warning") || status_val == get_status_value("unknown") || status_val == get_status_value('disabled')) {
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

function get_tree_view_element_id(element) {
  return $(element).parents('table.tree-element')[0].id;
}

function get_list_view_element_id(element) {
  return $(element)[0].id;
}

function auto_show_hide_constraints() {
  var cont = ["location_constraints", "ordering_constraints", "ordering_set_constraints", "colocation_constraints", "meta_attributes"];
  $.each(cont, function(index, name) {
    var elem = $("#" + name)[0];
    var cur_resource = Pcs.resourcesContainer.get('cur_resource');
    if (elem && cur_resource) {
      var visible = $(elem).children("span")[0].style.display != 'none';
      if (visible && (!cur_resource.get(name) || cur_resource.get(name).length == 0))
        show_hide_constraints(elem);
      else if (!visible && cur_resource.get(name) && cur_resource.get(name).length > 0)
        show_hide_constraints(elem);
    }
  });
}

function tree_view_onclick(resource_id, auto) {
  auto = typeof auto !== 'undefined' ? auto : false;
  var resource_obj = Pcs.resourcesContainer.get_resource_by_id(resource_id);
  if (!resource_obj) {
    console.log("Resource " + resource_id + "not found.");
    return;
  }
  if (resource_obj.get('stonith')) {
    Pcs.resourcesContainer.set('cur_fence', resource_obj);
    if (!auto) window.location.hash = "/fencedevices/" + resource_id;
  } else {
    Pcs.resourcesContainer.set('cur_resource', resource_obj);
    if (!auto) window.location.hash = "/resources/" + resource_id;
    auto_show_hide_constraints();
  }

  tree_view_select(resource_id);

  Ember.run.next(Pcs, function() {
    load_agent_form(resource_id, resource_obj.get('stonith'));
  });
}

function tree_view_select(element_id) {
  var e = $('#' + element_id);
  var view = e.parents('table.tree-view');
  view.find('div.arrow').hide();
  view.find('tr.children').hide();
  view.find('table.tree-element').show();
  view.find('tr.tree-element-name').removeClass("node_selected");
  e.find('tr.tree-element-name:first').addClass("node_selected");
  e.find('tr.tree-element-name div.arrow:first').show();
  e.parents('tr.children').show();
  e.find('tr.children').show();
}

function list_view_select(element_id) {
  var e = $('#' + element_id);
  var view = e.parents('table.list-view');
  view.find('div.arrow').hide();
  view.find('tr.list-view-element').removeClass("node_selected");
  e.addClass('node_selected');
  e.find('div.arrow').show();
}

function tree_view_checkbox_onchange(element) {
  var e = $(element);
  var children = $(element).closest(".tree-element").find(".children" +
    " input:checkbox");
  var val = e.prop('checked');
  children.prop('checked', val);
  children.prop('disabled', val);
}

function resource_master(resource_id) {
  show_loading_screen();
  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'resource_master',
    data: {resource_id: resource_id},
    timeout: pcs_timeout,
    error: function (xhr, status, error) {
      alert(
        "Unable to create master/slave resource "
        + ajax_simple_error(xhr, status, error)
      );
    },
    complete: function() {
      Pcs.update();
    }
  });
}

function resource_clone(resource_id) {
  show_loading_screen();
  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'resource_clone',
    data: {resource_id: resource_id},
    timeout: pcs_timeout,
    error: function (xhr, status, error) {
      alert(
        "Unable to clone the resource "
        + ajax_simple_error(xhr, status, error)
      );
    },
    complete: function() {
      Pcs.update();
    }
  });
}

function resource_unclone(resource_id) {
  show_loading_screen();
  var resource_obj = Pcs.resourcesContainer.get_resource_by_id(resource_id);
  if (resource_obj.get('class_type') == 'clone') {
    resource_id = resource_obj.get('member').get('id');
  }
  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'resource_unclone',
    data: {resource_id: resource_id},
    timeout: pcs_timeout,
    error: function (xhr, status, error) {
      alert(
        "Unable to unclone the resource "
        + ajax_simple_error(xhr, status, error)
      );
    },
    complete: function() {
      Pcs.update();
    }
  });
}

function resource_ungroup(group_id) {
  show_loading_screen();
  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'resource_ungroup',
    data: {group_id: group_id},
    timeout: pcs_timeout,
    error: function (xhr, status, error) {
      alert(
        "Unable to ungroup the resource "
        + ajax_simple_error(xhr, status, error)
      );
    },
    complete: function() {
      Pcs.update();
    }
  });
}

function resource_change_group(resource_id, group_id) {
  show_loading_screen();
  var resource_obj = Pcs.resourcesContainer.get_resource_by_id(resource_id);
  var data = {
    resource_id: resource_id,
    group_id: group_id
  };
  
  if (resource_obj.get('parent')) {
    if (resource_obj.get('parent').get('id') == group_id) {
      return;  
    }
    if (resource_obj.get('parent').get('class_type') == 'group') {
      data['old_group_id'] = resource_obj.get('parent').get('id');
    }
  }

  $.ajax({
    type: 'POST',
    url: get_cluster_remote_url() + 'resource_change_group',
    data: data,
    timeout: pcs_timeout,
    error: function (xhr, status, error) {
      alert(
        "Unable to change group "
        + ajax_simple_error(xhr, status, error)
      );
    },
    complete: function() {
      Pcs.update();
    }
  });
}

function ajax_simple_error(xhr, status, error) {
  var message = "(" + $.trim(error) + ")"
  if (
    $.trim(xhr.responseText).length > 0
    &&
    xhr.responseText.indexOf('cib_replace failed') == -1
  ) {
    message = message + "\n\n" + $.trim(xhr.responseText);
  }
  return message;
}

var permissions_current_cluster;

function permissions_load_all() {
  show_loading_screen();

  var cluster_list = [];
  $("#node_info div[id^='permissions_cluster_']").each(function(i, div) {
    cluster_list.push(
      $(div).attr("id").substring("permissions_cluster_".length)
    );
  });

  var call_count = cluster_list.length;
  var callback = function() {
    call_count = call_count - 1;
    if (call_count < 1) {
      hide_loading_screen();
    }
  }

  $.each(cluster_list, function(index, cluster) {
    permissions_load_cluster(cluster, callback);
  });

  if (cluster_list.length > 0) {
    permissions_current_cluster = cluster_list[0];
    permissions_show_cluster(
      permissions_current_cluster,
      $("#cluster_list tr").first().next() /* the first row is a heading */
    );
  }
  else {
    hide_loading_screen();
  }
}

function permissions_load_cluster(cluster_name, callback) {
  var element_id = "permissions_cluster_" + cluster_name;
  $.ajax({
    type: "GET",
    url: "/permissions_cluster_form/" + cluster_name,
    timeout: pcs_timeout,
    success: function(data) {
      $("#" + element_id).html(data);
      $("#" + element_id + " :checkbox").each(function(key, checkbox) {
        permissions_fix_dependent_checkboxes(checkbox);
      });
      permissions_cluster_dirty_flag(cluster_name, false);
      if (callback) {
        callback();
      }
    },
    error: function(xhr, status, error) {
      $("#" + element_id).html(
        "Error loading permissions " + ajax_simple_error(xhr, status, error)
      );
      if (callback) {
        callback();
      }
    }
  });
}

function permissions_show_cluster(cluster_name, list_row) {
  permissions_current_cluster = cluster_name;

  var container = $("#node_info");
  container.fadeTo(500, .01, function() {
    container.children().hide();
    $("#permissions_cluster_" + cluster_name).show();
    container.fadeTo(500, 1);
  });

  $(list_row).siblings("tr").each(function(index, row) {
    hover_out(row);
    $(row).find("td").last().children().hide();
  });
  hover_over(list_row);
  $(list_row).find("td").last().children().show();
}

function permissions_save_cluster(form) {
  var dataString = $(form).serialize();
  var cluster_name = permissions_get_clustername(form);
  $.ajax({
    type: "POST",
    url: "/permissions_save/",
    timeout: pcs_timeout,
    data: dataString,
    success: function() {
      show_loading_screen();
      permissions_load_cluster(cluster_name, hide_loading_screen);
    },
    error: function(xhr, status, error) {
      alert(
        "Unable to save permissions of cluster " + cluster_name + " "
        + ajax_simple_error(xhr, status, error)
      );
    }
  });
}

function permissions_cluster_dirty_flag(cluster_name, flag) {
  var cluster_row = permissions_get_cluster_row(cluster_name);
  if (cluster_row) {
    var dirty_elem = cluster_row.find("span[class=unsaved_changes]");
    if (dirty_elem) {
      if (flag) {
        dirty_elem.show();
      }
      else {
        dirty_elem.hide();
      }
    }
  }
}

function permission_remove_row(button) {
  var cluster_name = permissions_get_clustername(
    $(button).parents("form").first()
  );
  $(button).parent().parent().remove();
  permissions_cluster_dirty_flag(cluster_name, true);
}

function permissions_add_row(template_row) {
  var user_name = permissions_get_row_name(template_row);
  var user_type = permissions_get_row_type(template_row);
  var max_key = -1;
  var exists = false;
  var cluster_name = permissions_get_clustername(
    $(template_row).parents("form").first()
  );

  if("" == user_name) {
    alert("Please enter the name");
    return;
  }
  if("" == user_type) {
    alert("Please enter the type");
    return;
  }

  $(template_row).siblings().each(function(index, row) {
    if(
      (permissions_get_row_name(row) == user_name)
      &&
      (permissions_get_row_type(row) == user_type)
    ) {
      exists = true;
    }
    $(row).find("input").each(function(index, input) {
      var match = input.name.match(/^[^[]*\[(\d+)\].*$/);
      if (match) {
        var key = parseInt(match[1]);
        if(key > max_key) {
          max_key = key;
        }
      }
    });
  });
  if(exists) {
    alert("Permissions already set for the user");
    return;
  }

  max_key = max_key + 1;
  var new_row = $(template_row).clone();
  new_row.find("[name*='_new']").each(function(index, element) {
    element.name = element.name.replace("_new", "[" + max_key + "]");
  });
  new_row.find("td").last().html(
    '<a class="remove" href="#" onclick="permission_remove_row(this);">X</a>'
  );
  new_row.find("[name$='[name]']").each(function(index, element) {
    $(element).after(user_name);
    $(element).attr("type", "hidden");
  });
  new_row.find("[name$='[type]']").each(function(index, element) {
    $(element).after(user_type);
    $(element).after(
      '<input type="hidden" name="' + element.name  + '" value="' + user_type + '">'
    );
    $(element).remove();
  });

  $(template_row).before(new_row);
  var template_inputs = $(template_row).find(":input");
  template_inputs.removeAttr("checked").removeAttr("selected");
  template_inputs.removeAttr("disabled").removeAttr("readonly");
  $(template_row).find(":input[type=text]").val("");

  permissions_cluster_dirty_flag(cluster_name, true);
}

function permissions_get_dependent_checkboxes(checkbox) {
  var cluster_name = permissions_get_clustername(
    $(checkbox).parents("form").first()
  );
  var checkbox_permission = permissions_get_checkbox_permission(checkbox);
  var deps = {};
  var dependent_permissions = [];
  var dependent_checkboxes = [];

  if (permissions_dependencies[cluster_name]) {
    deps = permissions_dependencies[cluster_name];
    if (deps["also_allows"] && deps["also_allows"][checkbox_permission]) {
      dependent_permissions = deps["also_allows"][checkbox_permission];
      $(checkbox).parents("tr").first().find(":checkbox").not(checkbox).each(
        function(key, check) {
          var perm = permissions_get_checkbox_permission(check);
          if (dependent_permissions.indexOf(perm) != -1) {
            dependent_checkboxes.push(check);
          }
        }
      );
    }
  }
  return dependent_checkboxes;
}

function permissions_fix_dependent_checkboxes(checkbox) {
  var dep_checks = $(permissions_get_dependent_checkboxes(checkbox));
  if ($(checkbox).prop("checked")) {
    /* the checkbox is now checked */
    dep_checks.each(function(key, check) {
      var jq_check = $(check);
      jq_check.prop("checked", true);
      jq_check.prop("readonly", true);
      // readonly on checkbox makes it look like readonly but doesn't prevent
      // changing its state (checked - not checked), setting disabled works
      jq_check.prop("disabled", true);
      permissions_fix_dependent_checkboxes(check);
    });
  }
  else {
    /* the checkbox is now empty */
    dep_checks.each(function(key, check) {
      var jq_check = $(check);
      jq_check.prop("checked", jq_check.prop("defaultChecked"));
      jq_check.prop("readonly", false);
      jq_check.prop("disabled", false);
      permissions_fix_dependent_checkboxes(check);
    });
  }
}

function permissions_get_row_name(row) {
  return $.trim($(row).find("[name$='[name]']").val());
}

function permissions_get_row_type(row) {
  return $.trim($(row).find("[name$='[type]']").val());
}

function permissions_get_clustername(form) {
  return $.trim($(form).find("[name=cluster_name]").val());
}

function permissions_get_checkbox_permission(checkbox) {
  var match = checkbox.name.match(/^.*\[([^[]+)\]$/);
  if (match) {
    return match[1];
  }
  return "";
}

function permissions_get_cluster_row(cluster_name) {
  var cluster_row = null;
  $('#cluster_list td[class=node_name]').each(function(index, elem) {
    var jq_elem = $(elem);
    if (jq_elem.text().trim() == cluster_name.trim()) {
      cluster_row = jq_elem.parents("tr").first();
    }
  });
  return cluster_row;
}

function is_cib_true(value) {
  if (value) {
    return (['true', 'on', 'yes', 'y', '1'].indexOf(value.toString().toLowerCase()) != -1);
  }
  return false;
}

function set_utilization(type, entity_id, name, value) {
  var data = {
    name: name,
    value: value
  };
  if (type == "node") {
    data["node"] = entity_id;
  } else if (type == "resource") {
    data["resource_id"] = entity_id;
  } else return false;
  var url = get_cluster_remote_url() + "set_" + type + "_utilization";

  $.ajax({
    type: 'POST',
    url: url,
    data: data,
    timeout: pcs_timeout,
    error: function (xhr, status, error) {
      alert(
        "Unable to set utilization: "
        + ajax_simple_error(xhr, status, error)
      );
    },
    complete: function() {
      Pcs.update();
    }
  });
}

function is_integer(str) {
  if (Number(str) === str && str % 1 === 0) // if argument isn't string but number
    return true;
  var n = ~~Number(str);
  return String(n) === str;
}
