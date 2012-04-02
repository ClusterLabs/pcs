function verify_remove() {
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
      modal: true, resizable: false, heigh: 140,
      buttons: {
	"Remove resource(s)": function() {
	  $('#node_list > form').submit();
	},
      Cancel: function() {
	$(this).dialog("close");
      }}
    });
  } else {
    alert("You must select at least one node.");
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
	usplit = uptime.split(",");
	uptime = usplit[0].split(" up ")[1] + usplit[1];
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
      window.setTimeout(node_update,10000);
    },
    error: function (XMLHttpRequest, textStatus, errorThrown) {
      window.setTimeout(node_update, 60000);
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
      window.setTimeout(resource_update, 10000);
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
