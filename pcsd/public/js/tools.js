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

promise.post = function(url, data, rejectCode, options){
  options = options || {};
  options.type = 'POST';
  options.url = url;
  options.data = data;

  return promise.ajax(options, rejectCode);
};

promise.reject = function(){
  var dfd = $.Deferred();
  return dfd.reject.apply(dfd, arguments);
};

promise.resolve = function(){
  var dfd = $.Deferred();
  return dfd.resolve.apply(dfd, arguments);
};

tools = {string: {}, dialog: {}, submit: {}};

tools.string.upperFirst = function(string){
  return string.charAt(0).toUpperCase() + string.slice(1);
};

tools.string.escape = Handlebars.Utils.escapeExpression;

/**
  msg:
    list of objects {type, msg} where type in error, warning, info
*/
tools.dialog.resetMessages = function(dialogSelector){
  return function(msgList){
    msgBoxElement = $(dialogSelector+" table.msg-box");
    msgBoxElement.find(".error, .warning, .info").remove();
    for(var i in msgList){
      if(!msgList.hasOwnProperty(i)){
        continue;
      }
      msgBoxElement.find("td").append(
        '<div class="'+msgList[i].type+'">'
          +tools.string.escape(tools.formatMsg(msgList[i]))
          +"</div>"
      );
    }
  };
};

tools.dialog.setActionAbility = function(buttonSelector){
  return function(enabled){
    $(buttonSelector).button("option", "disabled", ! enabled);
  };
};

tools.dialog.close = function(dialogSelector, closeType){
  closeType = closeType || "close";
  return function(){
    $(dialogSelector+".ui-dialog-content.ui-widget-content").dialog(closeType);
  };
};

tools.dialog.inputsToArray = function(inputSelector){
  var values = [];
  $(inputSelector).each(function(i, element) {
    var value = $(element).val().trim();
    if (value.length > 0) {
      values.push(value);
    }
  });
  return values;
};

tools.dialog.resetInputs = function(selector){
  $(selector).each(function(i, element) {
    $(element).val("");
  });
};

tools.submit.onCallFail = function(resetMessages){
  return function(XMLHttpRequest, dialogCodes){
    dialogCodes = dialogCodes || [];
    if(XMLHttpRequest.status === 403){
      resetMessages([
        {
          type: "error",
          msg: "The user 'hacluster' is required for this action.",
        },
      ]);
    }else if(dialogCodes.includes(XMLHttpRequest.status)){
      resetMessages(
        XMLHttpRequest.responseText.split("\n").map(function(line){
          return { type: "error", msg: line };
        })
      );
    }else{
      alert(
        "Server returned an error: "+XMLHttpRequest.status
        +"\n"+XMLHttpRequest.responseText
      );
    }
  };
};

tools.submit.confirmForce = function(actionDesc, msgList){
  return confirm(
    "Unable to "+actionDesc+" \n\n"
    + msgList
      .map(function(msg){return tools.formatMsg(msg)})
      .join("\n")
    + "\n\nDo you want to force the operation?"
  );
};

tools.formatMsg = function(msg){
  return tools.string.upperFirst(msg.type)+": "+msg.msg;
};
