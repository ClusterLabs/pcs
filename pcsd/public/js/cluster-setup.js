clusterSetup = {dialog: {}, submit: {}, api: {}};

clusterSetup.validateFormData = function(formData){
  var errors = [];
  if(formData.clusterName == ""){
    errors.push({
      type: "error",
      msg: "You may not leave the cluster name field blank",
    });
  }
  if(formData.nodesNames.length == 0){
    errors.push({
      type: "error",
      msg: "At least one valid node must be entered.",
    });
  }
  return errors;
};

//------------------------------------------------------------------------------

clusterSetup.dialog.getNodesNames = function(){
  var nodes = [];
  $("#create_new_cluster_form tr.new_node").each(function(i, element) {
    var node = $(element).find(".node").val().trim();
    if (node.length > 0) {
      nodes.push(node);
    }
  });
  return nodes;
};

clusterSetup.dialog.getFormData = function(){
  return {
    clusterName: $('input[name^="clustername"]').val(),
    nodesNames: clusterSetup.dialog.getNodesNames(),
  };
};

clusterSetup.dialog.create = function(){
  $("#create_new_cluster").dialog({
    title: 'Create Cluster',
    modal: false,
    resizable: false,
    width: 'auto',
    buttons: [
      {
        text: "Create Cluster",
        id: "create_cluster_submit_btn",
        click: clusterSetup.submit.run,
      },
      {
        text: "Cancel",
        id: "create_cluster_cancel_btn",
        click: clusterSetup.dialog.close,
      },
    ]
  });
};

clusterSetup.dialog.close = function(){
  $("#create_new_cluster.ui-dialog-content.ui-widget-content").dialog("close");
};

clusterSetup.dialog.setSubmitAbility = function(enabled){
  $("#create_cluster_submit_btn").button("option", "disabled", ! enabled);
};

/**
  ok, noAuth, noConnect: array of node names
*/
clusterSetup.dialog.updateNodesByAuth = function(ok, noAuth, noConnect){
  $('#create_new_cluster input[name^="node-"]').each(function(){
    var nodeName = $(this).val();
    var label = $(this).parent().prev();

    var color = label.css("background-color");
    if(nodeName == "" || ok.includes(nodeName)){
      color = "";
    }else if(noConnect.includes(nodeName)){
      color = "red";
    }
    label.css("background-color", color);
  });
};

/**
  msgList:
    list of objects {type, msg} where type in error, warning, info
*/
clusterSetup.dialog.resetMessages = function(msgList){
  $("#create_new_cluster table.msg-box")
    .find(".error, .warning, .info")
    .remove()
  ;
  for(var i in msgList){
    if(!msgList.hasOwnProperty(i)){
      continue;
    }
    $("#create_new_cluster table.msg-box td").append(
      '<div class="'+msgList[i].type+'">'+tools.formatMsg(msgList[i])+"</div>"
    );
  }
};

//------------------------------------------------------------------------------

clusterSetup.submit.run = function(){
  var formData = clusterSetup.dialog.getFormData();

  var errors = clusterSetup.validateFormData(formData);
  if(errors.length > 0){
    clusterSetup.dialog.resetMessages(errors);
    return;
  }

  clusterSetup.dialog.resetMessages([]);
  clusterSetup.dialog.setSubmitAbility(false);

  var setupCoordinatingNode = formData.nodesNames[0];
  clusterSetup.submit.full(formData, setupCoordinatingNode);
};

clusterSetup.submit.onSuccess = function(){
  // Pcs.update makes sense only after success of /manage/remember-cluster -
  // it doesn't make sense to call it after success setup call.
  Pcs.update();
  clusterSetup.dialog.close();
};

