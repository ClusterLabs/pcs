promise = {};

promise.ajax = function(options, rejectCode){
  var dfd = $.Deferred();
  options.success = function(data){
    dfd.resolve(data);
  };
  options.error = function(XMLHttpRequest, textStatus, errorThrown){
    dfd.reject(rejectCode, {
      XMLHttpRequest: XMLHttpRequest,
      textStatus: textStatus,
      errorThrown: errorThrown,
    });
  };
  if(options.timeout === undefined){
    options.timeout = pcs_timeout;
  }
  ajax_wrapper(options);
  return dfd.promise();
};

promise.get = function(url, data, rejectCode){
  return promise.ajax(
    {
      type: 'GET',
      url: url,
      data: data,
    },
    rejectCode,
  );
};

promise.post = function(url, data, rejectCode){
  return promise.ajax(
    {
      type: 'POST',
      url: url,
      data: data,
    },
    rejectCode,
  );
};

promise.reject = function(){
  var dfd = $.Deferred();
  return dfd.reject.apply(dfd, arguments);
};

promise.resolve = function(){
  var dfd = $.Deferred();
  return dfd.resolve.apply(dfd, arguments);
};

tools = {string: {}};

tools.string.upperFirst = function(string){
  return string.charAt(0).toUpperCase() + string.slice(1);
};
