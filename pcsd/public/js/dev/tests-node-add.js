dev.patch.ajax_wrapper(
  function(url){
    switch(url){
      case "cluster_status":
        if(dev.flags.cluster_status_run === undefined){
          dev.flags.cluster_status_run = true;
          console.group('Wrapping ajax_wrapper');
          console.log(url);
          console.groupEnd();
          console.log(mock.cluster_status);
          return mock.cluster_status;
        }
      default: return undefined;
    }
  },
  function(){
    nodeAdd.dialog.create();
    $('#add_node input[name="new_nodename"]').val("dave8");
    add_sbd_device_textbox();
    add_sbd_device_textbox();
    var devices = ["first", "second", "third"];
    $("#add_node_selector .add_node_sbd_device [name='devices[]']").each(
      function(i, input){
        $(input).val(devices[i]);
      }
    );
    setTimeout(function(){ nodeAdd.submit.run() }, 500);
  },
);

testNodeAdd = {};

testNodeAdd.successPath = function(url, data, success, fail){
  switch(url){
    case "/manage/can-add-cluster-or-nodes": return success();
    case "/manage/check_auth_against_nodes": return success(JSON.stringify({
      dave8: "Online",
    }));
    case "/managec/"+Pcs.cluster_name+"/send-known-hosts": return success(
      "success"
    );
    case "/managec/"+Pcs.cluster_name+"/cluster_add_nodes": return success(
      JSON.stringify({
        status: "success",
        status_msg: "",
        report_list: [
          {
            severity: "INFO",
            code: "SOME_INFO_CODE",
            info: {},
            forceable: null,
            report_text: "Information. In formation. Inf or mation",
          },
        ],
        data: null,
      })
    );
    case "/managec/"+Pcs.cluster_name+"/cluster_start": return success();
  }
};

testNodeAdd.canAddClusterOrNodes403 = function(url, data, success, fail){
  switch(url){
    case "/manage/can-add-cluster-or-nodes": return fail(
      403, "Permission denied."
    );
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testNodeAdd.canAddClusterOrNodes500 = function(url, data, success, fail){
  switch(url){
    case "/manage/can-add-cluster-or-nodes": return fail(
      500, "Something is wrong",
    );
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testNodeAdd.canAddClusterOrNodes400 = function(url, data, success, fail){
  switch(url){
    case "/manage/can-add-cluster-or-nodes": return fail(
      400,
      "The node 'node_name' is already a part of the 'cluster_name' cluster."
      +" You may not add a node to two different clusters."
    );
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testNodeAdd.checkAuthFails = function(url, data, success, fail){
  switch(url){
    case "/manage/check_auth_against_nodes": return fail();
  }
};

testNodeAdd.checkAuthNodesNotAuth = function(url, data, success, fail){
  switch(url){
    case "/manage/check_auth_against_nodes": return success(JSON.stringify({
      dave8: "Unable to authenticate",
    }));
  }
};

testNodeAdd.sendKnownHostsFail = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/send-known-hosts": return fail();
    default:
      return testNodeAdd.successPath(url, data, success, fail);
  }
};

testNodeAdd.sendKnownHosts403 = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/send-known-hosts": return fail(
      403, "Permission denied."
    );
    default:
      return testNodeAdd.successPath(url, data, success, fail);
  }
};

testNodeAdd.sendKnownHostsError = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/send-known-hosts": return success(
      "error"
    );
    default:
      return testNodeAdd.successPath(url, data, success, fail);
  }
};

testNodeAdd.sendKnownHostsNotSupported = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/send-known-hosts": return success(
      "not_supported"
    );
    default:
      return testNodeAdd.successPath(url, data, success, fail);
  }
};

testNodeAdd.sendKnownHostsFailUnknown = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/send-known-hosts": return success(
      "unknown"
    );
    default:
      return testNodeAdd.successPath(url, data, success, fail);
  }
};

testNodeAdd.nodeAdd403 = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_add_nodes": return fail(
      403, "Permission denied."
    );
    default:
      return testNodeAdd.successPath(url, data, success, fail);
  }
};
testNodeAdd.nodeAdd500 = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_add_nodes": return fail(
      500, "Something is wrong",
    );
    default:
      return testNodeAdd.successPath(url, data, success, fail);
  }
};
testNodeAdd.nodeAddUnforcible = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_add_nodes": return success(
      JSON.stringify(dev.fixture.libErrorUnforcibleLarge)
    );
    default:
      return testNodeAdd.successPath(url, data, success, fail);
  }
};

testNodeAdd.nodeAddException = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_add_nodes": return success(
      JSON.stringify(dev.fixture.libException)
    );
    default:
      return testNodeAdd.successPath(url, data, success, fail);
  }
};

testNodeAdd.nodeAddForceFail = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_add_nodes":
      return success(JSON.stringify(
        dev.fixture.libError(JSON.parse(data.data_json).force_flags.length < 1)
      ));
    default:
      return testNodeAdd.successPath(url, data, success, fail);
  }
};

testNodeAdd.nodeAddForceFailForcible = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_add_nodes":
      return success(JSON.stringify(dev.fixture.libError(true)));
    default:
      return testNodeAdd.successPath(url, data, success, fail);
  }
};

testNodeAdd.nodeAddForce = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_add_nodes":
      if (JSON.parse(data.data_json).force_flags.length < 1) {
        return success(JSON.stringify(dev.fixture.libError(true)));
      }
    default:
      return testNodeAdd.successPath(url, data, success, fail);
  }
};

testNodeAdd.nodeStartClusterFail = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_start": return fail(
      500, "Server error"
    );
    default:
      return testNodeAdd.successPath(url, data, success, fail);
  }
};


dev.runScenario(
  // testNodeAdd.canAddClusterOrNodes403
  // testNodeAdd.canAddClusterOrNodes500
  // testNodeAdd.canAddClusterOrNodes400
  // testNodeAdd.checkAuthFails
  // testNodeAdd.checkAuthNodesNotAuth
  // testNodeAdd.sendKnownHostsFail
  // testNodeAdd.sendKnownHosts403
  // testNodeAdd.sendKnownHostsError
  // testNodeAdd.sendKnownHostsNotSupported
  // testNodeAdd.sendKnownHostsFailUnknown
  // testNodeAdd.nodeAdd403
  // testNodeAdd.nodeAdd500
  // testNodeAdd.nodeAddUnforcible
  // testNodeAdd.nodeAddException
  // testNodeAdd.nodeAddForceFail
  // testNodeAdd.nodeAddForceFailForcible
  // testNodeAdd.nodeAddForce
  // testNodeAdd.nodeStartClusterFail
  testNodeAdd.successPath
);
