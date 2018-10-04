api = {
  reports: {},
};

api.reports.severityMsgTypeMap = {
  ERROR: "error",
  WARNING: "warning",
  INFO: "info",
};

api.reports.statuses = {
  success: "success",
  error: "error",
};

api.reports.hasOnlyForibleErrors = function(reportList){
  var foundSomeError = false;
  for(var i in reportList){
    if(!reportList.hasOwnProperty(i)){
      continue;
    }

    var report = reportList[i];
    if (report.severity == "ERROR") {
      if (!report.forceable) {
        return false;
      }
      foundSomeError = true;
    }
  }
  return foundSomeError;
};

api.reports.isForcibleError = function(pcsResult){
  return (
    pcsResult.status === api.reports.statuses.error
    &&
    api.reports.hasOnlyForibleErrors(pcsResult.report_list)
  );
};

api.reports.toMsgs = function(reportList){
  return reportList
    .filter(function(report){
      return Object.keys(api.reports.severityMsgTypeMap)
        .includes(report.severity)
      ;
    })
    .map(function(report){
      return {
        type: api.reports.severityMsgTypeMap[report.severity],
        msg: report.report_text,
      };
    })
  ;
};

// TODO JSON.parse can fail
api.err = {
  NODES_AUTH_CHECK: "NODES_AUTH_CHECK",
  SEND_KNOWN_HOST_CALL_FAILED: "SEND_KNOWN_HOST_CALL_FAILED",
  SEND_KNOWN_HOSTS_ERROR: "SEND_KNOWN_HOSTS_ERROR",
  CLUSTER_SETUP_CALL_FAILED: "CLUSTER_SETUP_CALL_FAILED",
  CLUSTER_SETUP_FAILED: "CLUSTER_SETUP_FAILED",
  CLUSTER_SETUP_EXCEPTION: "CLUSTER_SETUP_EXCEPTION",
  CLUSTER_SETUP_FAILED_FORCIBLE: "CLUSTER_SETUP_FAILED_FORCIBLE",
  REMEMBER_CLUSTER_CALL_FAILED: "REMEMBER_CLUSTER_CALL_FAILED",
  AUTH_NODES_FAILED: "AUTH_NODES_FAILED",
};

api.checkAuthAgainstNodes = function(nodesNames){
  return promise.get(
    "/manage/check_auth_against_nodes",
    {"node_list": nodesNames},
    api.err.NODES_AUTH_CHECK,

  ).then(function(nodesAuthStatusResponse){
    var nodesAuthStatus = JSON.parse(nodesAuthStatusResponse);
    var status = {
      ok: [],
      noAuth: [],
      noConnect: [],
    };

    for (var name in nodesAuthStatus) {
      if( ! nodesAuthStatus.hasOwnProperty(name)){
        continue;
      }
      switch(nodesAuthStatus[name]){
        case "Online": status.ok.push(name); break;
        case "Unable to authenticate": status.noAuth.push(name); break;
        default: status.noConnect.push(name); break;
      }
    }

    return promise.resolve(status);
  });
};

api.clusterSetup = function(setupData, setupCoordinatingNode, force){
  return promise.post(
    "/manage/cluster-setup",
    {
      target_node: setupCoordinatingNode,
      setup_data: JSON.stringify({
        cluster_name: setupData.clusterName,
        nodes: setupData.nodesNames.map(function(nodeName){
          return {name: nodeName};
        }),
        transport_type: "knet",
        transport_options: {},
        link_list: [],
        compression_options: {},
        crypto_options: {},
        totem_options: {},
        quorum_options: {},
        force_flags: force ? ["FORCE"] : [],
      }),
    },
    api.err.CLUSTER_SETUP_CALL_FAILED,

  ).then(function(setupResultString){
    return promise.resolve(JSON.parse(setupResultString));
  });
};

api.clusterSetup.processErrors = function(
  setupResult, setupData, setupCoordinatingNode
){
  if (setupResult.status !== api.reports.statuses.error) {
    return promise.reject(api.err.CLUSTER_SETUP_EXCEPTION, {
      msg: setupResult.status_msg
    });
  }
  if (api.reports.isForcibleError(setupResult)) {
    return promise.reject(api.err.CLUSTER_SETUP_FAILED_FORCIBLE, {
      msgList: api.reports.toMsgs(setupResult.report_list),
      setupData: setupData,
      setupCoordinatingNode: setupCoordinatingNode,
    });
  }
  return promise.reject(api.err.CLUSTER_SETUP_FAILED, {
    msgList: api.reports.toMsgs(setupResult.report_list)
  });
};

api.sendKnownHostsToNode = function(setupCoordinatingNode, nodesNames){
  return promise.post(
    "/manage/send-known-hosts-to-node",
    {
      target_node: setupCoordinatingNode,
      "node_names[]": nodesNames,
    },
    api.err.SEND_KNOWN_HOST_CALL_FAILED,
  );
};

api.sendKnownHostsToNode.processErrors = function(
  authShareResultCode, setupCoordinatingNode
){
  var codeMsgMap = {
    "error": "Error during sharing authentication with node '"
      +setupCoordinatingNode+"'"
    ,
    "not_supported": "Sharing authentication with node '"
      +setupCoordinatingNode+"' not supported"
    ,
  };
  return promise.reject(api.err.SEND_KNOWN_HOSTS_ERROR, {
    message: codeMsgMap[authShareResultCode] !== undefined
      ? codeMsgMap[authShareResultCode]
      : "Unknown sharing authentication with node '"+setupCoordinatingNode
        +"' result: '"+authShareResultCode+"'"
    ,
  });
};

api.remember = function(clusterName, nodesNames){
  return promise.post(
    "/manage/remember-cluster",
    {
      cluster_name: clusterName,
      "nodes[]": nodesNames,
    },
    api.err.REMEMBER_CLUSTER_CALL_FAILED,
  );
};
