var pcs_timeout = 6000;

function create_group() {
  var num_nodes = 0;
  var node_names = "";
  $("#node_list :checked").each(function (index,element) {
    num_nodes++;
    node_names += element.getAttribute("res_id") + " "
  });

  if (num_nodes == 0) {
    alert("You must select at least one resource to add to a group");
  } else {
    $("#resources_to_add_to_group").val(node_names);
    $("#add_group").dialog({title: 'Create Group',
      modal: true, resizable: false, 
      buttons: {
	"Create Group": function() {
	  $('#add_group > form').submit();
	},
      Cancel: function() {
	$(this).dialog("close");
      }}
    });
  }
}

function verify_remove(error_message, ok_message, title_message, resource_id, post_location) {
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
      var f = $('<form action="'+post_location+'" method="POST">' +
	  '<input type="hidden" name="resid-'+resource_id+'" value="1">' +
	  '</form>');
      f.appendTo($('body'));
      f.submit();
    } else {
      $('#node_list > form').submit();
    }
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
    $("#node_list :checked").each(function (index,element) {
      list_of_nodes += "<li>" + element.getAttribute("res_id")+"</li>";
      nodes_to_remove++;
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
      uptime = node_data.uptime;
      if (uptime) {
	if (!uptime) {
	  uptime = node_data.uptime;
	}
      } else {
	uptime = "Unknown";
      }
      if (node_data.noresponse) {
	setStatus($('#pacemaker_status'),2, "Unknown");
	setStatus($('#corosync_status'),2, "Unknown");
	setStatus($('#pcsd_status'),1,"Stopped");
      } else  {
	if (node_data.notauthorized) {
	  setStatus($('#pcsd_status'),1, "Not Authorized");
	} else {
	  setStatus($('#pcsd_status'),0, "Running");
	}

	if (node_data.pacemaker) {
	  setStatus($('#pacemaker_status'),0, "Running");
	} else {
	  setStatus($('#pacemaker_status'),1, "Stopped");
	}

	if (node_data.corosync) {
	  setStatus($('#corosync_status'),0, "Running");
	} else {
	  setStatus($('#corosync_status'),1, "Stopped");
	}
	

      }
      $("#uptime").html(uptime);
      window.setTimeout(remote_node_update,4000);
    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
      window.setTimeout(remote_node_update, 60000);
    }
  });
}

function local_node_update(node, data) {
  node_data = data[node];
  if ($.inArray(node,node_data.corosync_online) > -1) {
    setStatus($('#corosync_online_status'), 0, "Corosync Connected")
  } else {
    setStatus($('#corosync_online_status'), 1, "Corosync Not Connected")
  }

  if ($.inArray(node,node_data.pacemaker_online) > -1) {
    setStatus($('#pacemaker_online_status'), 0, "Pacemaker Connected")
  } else {
    setStatus($('#pacemaker_online_status'), 1, "Pacemaker Not Connected")
  }

  for (var n in data) {
    if (data[n].pacemaker_online && (jQuery.inArray(n, data[n].pacemaker_online) != -1)) {
	setNodeStatus(n, true);
    } else {
    	setNodeStatus(n,false);
    }
  }
}
      


function resource_list_setup() {
  $('.node_list_check input[type=checkbox]').click(function(e) {
    e.stopPropagation();
  });
}

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
      resource_list_setup();
      window.setTimeout(resource_list_update, 4000);
    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
      window.setTimeout(resource_list_update, 60000);
    }
  });
}

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
      window.setTimeout(resource_update, 4000);
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
  node = $("#node_info_header_title_name").text();
  $("#node_start").click(function() {
    fade_in_out("#node_start");
    $.post('/remote/cluster_start',{"name": node});
  });
  $("#node_stop").click(function() {
    fade_in_out("#node_stop");
    $.post('/remote/cluster_stop', {"name": node});
  });
}

function setup_resource_links() {
  resource = $("#node_info_header_title_name").text();
  $("#resource_delete_link").click(function () {
    verify_remove(false, false, false, [resource]);
  });
  $("#stonith_delete_link").click(function () {
    verify_remove('You must select at least one fence device.', 'Remove fence device(s)', 'Fence Device Removal', [resource], '/fencerm');
  });
  $("#resource_stop_link").click(function () {
    fade_in_out("#resource_stop_link");
    $.post('/remote/resource_stop',"resource="+resource);
  });
  $("#resource_start_link").click(function () {
    fade_in_out("#resource_start_link");
    $.post('/remote/resource_start',"resource="+resource);
  });
  $("#resource_move_link").click(function () {
    alert("Not Yet Implemented");
  });
  $("#resource_history_link").click(function () {
    alert("Noy Yet Implemented");
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
  var buttonOpts = {}

  buttonOpts["Create Cluster"] = function() {
          checkClusterNodes();
//	  $('#create_new_cluster_form').submit();
  };

  buttonOpts["Cancel"] = function() {
    $(this).dialog("close");
  };

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
  $(element).parent().siblings().toggle("slow");
  $(element).children("span, p").toggle();
}

function show_hide_constraint_tables(element) {
  $(element).siblings().hide();
  $("#add_constraint_" + $(element).val()).show();
}
