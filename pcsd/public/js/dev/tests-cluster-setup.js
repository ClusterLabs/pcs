dev.utils.clusterSetupDialog = {
  wasRun: false,
};
dev.utils.clusterSetupDialog.prefill = function(url, nodesNames){
  nodesNames = nodesNames || ["dave8", "kryten8", "holly8"];

  if(dev.utils.clusterSetupDialog.wasRun){ return }

  dev.utils.clusterSetupDialog.wasRun = true;
  clusterSetup.dialog.create();
  $('input[name^="clustername"]').val(testClusterSetup.clusterName);
  var nodes = $('#csetup input[name="node[]"]');
  nodesNames.forEach(function(name, i){ nodes.eq(i).val(name) });

  setTimeout(function(){
    clusterSetup.submit.run(true);

    setTimeout(function(){
      dev.utils.clusterSetupDialog.prefillKnet();
      dev.utils.clusterSetupDialog.prefillTransportOptionsKnet();
      dev.utils.clusterSetupDialog.prefillCompression();
      dev.utils.clusterSetupDialog.prefillCrypto();
      dev.utils.clusterSetupDialog.prefillTotem();
      dev.utils.clusterSetupDialog.prefillQuorum();
      // dev.utils.clusterSetupDialog.prefillTransportOptionsUdp("udp");
      // $("[href='#csetup-transport-options']").trigger("click");
      // $("[href='#csetup-quorum']").trigger("click");
      // dev.utils.clusterSetupDialog.prefillUdp("udpu");
      $(".ui-dialog:has('#csetup') button:contains('Create cluster')")
        // .trigger("click")
      ;
      // $("[href='#csetup-totem']").trigger("click");
    }, 500);
  }, 5);
};

dev.utils.clusterSetupDialog.prefillForm = function(context, data, correct){
  correct = correct || function(name, value){ return value };

  for(var name in data){
    var widget = $("[name='"+name+"']", context);

    var value = correct(name, data[name]);
    if (widget.attr("type") === "checkbox") {
      widget.prop("checked", value);
    } else {
      widget.val(value);
    }

  }
};

dev.utils.clusterSetupDialog.prefillCompression = function(){
  dev.utils.clusterSetupDialog.prefillForm(
    $("#csetup-transport-options .compression-options"),
    {
      model: "zlib",
      threshold: "101",
      level: "1",
    },
  );
};

dev.utils.clusterSetupDialog.prefillTransportOptionsKnet = function(){
  dev.utils.clusterSetupDialog.prefillForm(
    $("#csetup-transport-options .options-container .options.knet"),
    {
      ip_version: "ipv4",
      knet_pmtud_interval: "2",
      link_mode: "rr",
    },
  );
};
dev.utils.clusterSetupDialog.prefillTransportOptionsUdp = function(type){
  dev.utils.clusterSetupDialog.prefillForm(
    $("#csetup-transport-options .options-container .options."+type),
    {
      ip_version: "ipv4",
      netmtu: "1501",
    },
  );
};

dev.utils.clusterSetupDialog.prefillTotem = function(){
  dev.utils.clusterSetupDialog.prefillForm($("#csetup-totem"), {
    consensus: 1201,
    downcheck: 1001,
    fail_recv_const: 2501,
    heartbeat_failures_allowed: 1,
    hold: 181,
    join: 51,
    max_messages: 18,
    max_network_delay: 51,
    merge: 201,
    miss_count_const: 6,
    send_join: 1,
    seqno_unchanged_const: 31,
    token: 1001,
    token_coefficient: 651,
    token_retransmit: 239,
    token_retransmits_before_loss_const: 5,
    window_size: 51,
  });
};

dev.utils.clusterSetupDialog.prefillQuorum = function(){
  dev.utils.clusterSetupDialog.prefillForm(
    $("#csetup-quorum"),
    {
      auto_tie_breaker: true,
      last_man_standing: true,
      last_man_standing_window: 1001,
      wait_for_all: true,
    },
    function(name, value){
      if (
        [
          "auto_tie_breaker",
          "last_man_standing",
          "wait_for_all",
        ].includes(name)
      ) {
        return value ? "on" : "off";
      }
      return value;
    }
  );
};

dev.utils.clusterSetupDialog.prefillCrypto = function(){
  dev.utils.clusterSetupDialog.prefillForm(
    $("#csetup-transport-options .crypto-options"),
    {
      model: "nss",
      hash: "sha256",
      cipher: "aes192",
    },
  );
};

