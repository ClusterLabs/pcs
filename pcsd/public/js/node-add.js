nodeAdd = {dialog: {}, submit: {}};

nodeAdd.validateFormData = function(formData){
  var errors = [];
  if(formData.nodeName == ""){
    errors.push({
      type: "error",
      msg: "You may not leave the node name field blank.",
    });
  }
  return errors;
};

//------------------------------------------------------------------------------

nodeAdd.dialog.withSbdFeatures = function() {
  return Pcs.is_sbd_enabled;
};

nodeAdd.dialog.create = function(){
  $('#add_node').keypress(nodeAdd.dialog.submitOnEnter);
  $('#add_node').dialog({
    title: 'Add Node',
    closeOnEscape: false,
    dialogClass: "no-close",
    modal:true,
    resizable: false,
    width: 'auto',
    buttons: [
      {
        text: "Add Node",
        id: "add_node_submit_btn",
        click: nodeAdd.submit.run,
      },
      {
        text: "Cancel",
        click: nodeAdd.dialog.close
      },
    ],
  });
  if (nodeAdd.dialog.withSbdFeatures()) {
    $("#add_node .sbd-features").show();
  }
};

nodeAdd.dialog.submitOnEnter = function(e){
  if (
    e.keyCode == $.ui.keyCode.ENTER
    &&
    !$("#add_node_submit_btn").button("option", "disabled")
  ) {
    $("#add_node_submit_btn").trigger("click");
    return false;
  }
};

nodeAdd.dialog.close = tools.dialog.close("#add_node");

nodeAdd.dialog.reset = function(){
  $("#add_node [name='new_nodename']").val("");
  tools.dialog.resetInputs("#add_node [name='links[]']");
  $("#add_node [name='auto_start']").prop('checked', true);
  if (nodeAdd.dialog.withSbdFeatures()) {
    $("#add_node [name='watchdog']").val("");
    tools.dialog.resetInputs("#add_node [name='devices[]']");
    $("#add_node [name='no-watchdog-validation']").prop('checked', false);
  }
};

nodeAdd.dialog.toggleLinks = function(){
  $("#add_node .node-links").toggle();
};

nodeAdd.dialog.setSubmitAbility = tools.dialog.setActionAbility(
  "#add_node_submit_btn"
);

nodeAdd.dialog.getWatchdog = function(){
  var watchdog = $("#add_node [name='watchdog']");
  var value = watchdog.val().trim();
  return value !== "" ? value : watchdog.attr("placeholder");
};

nodeAdd.dialog.getFormData = function(){
  return {
    nodeName: $("#add_node [name='new_nodename']").val().trim(),
    nodeAddresses: tools.dialog.inputsToArray("#add_node [name='links[]']"),
    autoStart: $("#add_node [name='auto_start']").is(":checked"),
    sbd: ! nodeAdd.dialog.withSbdFeatures() ? undefined : {
      watchdog: nodeAdd.dialog.getWatchdog(),
      devices: tools.dialog.inputsToArray("#add_node [name='devices[]']"),
      noWatchdogValidation: $("#add_node [name='no-watchdog-validation']")
        .is(":checked")
    }
  };
};

nodeAdd.dialog.resetMessages = tools.dialog.resetMessages("#add_node");

//------------------------------------------------------------------------------

nodeAdd.submit.onCallFail = tools.submit.onCallFail(
  nodeAdd.dialog.resetMessages
);

nodeAdd.submit.run = function(){
  var formData = nodeAdd.dialog.getFormData();
  var errors = nodeAdd.validateFormData(formData);
  if(errors.length > 0){
    nodeAdd.dialog.resetMessages(errors);
    return;
  }
  var clusterName = Pcs.cluster_name;

  nodeAdd.dialog.resetMessages([]);
  nodeAdd.dialog.setSubmitAbility(false);

  api.canAddClusterOrNodes(
    [formData.nodeName],

  ).then(function(){
    return api.checkAuthAgainstNodes([formData.nodeName]);

  }).then(function(nodesAuthGroups){
    if (!nodesAuthGroups.ok.includes(formData.nodeName)) {
      return promise.reject(
        api.err.NODES_AUTH_CHECK.WITH_ERR_NODES,
        {nodeName: formData.nodeName}
      );
    }
    return api.sendKnownHostsToCluster(clusterName, [formData.nodeName]);

  }).then(function(){
    return api.clusterNodeAdd(
      { nodeAddData: formData, clusterName: clusterName },
      {
        confirm: function(msgs){
          return tools.submit.confirmForce("add node to cluster", msgs);
        },
      },
    );

  }).then(function(){
    if (formData.autoStart) {
      return api.clusterStart(clusterName, formData.nodeName);
    }

  }).then(function(){
    Pcs.update();
    nodeAdd.dialog.reset();
    nodeAdd.dialog.close();

  }).fail(function(rejectCode, data){
    nodeAdd.dialog.setSubmitAbility(true);
    switch(rejectCode){
      case api.err.CAN_ADD_CLUSTER_OR_NODES.FAILED:
        nodeAdd.submit.onCallFail(data.XMLHttpRequest, [400]);
        break;

      case api.err.NODES_AUTH_CHECK.FAILED:
        alert("ERROR: Unable to contact server");
        break;

      case api.err.NODES_AUTH_CHECK.WITH_ERR_NODES:
        auth_nodes_dialog([data.nodeName], nodeAdd.submit.run);
        break;

      case api.err.SEND_KNOWN_HOST_TO_CLUSTER.FAILED:
        nodeAdd.submit.onCallFail(data.XMLHttpRequest);
        break;

      case api.err.SEND_KNOWN_HOST_TO_CLUSTER.PCSD_ERROR:
        nodeAdd.dialog.resetMessages([{type: "error", msg: data.message}]);
        break;

      case api.err.NODE_ADD.FAILED:
        nodeAdd.submit.onCallFail(data.XMLHttpRequest);
        break;

      case api.err.NODE_ADD.PCS_LIB_EXCEPTION:
        alert("Server returned an error: "+data.msg);
        break;

      case api.err.NODE_ADD.PCS_LIB_ERROR:
        nodeAdd.dialog.resetMessages(data.msgList);
        break;

      case api.err.NODE_ADD.CONFIRMATION_DENIED:
        nodeAdd.dialog.close();
        break;

      case api.err.CLUSTER_START.FAILED:
        alert(
          "The node was added successfully!"
          +"\n\nHowever, a start of the node failed. Use 'Start' in the node"
          +" detail page to start the node"
          +"\n\nDetails:\nServer returned an error: "+data.XMLHttpRequest.status
          +" "+data.XMLHttpRequest.responseText
        );
        nodeAdd.dialog.close();
        break;
    }
  });
};