clusterSetup.submit.full = function(formData, setupCoordinatingNode){
  api.checkAuthAgainstNodes(
    formData.nodesNames

  ).then(function(nodesAuthGroups){
    clusterSetup.dialog.updateNodesByAuth(
      nodesAuthGroups.ok,
      nodesAuthGroups.noAuth,
      nodesAuthGroups.noConnect,
    );

    var failNodes = nodesAuthGroups.noAuth.concat(nodesAuthGroups.noConnect);
    if(failNodes.length > 0){
      return promise.reject(api.err.AUTH_NODES_FAILED, {failNodes: failNodes});
    }

    return api.sendKnownHostsToNode(setupCoordinatingNode, formData.nodesNames);

  }).then(function(authShareResultCode){
    if(authShareResultCode !== "success"){
      return api.sendKnownHostsToNode.processErrors(
        authShareResultCode,
        setupCoordinatingNode,
      );
    }
    return api.clusterSetup(formData, setupCoordinatingNode);

  }).then(function(setupResult){
    return setupResult.status !== api.reports.statuses.success
      ? api.clusterSetup.processErrors(
          setupResult,
          formData,
          setupCoordinatingNode
        )
      : api.remember(formData.clusterName, formData.nodesNames)
    ;

  }).then(
    clusterSetup.submit.onSuccess
  ).fail(
    clusterSetup.submit.onError
  );
};

clusterSetup.submit.force = function(formData, setupCoordinatingNode){
  api.clusterSetup(
    formData,
    setupCoordinatingNode,
    true,

  ).then(function(setupResult){
    return setupResult.status !== api.reports.statuses.success
      ? api.clusterSetup.processErrors(
          setupResult,
          formData,
          setupCoordinatingNode
        )
      : api.remember(formData.clusterName, formData.nodesNames)
    ;
  }).then(
    clusterSetup.submit.onSuccess
  ).fail(
    clusterSetup.submit.onError
  );
};

clusterSetup.submit.onCallFail = function(XMLHttpRequest){
  if(XMLHttpRequest.status === 403){
    clusterSetup.dialog.resetMessages([
      {type: "error", msg: "The user 'hacluster' is required for this action."},
    ]);
  }else{
    alert(
      "Server returned an error: "+XMLHttpRequest.status
      +" "+XMLHttpRequest.responseText
    );
  }
};

clusterSetup.submit.onError = function(rejectCode, data){
  clusterSetup.dialog.setSubmitAbility(true);
  switch(rejectCode){
    case api.err.NODES_AUTH_CHECK:
      alert("ERROR: Unable to contact server");
      break;

    case api.err.AUTH_NODES_FAILED:
      auth_nodes_dialog(data.failNodes, clusterSetup.submit);
      break;

    case api.err.SEND_KNOWN_HOST_CALL_FAILED:
      clusterSetup.submit.onCallFail(data.XMLHttpRequest);
      break;

    case api.err.SEND_KNOWN_HOSTS_ERROR:
      clusterSetup.dialog.resetMessages([{type: "error", msg: data.message}]);
      break;

    case api.err.CLUSTER_SETUP_CALL_FAILED:
      clusterSetup.submit.onCallFail(data.XMLHttpRequest);
      break;

    case api.err.CLUSTER_SETUP_FAILED:
      clusterSetup.dialog.resetMessages(data.msgList);
      break;

    case api.err.CLUSTER_SETUP_FAILED_FORCIBLE:
      if (confirm(
        "Unable to setup cluster \n\n"
        + data.msgList
          .map(function(msg){return tools.formatMsg(msg)})
          .join("\n")
        + "\n\nDo you want to force the operation?"
      )) {
        clusterSetup.submit.force(data.setupData, data.setupCoordinatingNode);
      } else {
        clusterSetup.dialog.close();
      }
      break;

    case api.err.CLUSTER_SETUP_EXCEPTION:
      alert("Server returned an error: "+data.msg);
      break;

    case api.err.REMEMBER_CLUSTER_CALL_FAILED:
      // 403 makes not sense here. It would failed on
      // SEND_KNOWN_HOST_CALL_FAILED or on CLUSTER_SETUP_CALL_FAILED if the
      // user is not "hacluster". So we use standard mechanism here without
      // extra notice that cluster was setup and only remember-cluster failed.
      clusterSetup.submit.onCallFail(data.XMLHttpRequest);
      break;
  }
};
