nodesRemove = {dialog: {}, submit: {}};

nodesRemove.dialog.create = function(){
  var nodeNameList = get_checked_ids_from_nodelist("node_list");
  verify_remove(
    function(){ nodesRemove.submit.run(nodeNameList, Pcs.cluster_name) },
    false, // forceable
    undefined, // checklist_id
    "dialog_verify_remove_nodes", // dialog_id
    "node", // label
    "Remove Node(s)", // ok_text
    "Remove Node", // title
    nodeNameList,
    {
      closeOnEscape: false,
      dialogClass: "no-close",
    },
  );
};

nodesRemove.dialog.close = tools.dialog.close(
  "#dialog_verify_remove_nodes",
  "destroy",
);

nodesRemove.dialog.resetMessages = tools.dialog.resetMessages(
  "#dialog_verify_remove_nodes"
);

nodesRemove.submit.onCallFail = tools.submit.onCallFail(
  nodesRemove.dialog.resetMessages
);

nodesRemove.dialog.setSubmitAbility = tools.dialog.setActionAbility(
  "#verify_remove_submit_btn"
);
nodesRemove.dialog.setCancelAbility = tools.dialog.setActionAbility(
  "#verify_remove_cancel_btn"
);

nodesRemove.submit.run = function(nodeNameList, clusterName){
  nodesRemove.dialog.setSubmitAbility(false);
  nodesRemove.dialog.setCancelAbility(false);
  api.clusterNodeRemove(
    {
      clusterName: clusterName,
      nodeNameList: nodeNameList,
    },
    {
      confirm: function(msgs){
        return tools.submit.confirmForce("remove nodes from cluster", msgs);
      },
      buildMsg: function(report){
        switch(report.code){
          case "CANNOT_REMOVE_ALL_CLUSTER_NODES":
            return (
              "No nodes would be left in the cluster. If you intend to destroy"
              +" the whole cluster, go to cluster list page, select the cluster"
              +" and click 'Destroy'."
            );
        }
      },
    },

  ).then(function(){
    nodesRemove.dialog.close();
    Pcs.update();

  }).fail(function(rejectCode, data){
    // User cannot change form => it doesn't make sense resubmit removal.
    // nodesRemove.dialog.setSubmitAbility(true);
    nodesRemove.dialog.setCancelAbility(true);
    switch(rejectCode){
      case api.err.NODES_REMOVE.FAILED:
        nodesRemove.submit.onCallFail(data.XMLHttpRequest);
        break;

      case api.err.NODES_REMOVE.PCS_LIB_ERROR:
        nodesRemove.dialog.resetMessages(data.msgList);
        break;

      case api.err.NODES_REMOVE.PCS_LIB_EXCEPTION:
        alert("Server returned an error: "+data.msg);
        nodesRemove.dialog.close();
        break;
      case api.err.NODES_REMOVE.CONFIRMATION_DENIED:
        nodesRemove.dialog.close();
        break;

    }
  });
};
