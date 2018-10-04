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
        console.log("REQUEST DATA:");
        console.log(requestData);
        console.log("RESPONSE DATA:");
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
        console.log("REQUEST DATA:");
        console.log(requestData);
        console.log("RESPONSE STATUS:");
        console.log(status);
        console.log("RESPONSE TEXT:");
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
      options.data,
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

dev.scenario = {};
dev.runScenario = function(scenario){
  dev.patch.promise_ajax(scenario);
};