dev.utils.clusterSetupDialog.addLink = function(addressPrefix, data){
  $("#csetup-transport-netmaps .add-link").trigger("click");
  clusterSetup.netmap.current.detailList().find("[name$='-address[]']").each(
    function(i, input){ $(input).val(addressPrefix+(71 + i)) }
  );

  var currentLinkId = clusterSetup.netmap.current.linksContainer()
    .find(".current")
    .attr("data-transport-link-id")
  ;

  dev.utils.clusterSetupDialog.prefillForm(
    clusterSetup.netmap.current.detailList().find(
      "[data-transport-link-id='"+currentLinkId+"']"
    ),
    data
  );
};

dev.utils.clusterSetupDialog.prefillUdp = function(udpType){
  $("#csetup-transport-"+udpType).trigger("click");
  dev.utils.clusterSetupDialog.addLink("127.0.0.", {
    bindnetaddr: 1,
    broadcast: 2,
    mcastaddr: 3,
    mcastport: 4,
    ttl: 5,
  });
};

dev.utils.clusterSetupDialog.prefillKnet = function(){
  $("#csetup-transport-knet").trigger("click");
  var getData = function(multi){
    return {
      link_priority: 1,
      mcastport: "",
      ping_interval: 95,
      ping_precision: 2049,
      ping_timeout: 195,
      pong_count: 6,
      transport: "udp",
    };
  };
  dev.utils.clusterSetupDialog.addLink("127.0.0.", getData(1));
};

dev.utils.clusterSetupDialog.logSetupData = function(setupData){
  console.group('SETUP DATA', setupData);

  console.group('nodes');
  setupData.nodeList.forEach(function(node){
    console.group(node.name);
    console.log("addrs:", node.addrs);
    console.groupEnd();
  });
  console.groupEnd();

  console.group('linkList');
  setupData.linkList.forEach(function(link){
    console.log(link);
  });
  console.groupEnd();

  if (setupData.compression !== undefined) {
    console.group('compression');
    console.log(setupData.compression);
    console.groupEnd();
  }

  if (setupData.crypto !== undefined) {
    console.group('crypto');
    console.log(setupData.crypto);
    console.groupEnd();
  }

  console.group('totem');
  console.log(setupData.totem);
  console.groupEnd();

  console.group('quorum');
  console.log(setupData.quorum);
  console.groupEnd();

  console.groupEnd();
};
testClusterSetup = { clusterName: "starbug8" };

dev.patch.ajax_wrapper(
  function(url){
    switch(url){
      case "/clusters_overview":
        if(dev.flags.cluster_overview_run === undefined){
          dev.flags.cluster_overview_run = true;
          console.group('Wrapping ajax_wrapper');
          console.log(url);
          console.groupEnd();
          return mock.clusters_overview;
        }
      default: return undefined;
    }
  },
  dev.utils.clusterSetupDialog.prefill,
);


testClusterSetup.successPath = function(url, data, success, fail){
  switch(url){
    case "/manage/can-add-cluster-or-nodes": return success();
    case "/manage/check_auth_against_nodes": return success(JSON.stringify({
      dave8: "Online",
      kryten8: "Online",
      holly8: "Online",
    }));
    case "/manage/send-known-hosts-to-node": return success("success");

    case "/manage/cluster-setup": return success(
      JSON.stringify(dev.fixture.success)
    );


    case "/managec/"+testClusterSetup.clusterName+"/cluster_start":
      return success();

    case "/manage/remember-cluster": return success();
  }
};

