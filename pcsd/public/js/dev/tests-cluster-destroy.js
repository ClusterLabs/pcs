dev.patch.ajax_wrapper(
  function(url){
    switch(url){
      case "/clusters_overview":
        if(dev.flags.cluster_overview_run === undefined){
          dev.flags.cluster_overview_run = true;
          return mock.clusters_overview;
        }
      default: return undefined;
    }
  },
  function(){
    setTimeout(function(){
      $('[name="clusterid-dwarf8"]').prop('checked', true);
      clusterDestroy.dialog.create();
      setTimeout(function(){
        $("#verify_remove_submit_btn").trigger("click");
      }, 500);
    }, 2);
  },
);

testClusterDestroy = {};
testClusterDestroy.successPath = function(url, data, success, fail){
  switch(url){
    case "/managec/dwarf8/cluster_destroy": return success();
  }
};

testClusterDestroy.destroyFail403 = function(url, data, success, fail){
  switch(url){
    case "/managec/dwarf8/cluster_destroy": return fail(
      403, "Permission denied."
    );
  }
};

testClusterDestroy.destroyFail400 = function(url, data, success, fail){
  switch(url){
    case "/managec/dwarf8/cluster_destroy": return fail(
      400, "Error destroying cluster:\nout\nerrout\nretval\n"
    );
  }
};

dev.runScenario(
  // testClusterDestroy.destroyFail403
  testClusterDestroy.destroyFail400
  // testClusterDestroy.successPath
);
