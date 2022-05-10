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
    setTimeout(function(){
      $('#node_list .node_list_check input').prop('checked', true);
      nodesRemove.dialog.create();
      setTimeout(function(){
        $("#verify_remove_submit_btn").trigger("click");
      }, 500);
    }, 2);
  },
);

testNodesRemove = {};

testNodesRemove.successPath = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_remove_nodes": return success(
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
  }
};

testNodesRemove.nodesRemove403 = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_remove_nodes": return fail(
      403, "Permission denied."
    );
  }
};

testNodesRemove.nodesRemove500 = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_remove_nodes": return fail(
      500, "Something is wrong"
    );
  }
};

testNodesRemove.nodesRemoveUnforcible = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_remove_nodes": return success(
      JSON.stringify(dev.fixture.libErrorUnforcibleLarge)
    );
  }
};

testNodesRemove.nodesRemoveUnforcibleSpecificTranslation = function(
  url, data, success, fail
){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_remove_nodes": return success(
      JSON.stringify({
        status: "error",
        status_msg: "",
        report_list: [
          dev.fixture.report("ERROR", "CANNOT_REMOVE_ALL_CLUSTER_NODES"),
        ],
        data: null,
      })
    );
  }
};

testNodesRemove.nodesRemoveException = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_remove_nodes": return success(
      JSON.stringify(dev.fixture.libException)
    );
  }
};

testNodesRemove.nodesRemoveForceFail = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_remove_nodes": return success(
      JSON.stringify(
        dev.fixture.libError(JSON.parse(data.data_json).force_flags.length < 1)
      )
    );
  }
};

testNodesRemove.nodesRemoveForceFailForcible = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_remove_nodes": return success(
      JSON.stringify(dev.fixture.libError(true)),
    );
  }
};

testNodesRemove.nodesRemoveForce = function(url, data, success, fail){
  switch(url){
    case "/managec/"+Pcs.cluster_name+"/cluster_remove_nodes":
      if (JSON.parse(data.data_json).force_flags.length < 1) {
        return success(JSON.stringify(dev.fixture.libError(true)));
      }
    default:
      return testNodesRemove.successPath(url, data, success, fail);
  }
};


dev.runScenario(
  // testNodesRemove.nodesRemove403
  // testNodesRemove.nodesRemove500
  // testNodesRemove.nodesRemoveUnforcible
  // testNodesRemove.nodesRemoveUnforcibleSpecificTranslation
  // testNodesRemove.nodesRemoveException
  // testNodesRemove.nodesRemoveForceFail
  // testNodesRemove.nodesRemoveForceFailForcible
  // testNodesRemove.nodesRemoveForce
  testNodesRemove.successPath
);