testClusterSetup.canAddClusterOrNodes403 = function(url, data, success, fail){
  switch(url){
    case "/manage/can-add-cluster-or-nodes": return fail(
      403, "Permission denied."
    );
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.canAddClusterOrNodes500 = function(url, data, success, fail){
  switch(url){
    case "/manage/can-add-cluster-or-nodes": return fail(
      500, "Something is wrong",
    );
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.canAddClusterOrNodes400 = function(url, data, success, fail){
  switch(url){
    case "/manage/can-add-cluster-or-nodes": return fail(
      400,
      "The cluster name 'cluster_name' has already been added."
      +" You may not add two clusters with the same name."
      +"\nThe node 'node_name' is already a part of the 'cluster_name' cluster."
      +" You may not add a node to two different clusters."
    );
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.checkAuth500 = function(url, data, success, fail){
  switch(url){
    case "/manage/check_auth_against_nodes": return fail(
      500, "Something is wrong",
    );
    case "/manage/send-known-hosts-to-node": return success("success");
  }
};

testClusterSetup.checkAuthFails = function(url, data, success, fail){
  switch(url){
    case "/manage/check_auth_against_nodes": return fail();
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.checkAuthNodesNotAuth = function(url, data, success, fail){
  switch(url){
    case "/manage/check_auth_against_nodes": return success(JSON.stringify({
      dave8: "Online",
      kryten8: "Unable to authenticate",
      holly8: "Cant connect",
    }));
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.sendKnownHosts403 = function(url, data, success, fail){
  switch(url){
    case "/manage/send-known-hosts-to-node": return fail(
      403, "Permission denied."
    );
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.sendKnownHostsFail = function(url, data, success, fail){
  switch(url){
    case "/manage/send-known-hosts-to-node": return success("error");
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.sendKnownHostsUnsupported = function(url, data, success, fail){
  switch(url){
    case "/manage/send-known-hosts-to-node": return success("not_supported");
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.sendKnownHostsUnknownFail = function(url, data, success, fail){
  switch(url){
    case "/manage/send-known-hosts-to-node": return success("unknown");
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.clusterSetup403 = function(url, data, success, fail){
  switch(url){
    case "/manage/cluster-setup": return fail(
      403, "Permission denied."
    );
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.clusterSetup500 = function(url, data, success, fail){
  switch(url){
    case "/manage/cluster-setup": return fail(
      500, "Something is wrong",
    );
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};
testClusterSetup.clusterSetupUnforcible = function(url, data, success, fail){
  switch(url){
    case "/manage/cluster-setup": return success(
      JSON.stringify(dev.fixture.libErrorUnforcibleLarge)
    );
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.clusterSetupUnforcibleFirstTime =
function(url, data, success, fail){
  switch(url){
    case "/manage/cluster-setup":
      if (dev.flags.cluster_setup_test_setup_first_time_was_run === undefined) {
        dev.flags.cluster_setup_test_setup_first_time_was_run = true;
        return success(
          JSON.stringify(dev.fixture.libErrorUnforcibleLarge)
        );
      }
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.clusterSetupException = function(url, data, success, fail){
  switch(url){
    case "/manage/cluster-setup":
      return success(JSON.stringify(dev.fixture.libException));
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};


testClusterSetup.clusterSetupForceFail = function(url, data, success, fail){
  switch(url){
    case "/manage/cluster-setup":
      return success(JSON.stringify(
        dev.fixture.libError(JSON.parse(data.setup_data).force_flags.length < 1)
      ));
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.clusterSetupForceFailForcible = function(
  url, data, success, fail
){
  switch(url){
    case "/manage/cluster-setup":
      return success(JSON.stringify(dev.fixture.libError(true)));
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.clusterSetupForce = function(url, data, success, fail){
  switch(url){
    case "/manage/cluster-setup":
      if (JSON.parse(data.setup_data).force_flags.length < 1) {
        return success(JSON.stringify(dev.fixture.libError(true)));
      }
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.rememberFail = function(url, data, success, fail){
  switch(url){
    case "/manage/remember-cluster": return fail(500, "Server error");
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};

testClusterSetup.startClusterFail = function(url, data, success, fail){
  switch(url){
    case "/managec/"+testClusterSetup.clusterName+"/cluster_start": return fail(
      400, "Server error"
    );
    default:
      return testClusterSetup.successPath(url, data, success, fail);
  }
};




dev.runScenario(
  // testClusterSetup.canAddClusterOrNodes403
  // testClusterSetup.canAddClusterOrNodes500
  // testClusterSetup.canAddClusterOrNodes400
  // testClusterSetup.checkAuthFails
  // testClusterSetup.checkAuthNodesNotAuth
  // testClusterSetup.sendKnownHosts403
  // testClusterSetup.sendKnownHostsFail
  // testClusterSetup.sendKnownHostsUnsupported
  // testClusterSetup.sendKnownHostsUnknownFail
  // testClusterSetup.clusterSetup403
  // testClusterSetup.clusterSetup500
  // testClusterSetup.clusterSetupUnforcible
  // testClusterSetup.clusterSetupUnforcibleFirstTime
  // testClusterSetup.clusterSetupException
  // testClusterSetup.clusterSetupForceFail
  // testClusterSetup.clusterSetupForceFailForcible
  // testClusterSetup.clusterSetupForce
  // testClusterSetup.rememberFail
  // testClusterSetup.startClusterFail
  testClusterSetup.successPath
);
