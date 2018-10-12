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

dev.patch.ajax_wrapper = function(routeFn, onDone){
  var originalFn = ajax_wrapper;
  ajax_wrapper = function(options){
    var response = routeFn(options.url);
    if(response !== undefined){
      setTimeout(function(){
        options.success(response);
        if(options.complete){
          options.complete();
        }
        onDone(options.url);
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

dev.fixture = {};

dev.fixture.report = function(severity, code, forceable){
  forceable = forceable || false;
  return {
    severity: severity,
    code: code,
    info: {},
    forceable: forceable ? "FORCE" : null,
    report_text: code.toLowerCase()+" message",
  };
};

dev.fixture.libErrorUnforcibleLarge = {
  status: "error",
  status_msg: "",
  report_list: [
    dev.fixture.report("ERROR", "SOME_CODE"),
    dev.fixture.report("WARNING", "SOME_WARNING_CODE"),
    dev.fixture.report("INFO", "SOME_INFO_CODE"),
    dev.fixture.report("ERROR", "SOME_OTHER_CODE", true),
    dev.fixture.report("DEBUG", "DEBUG_CODE"),
  ],
  data: null,
};

dev.fixture.libException = {
  status: "exception",
  status_msg: "Some exception happens",
  report_list: [],
  data: null,
};

dev.fixture.success = {
  status: "success",
  status_msg: "",
  report_list: [dev.fixture.report("INFO", "SOME_INFO_CODE")],
  data: null,
};

dev.fixture.libError = function(forcible){
  return {
    status: "error",
    status_msg: "",
    report_list: [
      dev.fixture.report("ERROR", "SOME_CODE", forcible),
    ],
    data: null,
  };
};
