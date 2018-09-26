dev = {
  flags: {},
  promise: {},
  patch: {},
  utils: {},
};

dev.promise.success = function(url, requestData){
  return function(responseData){
    console.group('Ajax sent: '+url);
    console.log(requestData);
    console.groupEnd();

    var dfd = $.Deferred();
    setTimeout(
      function(){
        console.group('Ajax succeeded: '+url);
        console.log(requestData);
        console.log(responseData);
        console.groupEnd();
        dfd.resolve(responseData);
      },
      100
    );
    return dfd.promise();
  };
};

dev.promise.fail = function(url, requestData, rejectCode){
  return function(status, responseText){
    console.group('Ajax sent: '+url);
    console.log(requestData);
    console.groupEnd();

    var dfd = $.Deferred();
    setTimeout(
      function(){
        console.group('Ajax failed: '+url);
        console.log(requestData);
        console.log(status);
        console.log(responseText);
        console.groupEnd();
        dfd.reject(rejectCode, {
          XMLHttpRequest: {
            status: status,
            responseText: responseText,
          }
        });
      },
      100
    );
    return dfd.promise();
  };
};

dev.patch.promise_ajax = function(routeFn){
  promise.ajax = function(options, rejectCode){
    var promise = routeFn(
      options.url,
      dev.promise.success(options.url, options.data),
      dev.promise.fail(options.url, options.data, rejectCode),
    );
    if( ! promise){
      throw new Error("Unknown url: "+options.url);
    }
    return promise;
  };
};

dev.patch.ajax_wrapper = function(routeFn){
  var originalFn = ajax_wrapper;
  ajax_wrapper = function(options){
    var response = routeFn(options.url);
    if(response !== undefined){
      setTimeout(function(){
        options.success(response);
        if(options.complete){
          options.complete();
        }
        dev.utils.clusterSetupDialog.prefill();
      }, 200);
    }else{
      originalFn(options);
    }
  };
};

dev.patch.ajax_wrapper(function(url){
  switch(url){
    case "/clusters_overview":
      if(dev.flags.cluster_overview_run === undefined){
        dev.flags.cluster_overview_run = true;
        console.group('Wrapping ajax_wrapper');
        console.log(url);
        console.groupEnd();
        return mock.clusters_overview;
      }
    default: return undefined;
  }
});

// dev.patch.promise_ajax(function(url, success, fail){
//   switch(url){
//     case "/manage/check_auth_against_nodes": return success(JSON.stringify({
//       dave8: "Online",
//       kryten8: "Online",
//       holly8: "Online",
//       // kryten8: "Unable to authenticate",
//       // holly8: "Cant connect",
//     }));
//     // case "/manage/check_auth_against_nodes": return fail();
//     case "/manage/send-known-hosts-to-node": return success("success");
//     // case "/manage/send-known-hosts-to-node": return fail(
//     //   403, "Permission denied."
//     // );
//     case "/manage/cluster-setup": return success(JSON.stringify({
//       status: "success",
//       status_msg: "",
//       report_list: [
//         {
//           severity: "WARNING",
//           code: "SOME_WARNING_CODE",
//           info: {},
//           forceable: null,
//           report_text: "Another warning appeared",
//         },
//         {
//           severity: "ERROR",
//           code: "SOME_CODE",
//           info: {},
//           forceable: null,
//           report_text: "Error happens",
//         },
//         {
//           severity: "INFO",
//           code: "SOME_INFO_CODE",
//           info: {},
//           forceable: null,
//           report_text: "Information. In formation. Inf or mation",
//         },
//         {
//           severity: "ERROR",
//           code: "SOME_OTHER_CODE",
//           info: {},
//           forceable: null,
//           report_text: "Another error happens",
//         },
//       ],
//       data: null,
//     }));
//     // case "/manage/cluster-setup": return fail(403, "Permission denied.");
//     case "/manage/remember-cluster": return success();
//     // case "/manage/remember-cluster": return fail(
//     //   400,
//     //   "Configuration conflict detected."
//     //     +"\n\nSome nodes had a newer configuration than the local node."
//     //     +" Local node's configuration has been updated."
//     //     +" Please add the cluster manually if appropriate."
//     // );
//     // case "/manage/remember-cluster": return fail(403, "Permission denied.");
//   }
// });
//
// dev.utils.clusterSetupDialog = {
//   wasRun: false,
//   prefill: function(){
//     if(dev.utils.clusterSetupDialog.wasRun){
//       return;
//     }
//     dev.utils.clusterSetupDialog.wasRun = true;
//     clusterSetup.dialog.create();
//     $('input[name^="clustername"]').val("starbug8");
//     $('#create_new_cluster input[name="node-1"]').val("dave8");
//     $('#create_new_cluster input[name="node-2"]').val("kryten8");
//     $('#create_new_cluster input[name="node-3"]').val("holly8");
//   },
// };
