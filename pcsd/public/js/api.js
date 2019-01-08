api = {
  reports: {},
  pcsLib: {},
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

api.reports.hasOnlyForcibleErrors = function(reportList){
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
    api.reports.hasOnlyForcibleErrors(pcsResult.report_list)
  );
};

api.reports.toMsgs = function(reportList, msgBuilder){
  return reportList
    .filter(function(report){
      return Object.keys(api.reports.severityMsgTypeMap)
        .includes(report.severity)
      ;
    })
    .map(function(report){
      var msg = report.report_text;
      if (msgBuilder) {
        var buildedMsg = msgBuilder(report);
        if (buildedMsg !== undefined) {
          msg = buildedMsg;
        }
      }
      return {
        type: api.reports.severityMsgTypeMap[report.severity],
        msg: msg + (
          (report.severity === "ERROR" && report.forceable)
            ? " (can be forced)"
            : ""
        ),
      };
    })
  ;
};

api.processSingleStatus = function(resultCode, rejectCode, actionDesc){
  if(resultCode === "success"){
    return promise.resolve();
  }
  var codeMsgMap = {
    "error": "Error during "+actionDesc+"'.",
    "not_supported": tools.string.upperFirst(actionDesc)+"' not supported.",
  };
  return promise.reject(rejectCode, {
    message: codeMsgMap[resultCode] !== undefined
      ? codeMsgMap[resultCode]
      : "Unknown result of "+actionDesc+" (result: '"+resultCode+"')."
    ,
  });
};

api.pcsLib.forcibleLoop = function(apiCall, errGroup, processOptions, force){
  return apiCall(force).then(function(responseString){
    var response = JSON.parse(responseString);

    if (response.status === api.reports.statuses.success) {
      return promise.resolve(response.data);
    }

    if (response.status !== api.reports.statuses.error) {
      return promise.reject(errGroup.PCS_LIB_EXCEPTION, {
        msg: response.status_msg
      });
    }

    var msgs = api.reports.toMsgs(
      response.report_list, processOptions.buildMsg
    );

    if (!api.reports.isForcibleError(response)) {
      return promise.reject(errGroup.PCS_LIB_ERROR, { msgList: msgs });
    }

    if (!processOptions.confirm(msgs)) {
      return promise.reject(errGroup.CONFIRMATION_DENIED);
    }

    return api.pcsLib.forcibleLoop(apiCall, errGroup, processOptions, true);
  });
};

// TODO JSON.parse can fail
api.err = {
  NODES_AUTH_CHECK: {
    FAILED: "NODES_AUTH_CHECK.FAILED",
    WITH_ERR_NODES: "NODES_AUTH_CHECK.WITH_ERR_NODES",
  },
  SEND_KNOWN_HOSTS: {
    FAILED: "SEND_KNOWN_HOSTS.FAILED",
    PCSD_ERROR: "SEND_KNOWN_HOSTS.PCSD_ERROR",
  },
  CLUSTER_SETUP: {
    FAILED: "CLUSTER_SETUP.FAILED",
    PCS_LIB_EXCEPTION: "CLUSTER_SETUP.PCS_LIB_EXCEPTION",
    PCS_LIB_ERROR: "CLUSTER_SETUP.PCS_LIB_ERROR",
    CONFIRMATION_DENIED: "CLUSTER_SETUP.CONFIRMATION_DENIED",
  },
  REMEMBER_CLUSTER: {
    FAILED: "REMEMBER_CLUSTER.FAILED",
  },
  SEND_KNOWN_HOST_TO_CLUSTER: {
    FAILED: "SEND_KNOWN_HOST_TO_CLUSTER.FAILED",
    PCSD_ERROR: "SEND_KNOWN_HOST_TO_CLUSTER.PCSD_ERROR",
  },
  NODE_ADD: {
    FAILED: "NODE_ADD.FAILED",
    PCS_LIB_EXCEPTION: "NODE_ADD.PCS_LIB_EXCEPTION",
    PCS_LIB_ERROR: "NODE_ADD.PCS_LIB_ERROR",
    CONFIRMATION_DENIED: "NODE_ADD.CONFIRMATION_DENIED",
  },
  NODES_REMOVE: {
    FAILED: "NODES_REMOVE.FAILED",
    PCS_LIB_EXCEPTION: "NODES_REMOVE.PCS_LIB_EXCEPTION",
    PCS_LIB_ERROR: "NODES_REMOVE.PCS_LIB_ERROR",
    CONFIRMATION_DENIED: "NODES_REMOVE.CONFIRMATION_DENIED",
  },
  CLUSTER_START: {
    FAILED: "CLUSTER_START.FAILED",
  },
  CLUSTER_DESTROY: {
    FAILED: "CLUSTER_DESTROY.FAILED",
  },
  CAN_ADD_CLUSTER_OR_NODES: {
    FAILED: "CAN_ADD_CLUSTER_OR_NODES.FAILED",
  }
};

