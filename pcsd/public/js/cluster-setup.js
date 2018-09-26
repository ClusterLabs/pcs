clusterSetup = {dialog: {}};

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
        click: clusterSetup.submit,
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
  messageList:
    list of objects {type, msg} where type in error, warning, info
*/
clusterSetup.dialog.resetMessages = function(msgList){
  $("#create_new_cluster table.msg-box")
    .find(".error, .warning, .info")
    .remove()
  ;
  for(var i in msgList){
    if(msgList.hasOwnProperty(i)){
      $("#create_new_cluster table.msg-box td").append(
        '<div class="'+msgList[i].type+'">'
          +tools.string.upperFirst(msgList[i].type)+": "+msgList[i].msg
          +"</div>"
      );
    }
  }
};

clusterSetup.dialog.setErrors = function(msgList){
  clusterSetup.dialog.resetMessages(msgList.map(function(msg){
    return {type: "error", msg: msg};
  }));
};

clusterSetup.submit = function(){
  // TODO JSON.parse can fail
  var formData = clusterSetup.dialog.getFormData();

  var errors = clusterSetup.validateFormData(formData);
  if(errors.length > 0){
    clusterSetup.dialog.setErrors(errors);
    return;
  }

  clusterSetup.dialog.setErrors([]);
  clusterSetup.dialog.setSubmitAbility(false);

  var targetNode = formData.nodesNames[0];

  var err = {
    NODES_AUTH_CHECK: "NODES_AUTH_CHECK",
    AUTH_NODES_FAILED: "AUTH_NODES_FAILED",
    SEND_KNOWN_HOST_CALL_FAILED: "SEND_KNOWN_HOST_CALL_FAILED",
    SEND_KNOWN_HOSTS_ERROR: "SEND_KNOWN_HOSTS_ERROR",
    CLUSTER_SETUP_CALL_FAILED: "CLUSTER_SETUP_CALL_FAILED",
    CLUSTER_SETUP_FAILED: "CLUSTER_SETUP_FAILED",
    REMEMBER_CLUSTER_CALL_FAILED: "REMEMBER_CLUSTER_CALL_FAILED",
  };

  var severityMsgTypeMap = {
    ERROR: "error",
    WARNING: "warning",
    INFO: "info",
  };

  promise.get(
    "/manage/check_auth_against_nodes",
    {"node_list": formData.nodesNames},
    err.NODES_AUTH_CHECK,

  ).then(function(nodesAuthData){
    var nodesStatus = clusterSetup.nodesAuthStatus(JSON.parse(nodesAuthData));
    clusterSetup.dialog.updateNodesByAuth(
      nodesStatus.ok,
      nodesStatus.noAuth,
      nodesStatus.noConnect,
    );

    var failNodes = nodesStatus.noAuth.concat(nodesStatus.noConnect);
    if(failNodes.length > 0){
      return promise.reject(err.AUTH_NODES_FAILED, {failNodes: failNodes});
    }

    return promise.post(
      "/manage/send-known-hosts-to-node",
      {
        target_node: targetNode,
        "node_names[]": formData.nodesNames,
      },
      err.SEND_KNOWN_HOST_CALL_FAILED,
    );

  }).then(function(authShareResult){
    if(authShareResult !== "success"){
      var codeMessageMap = {
        "error":
          "Error during sharing authentication with node '"+targetNode+"'"
        ,
        "not_supported":
          "Sharing authentication with node '"+targetNode+"' not supported"
        ,
      };
      return promise.reject(err.SEND_KNOWN_HOSTS_ERROR, {
        message: codeMessageMap[authShareResult] !== undefined
          ? codeMessageMap[authShareResult]
          : "Unknown sharing authentication with node '"+targetNode
            +"' result: '"+authShareResult+"'"
        ,
      });
    }
    return promise.post(
      "/manage/cluster-setup",
      {
        target_node: targetNode,
        setup_data: JSON.stringify({
          cluster_name: formData.clusterName,
          nodes: formData.nodesNames.map(function(nodeName){
            return {name: nodeName};
          }),
          transport_type: "knet",
          transport_options: {},
          link_list: [],
          compression_options: {},
          crypto_options: {},
          totem_options: {},
          quorum_options: {},
        }),
      },
      err.CLUSTER_SETUP_CALL_FAILED,
    );

  }).then(function(setupResultsString){
    var setupResults = JSON.parse(setupResultsString);
    if(setupResults.status != "success"){
      return promise.reject(err.CLUSTER_SETUP_FAILED, {
        messageList: setupResults.report_list
          .filter(function(report){
            return Object.keys(severityMsgTypeMap).includes(report.severity);
          })
          .map(function(report){
            return {
              type: severityMsgTypeMap[report.severity],
              msg: report.report_text,
            };
          })
        ,
      });
    }

    return promise.post(
      "/manage/remember-cluster",
      {
        cluster_name: formData.clusterName,
        "nodes[]": formData.nodesNames,
      },
      err.REMEMBER_CLUSTER_CALL_FAILED,
    );

  }).then(function(){
    // Pcs.update makes sense only after success of /manage/remember-cluster.
    Pcs.update();
    clusterSetup.dialog.close();
    // alert("Setup of cluster '"+formData.clusterName+"' is successful");

  }).fail(function(rejectCode, data){
    clusterSetup.dialog.setSubmitAbility(true);
    switch(rejectCode){
      case err.NODES_AUTH_CHECK:
        alert("ERROR: Unable to contact server");
        break;

      case err.AUTH_NODES_FAILED:
        auth_nodes_dialog(data.failNodes, clusterSetup.submit);
        break;

      case err.SEND_KNOWN_HOST_CALL_FAILED:
        clusterSetup.onCallFail(data.XMLHttpRequest);
        break;

      case err.SEND_KNOWN_HOSTS_ERROR:
        clusterSetup.dialog.setErrors([data.message]);
        break;

      case err.CLUSTER_SETUP_CALL_FAILED:
        clusterSetup.onCallFail(data.XMLHttpRequest);
        break;

      case err.CLUSTER_SETUP_FAILED:
        clusterSetup.dialog.resetMessages(data.messageList);
        break;

      case err.REMEMBER_CLUSTER_CALL_FAILED:
        // 403 makes not sense here. It would failed on
        // SEND_KNOWN_HOST_CALL_FAILED or on CLUSTER_SETUP_CALL_FAILED if the
        // user is not "hacluster". So we use standard mechanism here without
        // extra notice that cluster was setup and only remember-cluster failed.
        clusterSetup.onCallFail(data.XMLHttpRequest);
        break;
    }
  });
};

clusterSetup.validateFormData = function(formData){
  var errors = [];
  if(formData.clusterName == ""){
    errors.push("You may not leave the cluster name field blank");
  }
  if(formData.nodesNames.length == 0){
    errors.push("At least one valid node must be entered.");
  }
  return errors;
};

clusterSetup.nodesAuthStatus = function(nodes_auth_status_response){
  var status = {
    ok: [],
    noAuth: [],
    noConnect: [],
  };

  for (var name in nodes_auth_status_response) {
    if( ! nodes_auth_status_response.hasOwnProperty(name)){
      continue;
    }
    switch(nodes_auth_status_response[name]){
      case "Online": status.ok.push(name); break;
      case "Unable to authenticate": status.noAuth.push(name); break;
      default: status.noConnect.push(name); break;
    }
  }

  return status;
};

clusterSetup.onCallFail = function(XMLHttpRequest){
  if(XMLHttpRequest.status === 403){
    clusterSetup.dialog.setErrors([
      "The user 'hacluster' is required for this action.",
    ]);
  }else{
    alert(
      "Server returned an error: "+XMLHttpRequest.status
      +" "+XMLHttpRequest.responseText
    );
  }
};
