clusterSetup = {dialog: {}, submit: {}};

clusterSetup.validateFormData = function(formData){
  var errors = [];
  if(formData.clusterName == ""){
    errors.push({
      type: "error",
      msg: "You may not leave the cluster name field blank.",
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

clusterSetup.dialog.getFormData = function(){
  return {
    clusterName: $('input[name^="clustername"]').val().trim(),
    nodesNames: tools.dialog.inputsToArray(
      "#create_new_cluster_form tr.new_node [name^='node-']"
    ),
    autoStart: $("#create_new_cluster_form [name='auto_start']").is(":checked"),
  };
};

clusterSetup.dialog.reset = function(){
  $('input[name^="clustername"]').val("");
  tools.dialog.resetInputs(
    "#create_new_cluster_form tr.new_node [name^='node-']"
  );
};

clusterSetup.dialog.create = function(){
  $("#create_new_cluster").dialog({
    title: 'Create Cluster',
    closeOnEscape: false,
    dialogClass: "no-close",
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

clusterSetup.dialog.close = tools.dialog.close("#create_new_cluster");

clusterSetup.dialog.setSubmitAbility = tools.dialog.setActionAbility(
  "#create_cluster_submit_btn"
);

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

clusterSetup.dialog.resetMessages = tools.dialog.resetMessages(
  "#create_new_cluster"
);

//------------------------------------------------------------------------------
//
clusterSetup.submit.onCallFail = tools.submit.onCallFail(
  clusterSetup.dialog.resetMessages
);

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

  api.canAddClusterOrNodes(
    formData.nodesNames,
    formData.clusterName,

  ).then(function(){
    return api.checkAuthAgainstNodes(formData.nodesNames);

  }).then(function(nodesAuthGroups){
    clusterSetup.dialog.updateNodesByAuth(
      nodesAuthGroups.ok,
      nodesAuthGroups.noAuth,
      nodesAuthGroups.noConnect,
    );

    var failNodes = nodesAuthGroups.noAuth.concat(nodesAuthGroups.noConnect);
    if(failNodes.length > 0){
      return promise.reject(
        api.err.NODES_AUTH_CHECK.WITH_ERR_NODES,
        {failNodes: failNodes},
      );
    }

    return api.sendKnownHostsToNode(setupCoordinatingNode, formData.nodesNames);

  }).then(function(){
    return api.clusterSetup(
      { setupData: formData, setupCoordinatingNode: setupCoordinatingNode },
      {
        confirm: function(msgs){
          return tools.submit.confirmForce("setup cluster", msgs);
        },
      }
    );

  }).then(function(){
    return api.rememberCluster(formData.clusterName, formData.nodesNames);

  }).then(function(){
    if (formData.autoStart) {
      return api.clusterStart(formData.clusterName, { all: true });
    }

  }).then(function(){
    Pcs.update();
    clusterSetup.dialog.reset();
    clusterSetup.dialog.close();

  }).fail(function(rejectCode, data){
    clusterSetup.dialog.setSubmitAbility(true);
    switch(rejectCode){
      case api.err.CAN_ADD_CLUSTER_OR_NODES.FAILED:
        clusterSetup.submit.onCallFail(data.XMLHttpRequest, [400]);
        break;

      case api.err.NODES_AUTH_CHECK.FAILED:
        alert("ERROR: Unable to contact server");
        break;

      case api.err.NODES_AUTH_CHECK.WITH_ERR_NODES:
        auth_nodes_dialog(data.failNodes, clusterSetup.submit.run);
        break;

      case api.err.SEND_KNOWN_HOSTS.FAILED:
        clusterSetup.submit.onCallFail(data.XMLHttpRequest);
        break;

      case api.err.SEND_KNOWN_HOSTS.PCSD_ERROR:
        clusterSetup.dialog.resetMessages([{type: "error", msg: data.message}]);
        break;

      case api.err.CLUSTER_SETUP.FAILED:
        clusterSetup.submit.onCallFail(data.XMLHttpRequest);
        break;

      case api.err.CLUSTER_SETUP.PCS_LIB_ERROR:
        clusterSetup.dialog.resetMessages(data.msgList);
        break;

      case api.err.CLUSTER_SETUP.CONFIRMATION_DENIED:
        clusterSetup.dialog.close();
        break;

      case api.err.CLUSTER_SETUP.PCS_LIB_EXCEPTION:
        alert("Server returned an error: "+data.msg);
        break;

      case api.err.CLUSTER_START.FAILED:
        alert(
          "Cluster was created successfully!"
          +"\n\nHowever, a start of the cluster failed. Use 'Start' in the node"
          +" detail page to start each node individually."
          +"\n\nDetails:\nServer returned an error: "+data.XMLHttpRequest.status
          +" "+data.XMLHttpRequest.responseText
        );
        clusterSetup.dialog.close();
        break;

      case api.err.REMEMBER_CLUSTER.FAILED:
        // 403 makes not sense here. It would failed on
        // SEND_KNOWN_HOSTS.FAILED or on CLUSTER_SETUP.FAILED if the
        // user is not "hacluster". So we use standard mechanism here without
        // extra notice that cluster was setup and only remember-cluster failed.
        alert(
          "Cluster was created successfully!"
            +"\n\nHowever, adding it to web UI failed. Use 'Add Existing' to"
            +" add the new cluster to web UI."
            +"\n\nDetails:\nServer returned an error: "
            +data.XMLHttpRequest.status
            +" "+data.XMLHttpRequest.responseText
        );
        clusterSetup.dialog.close();
        break;
    }
  });
};
