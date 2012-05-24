function create_group() {
  var num_nodes = 0;
  var node_names = "";
  $("#node_list :checked").each(function (index,element) {
    num_nodes++;
    node_names += element.getAttribute("res_id") + " "
  });

  if (num_nodes == 0) {
    alert("You must select at least one node to add to a group");
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

function verify_remove(error_message, ok_message) {
  if (!error_message)
    error_message = "You must select at least one node.";
  if (!ok_message)
    ok_message = "Remove resource(s)";

  var buttonOpts = {}
  buttonOpts[ok_message] = function() {
	  $('#node_list > form').submit();
  };
  buttonOpts["Cancel"] = function() {
    $(this).dialog("close");
  };

  var list_of_nodes = "<ul>";
  var nodes_to_remove = 0;
  $("#node_list :checked").each(function (index,element) {
    list_of_nodes += "<li>" + element.getAttribute("res_id")+"</li>";
    nodes_to_remove++;
  });
  list_of_nodes += "</ul>";
  if (nodes_to_remove != 0) {
    $("#resource_to_remove").html(list_of_nodes);
    $("#verify_remove").dialog({title: 'Resource Removal',
      modal: true, resizable: false,
      buttons: buttonOpts
    });
  } else {
    alert(error_message);
  }
}

function node_update() {
  node = $('#node_info_header_title_name').first().text();
  $.ajax({
    type: 'GET',
    url: '/remote/status?node='+node,
    timeout: 2000,
    success: function (data) {
      data = jQuery.parseJSON(data);
      uptime = data.uptime;
      if (uptime) {
	if (!uptime) {
	  uptime = data.uptime;
	}
      } else {
	uptime = "Unknown";
      }
      if (data.noresponse) {
	pcsd_status = "Stopped";
	pacemaker_status = "Unknown";
	corosync_status = "Unknown";
	setStatus($('#pacemaker_status'),false);
	setStatus($('#corosync_status'),false);
	setStatus($('#pcsd_status'),false);
      } else  {
	pcsd_status = "Running";
	setStatus($('#pcsd_status'),true);

	if (data.pacemaker) {
	  pacemaker_status = "Running";
	  setStatus($('#pacemaker_status'),true);
	} else {
	  pacemaker_status = "Stopped";
	  setStatus($('#pacemaker_status'),false);
	}

	if (data.corosync) {
	  corosync_status = "Running";
	  setStatus($('#corosync_status'),true);
	} else {
	  corosync_status = "Stopped";
	  setStatus($('#corosync_status'),false);
	}
      }
      mydata = data;
      $("#uptime").html(uptime);
      $("#pacemaker_status").html(pacemaker_status);
      $("#corosync_status").html(corosync_status);
      $("#pcsd_status").html(pcsd_status);
      window.setTimeout(node_update,4000);
    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
      window.setTimeout(node_update, 60000);
    }
  });
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
    timeout: 2000,
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
    timeout: 2000,
    success: function(data) {
      data = jQuery.parseJSON(data);
      $("#cur_res_loc").html(data.location);
      $("#res_status").html(data.status);
      if (data.status == "Running") {
	setStatus($("#res_status"), true);
      } else {
	setStatus($("#res_status"), false);
      }
      window.setTimeout(resource_update, 4000);
    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
      window.setTimeout(resource_update, 60000);
    }
  });
}

function setStatus(item,running) {
  if (running) {
    item.removeClass();
    item.addClass('status');
  } else {
    item.removeClass();
    item.addClass('status-offline');
  }
}

function setup_node_links() {
  node = $("#node_info_header_title_name").text();
  $("#node_start").click(function() {
    $.post('/remote/cluster_start',{"name": node});
  });
  $("#node_stop").click(function() {
    $.post('/remote/cluster_stop', {"name": node});
  });
}

function setup_resource_links() {
  resource = $("#node_info_header_title_name").text();
  $("#resource_delete_link").click(function () {
    $.post('/resourcerm',"resid-"+resource+"=1");
  });
  $("#resource_stop_link").click(function () {
    $.post('/remote/resource_stop',"resource="+resource);
    alert("Stopping Resource");
  });
  $("#resource_start_link").click(function () {
    $.post('/remote/resource_start',"resource="+resource);
    alert("Starting Resource");
  });
  $("#resource_move_link").click(function () {
    alert("Not Yet Implemented");
  });
  $("#resource_history_link").click(function () {
    alert("Noy Yet Implemented");
  });
}

function checkClusterNodes() {
  var nodes = [];
  $('input[name^="node-"]').each(function(i,e) {
    if (e.value != "") {
      nodes.push(e.value)
    }
  });

  $.post('/remote/check_gui_status',{"nodes": nodes.join(",")});
  $.ajax({
    type: 'POST',
    url: '/remote/check_gui_status',
    data: {"nodes": nodes.join(",")},
    timeout: 2000,
    success: function (data) {
      mydata = jQuery.parseJSON(data);
      update_create_cluster_dialog(mydata);

    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
      alert("ERROR: Unable to contact server");
    }
  });
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