api.tools = {};

api.tools.forceFlags = function(force){
  return force ? ["FORCE"] : [];
};

api.canAddClusterOrNodes = function(nodesNames, clusterName){
  var data = { node_names: nodesNames };
  if (clusterName) {
    data["cluster"] = clusterName;
  }
  return promise.get(
    "/manage/can-add-cluster-or-nodes",
    data,
    api.err.CAN_ADD_CLUSTER_OR_NODES.FAILED,
  );

};

api.checkAuthAgainstNodes = function(nodesNames){
  return promise.get(
    "/manage/check_auth_against_nodes",
    {"node_list": nodesNames},
    api.err.NODES_AUTH_CHECK.FAILED,

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

api.clusterSetup = function(submitData, processOptions){
  var setupData = submitData.setupData;
  var data = {
    cluster_name: setupData.clusterName,
    nodes: setupData.nodeList.map(function(node){
      return {
        name: node.name,
        addrs: node.addrs.filter(function(addr){return addr.length > 0}),
      };
    }),
    transport_type: setupData.transportType,
    transport_options: setupData.transportType == "knet"
      ? {
        ip_version: setupData.transportOptions.ip_version,
        knet_pmtud_interval: setupData.transportOptions.knet_pmtud_interval,
        link_mode: setupData.transportOptions.link_mode,
      }
      : {
        ip_version: setupData.transportOptions.ip_version,
        netmtu: setupData.transportOptions.netmtu,
      }
    ,
    link_list: setupData.linkList.map(function(link){
      return setupData.transportType == "knet"
        ? {
          linknumber: link.linknumber,
          ip_version: link.ip_version,
          link_priority: link.link_priority,
          mcastport: link.mcastport,
          ping_interval: link.ping_interval,
          ping_precision: link.ping_precision,
          ping_timeout: link.ping_timeout,
          pong_count: link.pong_count,
          transport: link.transport,
        }
        : {
          bindnetaddr: link.bindnetaddr,
          broadcast: link.broadcast,
          mcastaddr: link.mcastaddr,
          mcastport: link.mcastport,
          ttl: link.ttl,
        }
      ;
    }),
    compression_options: {
      model: setupData.compression.model,
      threshold: setupData.compression.threshold,
      level: setupData.compression.level,
    },
    crypto_options: {
      model: setupData.crypto.model,
      hash: setupData.crypto.hash,
      cipher: setupData.crypto.cipher,
    },
    totem_options: {
      consensus: setupData.totem.consensus,
      downcheck: setupData.totem.downcheck,
      fail_recv_const: setupData.totem.fail_recv_const,
      heartbeat_failures_allowed: setupData.totem.heartbeat_failures_allowed,
      hold: setupData.totem.hold,
      join: setupData.totem.join,
      max_messages: setupData.totem.max_messages,
      max_network_delay: setupData.totem.max_network_delay,
      merge: setupData.totem.merge,
      miss_count_const: setupData.totem.miss_count_const,
      send_join: setupData.totem.send_join,
      seqno_unchanged_const: setupData.totem.seqno_unchanged_const,
      token: setupData.totem.token,
      token_coefficient: setupData.totem.token_coefficient,
      token_retransmit: setupData.totem.token_retransmit,
      token_retransmits_before_loss_const:
        setupData.totem.token_retransmits_before_loss_const
      ,
      window_size: setupData.totem.window_size,
    },
    quorum_options: {
      auto_tie_breaker: setupData.quorum.auto_tie_breaker,
      last_man_standing: setupData.quorum.last_man_standing,
      last_man_standing_window: setupData.quorum.last_man_standing_window,
      wait_for_all: setupData.quorum.wait_for_all,
    },
  };

  var apiCall = function(force){
    data.force_flags = api.tools.forceFlags(force);
    return promise.post(
      "/manage/cluster-setup",
      {
        target_node: submitData.setupCoordinatingNode,
        setup_data: JSON.stringify(data),
      },
      api.err.CLUSTER_SETUP.FAILED,
    );
  };

  return api.pcsLib.forcibleLoop(
    apiCall,
    api.err.CLUSTER_SETUP,
    processOptions
  );
};

api.sendKnownHostsToNode = function(setupCoordinatingNode, nodesNames){
  return promise.post(
    "/manage/send-known-hosts-to-node",
    {
      target_node: setupCoordinatingNode,
      "node_names[]": nodesNames,
    },
    api.err.SEND_KNOWN_HOSTS.FAILED,

  ).then(function(response){
    return api.processSingleStatus(
      response,
      api.err.SEND_KNOWN_HOSTS.PCSD_ERROR,
      "sharing authentication with node '"+setupCoordinatingNode+"'",
    );
  });
};

api.rememberCluster = function(clusterName, nodesNames){
  return promise.post(
    "/manage/remember-cluster",
    {
      cluster_name: clusterName,
      "nodes[]": nodesNames,
    },
    api.err.REMEMBER_CLUSTER.FAILED,
  );
};

api.sendKnownHostsToCluster = function(clusterName, nodesNames){
  return promise.post(
    get_cluster_remote_url(clusterName)+"send-known-hosts",
    {
      "node_names[]": nodesNames,
    },
    api.err.SEND_KNOWN_HOST_TO_CLUSTER.FAILED,
  ).then(function(response){
    return api.processSingleStatus(
      response,
      api.err.SEND_KNOWN_HOST_TO_CLUSTER.PCSD_ERROR,
      "sharing authentication for nodes '"+nodesNames.join("', '")
        +"' with cluster '"+clusterName+"'"
      ,
    );
  });
};

api.clusterNodeAdd = function(submitData, processOptions){
  var nodeAddData = submitData.nodeAddData;

  var node = {name: nodeAddData.nodeName};
  if (nodeAddData.nodeAddresses.length > 0) {
    node.addrs = nodeAddData.nodeAddresses;
  }
  if (nodeAddData.sbd !== undefined) {
    node.watchdog = nodeAddData.sbd.watchdog;
    node.devices = nodeAddData.sbd.devices;
  }

  var data = {
    nodes: [node],
    wait: false,
    start: false, // don't slow it down; start will be considered aftermath
    enable: true,
    no_watchdog_validation: nodeAddData.sbd !== undefined
      ? nodeAddData.sbd.noWatchdogValidation 
      : false
    ,
  };

  var apiCall = function(force){
    data.force_flags = api.tools.forceFlags(force);
    return promise.post(
      get_cluster_remote_url(submitData.clusterName)+"cluster_add_nodes",
      {data_json: JSON.stringify(data)},
      api.err.NODE_ADD.FAILED
    );
  };

  return api.pcsLib.forcibleLoop(apiCall, api.err.NODE_ADD, processOptions);
};

api.clusterNodeRemove = function(submitData, processOptions){
  var data = { node_list: submitData.nodeNameList };
  var apiCall = function(force){
    data.force_flags = api.tools.forceFlags(force);
    return promise.post(
      get_cluster_remote_url(submitData.clusterName)+"cluster_remove_nodes",
      {data_json: JSON.stringify(data)},
      api.err.NODES_REMOVE.FAILED,
      {
        timeout: 60000,
      }
    );
  };
  return api.pcsLib.forcibleLoop(apiCall, api.err.NODES_REMOVE, processOptions);
};

api.clusterStart = function(clusterName, settings){
  var data = {};
  if (settings.nodeName) {
    data["name"] = settings.nodeName;
  }

  if (settings.all) {
    data["all"] = "1";
  }
  return promise.post(
    get_cluster_remote_url(clusterName)+"cluster_start",
    data,
    api.err.CLUSTER_START.FAILED,
  );
};

api.clusterDestroy = function(clusterName){
  return promise.post(
    get_cluster_remote_url(clusterName)+"cluster_destroy",
    { all: 1 },
    api.err.CLUSTER_DESTROY.FAILED,
  );
};
