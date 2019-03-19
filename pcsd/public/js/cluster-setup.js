clusterSetup = {
  transportType: {},
  link: {
    detail: {},
  },
  netmap: { current: {} },
  snippet: {},
  data: {},
  step: {},
  dialog: { },
  submit: {},
};

//------------------------------------------------------------------------------

clusterSetup.state = {
  dialogOpened: false,
  compiled: false,
  lastUid: 1,
  multiStepErrors: [],
};

clusterSetup.const = {
  BACK_TO_NODES: "BACK_TO_NODES",
  CANCEL: "CANCEL",
};

clusterSetup.generateUid = function(){
  return clusterSetup.state.lastUid++;
};

//------------------------------------------------------------------------------

clusterSetup.link.pairAttr = "data-transport-link-id";
clusterSetup.link.create = function(transportType, actions){
  return tools.snippet.take("transport-link")
    .click(actions.setCurrent)
    .find(".label").text(transportType+" link").parents(".transport-link")
    .find(".delete").click(actions.delete).parents(".transport-link")
  ; 
};

clusterSetup.link.detail.addressName = function(nodeName){
  return nodeName+"-address[]";
};

clusterSetup.link.detail.create = function(transportType, nodesNames){
  var detail = tools.snippet.take("transport-link-detail");
  var html = detail.html();
  var addrList = detail.find(".transport-addresses");

  $(nodesNames).each(function(j, nodeName){
    $(addrList).append(clusterSetup.link.detail.createAddress(nodeName));
  });

  detail.find(".options").append(
    tools.snippet.take("transport-link-options-"+
      clusterSetup.transportType.alias(transportType)
    )
  );

  return detail;
};

clusterSetup.link.detail.createAddress = function(nodeName){
  var address = tools.snippet.take("transport-addr").find("tr");
  address.attr("data-transport-addr-host", nodeName)
  $(".node-name", address).text(nodeName+":");
  $(".address", address)
    .attr("name", clusterSetup.link.detail.addressName(nodeName))
  ;
  return address;
};

clusterSetup.link.detail.refreshNodesNames = function(linkDetail, nodesNames){
  // Is fast enough. No cache required.
  var previousNodesNames = $.makeArray(
    linkDetail
      .find(".transport-addresses [data-transport-addr-host]")
      .map(function(){return $(this).attr("data-transport-addr-host")})
  );

  var newAddresses = nodesNames.map(function(nodeName){
    return previousNodesNames.contains(nodeName)
      ? linkDetail.find("[data-transport-addr-host="+nodeName+"]")
      : clusterSetup.link.detail.createAddress(nodeName)
    ;
  });

  linkDetail.find(".transport-addresses").empty().append(newAddresses);
};

//------------------------------------------------------------------------------
clusterSetup.netmap.updateAddLinkAbility = function(transportType, linkList){
  var addLinkButton = $("#csetup-transport-netmaps .add-link");
  var maxLinkCount = transportType === "knet" ? 8 : 1;
  if (linkList.length >= maxLinkCount) {
    addLinkButton.hide();
  }else{
    addLinkButton.show();
  }
};

clusterSetup.netmap.onLinksChange = function(){
  var linkList = clusterSetup.netmap.current.linkList();

  clusterSetup.netmap.updateAddLinkAbility(
    clusterSetup.transportType.current(),
    linkList,
  );

  if(linkList.length < 1){
    clusterSetup.netmap.current.get().hide();
    return;
  }

  clusterSetup.netmap.current.renumberLinks();
  clusterSetup.netmap.current.get().show();

  if(linkList.filter(".current").length < 1) {
    var firstLinkId = linkList.eq(0).attr("data-transport-link-id") ;
    clusterSetup.netmap.current.setCurrentLink(firstLinkId);
  }
};

clusterSetup.netmap.current.selector = function(){
  return "#csetup-transport-netmaps ."+clusterSetup.transportType.current();
};

clusterSetup.netmap.current.get = function(){
  return $(clusterSetup.netmap.current.selector());
};

clusterSetup.netmap.current.detailsContainer = function(){
  return $(clusterSetup.netmap.current.selector() +" .link-detail-list");
};

clusterSetup.netmap.current.detailList = function(){
  return $(
    clusterSetup.netmap.current.selector() +" .link-detail-list .detail"
  );
};

clusterSetup.netmap.current.linksContainer = function(){
  return $(clusterSetup.netmap.current.selector() +" .link-container");
};

clusterSetup.netmap.current.linkList = function(){
  return clusterSetup.netmap.current.linksContainer().find(".transport-link");
};

clusterSetup.netmap.current.adaptToType = function(){
  $("#csetup-transport-netmaps .type-netmap").hide();
  if (clusterSetup.netmap.current.linksContainer().children().length > 0) {
    clusterSetup.netmap.current.get().show();
  }
  clusterSetup.netmap.updateAddLinkAbility(
    clusterSetup.transportType.current(),
    clusterSetup.netmap.current.linkList(),
  );
};

clusterSetup.netmap.current.createLink = function(id, nodesNames){
  var linkActions = {
    setCurrent: function(){ clusterSetup.netmap.current.setCurrentLink(id) },
    delete: function(){ clusterSetup.netmap.current.deleteLink(id) },
  };

  clusterSetup.netmap.current.linksContainer().append(
    clusterSetup.link
      .create(clusterSetup.transportType.current(), linkActions)
      .attr(clusterSetup.link.pairAttr, id)
  );

  clusterSetup.netmap.current.detailsContainer().append(
    clusterSetup.link.detail
      .create(clusterSetup.transportType.current(), nodesNames)
      .attr(clusterSetup.link.pairAttr, id)
  );

  clusterSetup.netmap.current.setCurrentLink(id);
  clusterSetup.netmap.onLinksChange();
};

clusterSetup.netmap.current.renumberLinks = function(){
  clusterSetup.netmap.current.linksContainer().children().each(function(i){
    $(this).find(".link-nr").text(i);
  });
};

clusterSetup.netmap.current.deleteLink = function(id){
  $("["+clusterSetup.link.pairAttr+"='"+id+"']").remove();
  clusterSetup.netmap.onLinksChange();
};

clusterSetup.netmap.current.setCurrentLink = function(id){
  var pairSelector = "["+clusterSetup.link.pairAttr+"='"+id+"']";

  var linkList = clusterSetup.netmap.current.linksContainer();
  linkList.children().each(function(){ $(this).removeClass("current") });
  linkList.children(pairSelector).addClass("current");

  clusterSetup.netmap.current.detailList().hide();
  clusterSetup.netmap.current.detailsContainer().find(pairSelector).show()
  ;
};

//------------------------------------------------------------------------------

clusterSetup.transportType.idPrefix = "csetup-transport-";
clusterSetup.transportType.list = ["knet", "udp", "udpu"];
clusterSetup.transportType.alias = function(transportType){
  return transportType === "udpu" ? "udp" : transportType;
};
clusterSetup.transportType.adaptToCurrent = function(){
  var optionsSelector = "#csetup-transport-options .options";
  $(optionsSelector).hide();
  $(optionsSelector + "." + clusterSetup.transportType.current()).show();

  clusterSetup.netmap.current.adaptToType();

  $("#csetup-transport-options")
    .toggleClass("knet", clusterSetup.transportType.current() === "knet")
    .toggleClass("udp", clusterSetup.transportType.current() !== "knet")
  ;
};


clusterSetup.transportType.current = function(){
  var checkedRadio = $("#csetup-transport [name='transport']:checked");
  if (checkedRadio.length === 0) {
    return clusterSetup.transportType.list[0];
  }

  return $("#csetup-transport [name='transport']:checked").attr("id").slice(
    clusterSetup.transportType.idPrefix.length
  );
};

//------------------------------------------------------------------------------

clusterSetup.snippet.transportLinks = function(transportType){
  return tools.snippet.take("transport-links-setting")
    .addClass(transportType)
    .hide()
  ;
};

clusterSetup.snippet.transportOptions = function(transportType){
  return tools.snippet
    .take("transport-options-"+clusterSetup.transportType.alias(transportType))
    .addClass(transportType)
  ;
};

clusterSetup.snippet.compile = function(){
  if (clusterSetup.state.compiled) {
    return;
  }
  clusterSetup.state.compiled = true;

  $("#csetup-transport .csetup-transport-sections").tabs({ active: 0 });

  $(clusterSetup.transportType.list).each(function(i, transportType){
    $("#csetup-transport-netmaps").append(
      clusterSetup.snippet.transportLinks(transportType)
    );
    $("#csetup-transport-options .options-container").append(
      clusterSetup.snippet.transportOptions(transportType)
    );
  });

  $("#csetup-transport [name='transport']").eq(0).trigger("click");
};

//------------------------------------------------------------------------------

clusterSetup.data.start = function(){
  return $("#csetup [name='auto_start']").is(":checked");
};

clusterSetup.data.fromForm = function(context, fields, normalize){
  normalize = normalize || function(name, value){ return value };
  var data = {};
  fields.forEach(function(name){
    var widget = $("[name='"+name+"']", context);
    if (widget.attr("type") === "checkbox") {
      data[name] = normalize(name, widget.is(":checked"));
    } else {
      var value = widget.val().trim();
      if (value) {
        data[name] = normalize(name, value);
      }
    }
  });
  return data;
};

clusterSetup.data.nameAndNodes = function(){
  return {
    clusterName: $('input[name^="clustername"]').val().trim(),
    nodesNames: tools.dialog.inputsToArray("#csetup [name='node[]']"),
  };
};

clusterSetup.data.validateNameAndNodes = function(formData){
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

clusterSetup.data.nodes = function(nodesNames, getAddrs){
  return nodesNames.map(function(nodeName){
    // The field addrs is here always. The details of backend is solved within
    // api.js module.
    return { name: nodeName, addrs: getAddrs ? getAddrs(nodeName) : [] };
  });
};

clusterSetup.data.setupMinimal = function(clusterName, nodesNames){
  return {
    clusterName: clusterName,
    nodeList: clusterSetup.data.nodes(nodesNames),
    transportType: undefined,
    totem: {},
    quorum: {},
    linkList: [],
    compression: {},
    crypto: {},
  };
};

clusterSetup.data.settings = function(clusterName, nodesNames){
  var fromForm = clusterSetup.data.fromForm;
  return $.extend(
    {
      clusterName: clusterName,
      nodeList: clusterSetup.data.nodes(nodesNames, function(nodeName){
        return clusterSetup.netmap.current.detailsContainer()
          .find("[name='"+clusterSetup.link.detail.addressName(nodeName)+"']")
          .map(function(){ return $(this).val().trim() })
          .toArray()
        ;
      }),
      transportType: clusterSetup.transportType.current(),
      totem: fromForm($("#csetup-totem"), [
        "consensus",
        "downcheck",
        "fail_recv_const",
        "heartbeat_failures_allowed",
        "hold",
        "join",
        "max_messages",
        "max_network_delay",
        "merge",
        "miss_count_const",
        "send_join",
        "seqno_unchanged_const",
        "token",
        "token_coefficient",
        "token_retransmit",
        "token_retransmits_before_loss_const",
        "window_size",
      ]),
      quorum: fromForm(
        $("#csetup-quorum"),
        [
          "auto_tie_breaker",
          "last_man_standing",
          "last_man_standing_window",
          "wait_for_all",
        ],
        function(name, value){
          if (
            [
              "auto_tie_breaker",
              "last_man_standing",
              "wait_for_all",
            ].includes(name)
          ) {
            return value == "on" ? "1" : "0";
          }
        },
      ),
    },

    clusterSetup.transportType.current() === "knet"

    ? {
      linkList: clusterSetup.netmap.current.detailList()
        .map(function(linknumber, form){
          return $.extend({linknumber: linknumber}, fromForm(form, [
            "link_priority",
            "mcastport",
            "ping_interval",
            "ping_precision",
            "ping_timeout",
            "pong_count",
            "transport",
          ]));
        })
        .toArray()
      ,

      transportOptions: fromForm(
        $("#csetup-transport-options .options-container .options.knet"),
        ["ip_version", "knet_pmtud_interval", "link_mode"],
      ),

      compression: fromForm(
        $("#csetup-transport-options .compression-options"),
        ["model", "threshold", "level"]
      ),

      crypto: fromForm(
        $("#csetup-transport-options .crypto-options"),
        ["model", "hash", "cipher"]
      ),
    }

    : {
      transportOptions: fromForm(
        $(
          "#csetup-transport-options .options-container .options."
          +
          clusterSetup.transportType.current()
        ),
        ["ip_version", "netmtu"],
      ),
      compression: {},
      crypto: {},
      linkList: clusterSetup.netmap.current.detailList()
        .map(function(linknumber, form){
          return fromForm(
            form,
            ["bindnetaddr", "broadcast", "mcastaddr", "mcastport", "ttl"],
            function(name, value){
              if (name === "broadcast"){
                return value == "yes" ? "1" : "0";
              }
            },
          );
        })
        .toArray()
    },
  );
};

clusterSetup.step.set = function(config){
  $("#csetup .step").hide();
  $("#csetup ."+config.stepForm).show();
  $("#csetup").dialog("option", "title", config.title);
  $("#csetup").dialog("option", "buttons", config.buttons);
};

clusterSetup.step.clusterNameNodes = function(){
  clusterSetup.step.set({
    stepForm: "cluster-name-nodes",
    title: "Create cluster: Cluster name and nodes",
    buttons: [
      {
        text: "Create cluster",
        click: function(){ clusterSetup.submit.run(false) },
      },
      {
        text: "Go to advanced settings",
        click: function(){ clusterSetup.submit.run(true) },
      },
      {
        text: "Cancel",
        click: clusterSetup.dialog.close,
      },
    ],
  });
};

clusterSetup.step.clusterSettings = function(clusterName, nodesNames, actions){
  clusterSetup.step.set({
    stepForm: "cluster-settings",
    title: "Create cluster "+clusterName+": Settings",
    buttons: [
      {
        text: "Back",
        click: actions.back,
      },
      {
        text: "Create cluster",
        click: actions.create,
      },
      {
        text: "Cancel",
        click: actions.cancel,
      },
    ],
  });

  $("#csetup .cluster-settings").tabs();

  clusterSetup.netmap.current.detailList().each(function(){
    clusterSetup.link.detail.refreshNodesNames($(this), nodesNames);
  });

  $("#csetup-transport-netmaps .add-link").unbind("click").click(function(){
    clusterSetup.netmap.current.createLink(
      clusterSetup.generateUid(),
      nodesNames
    );
  });

};

clusterSetup.step.clusterStart = function(clusterName, actions){
  clusterSetup.step.set({
    stepForm: "cluster-start",
    title: "Create cluster "+clusterName+": Start",
    buttons: [
      {
        text: "Finish",
        click: actions.finish,
      },
    ],
  });
};

//------------------------------------------------------------------------------

clusterSetup.dialog.create = function(){
  clusterSetup.snippet.compile(); 

  $("#csetup").dialog({
    closeOnEscape: false,
    dialogClass: "no-close",
    modal: false,
    resizable: false,
    width: 'auto',
  });

  clusterSetup.step.clusterNameNodes();
};

clusterSetup.dialog.close = function() {
  clusterSetup.state.multiStepErrors = [];
  clusterSetup.dialog.resetMessages([]);
  clusterSetup.step.clusterNameNodes();
  tools.dialog.close("#csetup")();
};

clusterSetup.dialog.setSubmitAbility = tools.dialog.setActionAbility(
   ".ui-dialog:has('#csetup') button:contains('Create cluster'),"
   +".ui-dialog:has('#csetup') button:contains('Go to advanced settings')"
);

clusterSetup.dialog.setSubmitAdvancedAbility = tools.dialog.setActionAbility(
   ".ui-dialog:has('#csetup') button:contains('Back'),"
   +".ui-dialog:has('#csetup') button:contains('Create cluster')"
);

clusterSetup.dialog.setSubmitStartAbility = tools.dialog.setActionAbility(
   ".ui-dialog:has('#csetup') button:contains('Finish')"
);

/**
  ok, noAuth, noConnect: array of node names
*/
clusterSetup.dialog.updateNodesByAuth = function(ok, noAuth, noConnect){
  $('#csetup input[name="node[]"]').each(function(){
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

clusterSetup.dialog.resetMessages = function(msgList){
  tools.dialog.resetMessages("#csetup")(
    clusterSetup.state.multiStepErrors.concat(msgList)
  );
};

clusterSetup.dialog.addNode = function(){
  var nodes = $("#csetup tr").has("[name='node[]']");

  var newNode = nodes.eq(0).clone();
  $("td:first-child", newNode).text("Node "+(nodes.length+1)+":");
  $("input[name='node[]']", newNode).val("");
  newNode.insertAfter(nodes.last());

  if (nodes.length == 7){
    $("#csetup tr ").has(".add-nodes").hide();
  }
};

clusterSetup.dialog.reset = function(){
  $('input[name="clustername"]').val("");
  tools.dialog.resetInputs([
    "#csetup [name='node[]']",
    "#csetup-quorum [type='text']",
    "#csetup-quorum select",
    "#csetup-totem [type='text']",
    "#csetup-quorum select",
    "#csetup-transport-netmaps [type='text']",
    "#csetup-transport-options select",
    "#csetup-transport-options [type='text']",
  ].join(","));
  $(".transport-link[data-transport-link-id]").map(function(){
    clusterSetup.netmap.current.deleteLink(
      $(this).attr("data-transport-link-id")
    );
  });
  $("[href='#csetup-transport-netmaps']").trigger("click");
  $("[href='#csetup-transport']").trigger("click");
  $("#csetup-transport-knet").trigger("click");
};

//------------------------------------------------------------------------------

clusterSetup.submit.onCallFail = tools.submit.onCallFail(
  clusterSetup.dialog.resetMessages
);

clusterSetup.submit.run = function(useAdvancedOptions){
  var formData = clusterSetup.data.nameAndNodes();

  var errors = clusterSetup.data.validateNameAndNodes(formData);
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
    if (!useAdvancedOptions) {
      return promise.resolve(clusterSetup.data.setupMinimal(
        formData.clusterName,
        formData.nodesNames
      ));
    }
    return promise.with(function(dialogPromise){
      clusterSetup.step.clusterSettings(
        formData.clusterName,
        formData.nodesNames,
        {
          back: function(){
            dialogPromise.reject(clusterSetup.const.BACK_TO_NODES);
          },
          create: function(){
            clusterSetup.dialog.setSubmitAdvancedAbility(false);
            dialogPromise.resolve(clusterSetup.data.settings(
              formData.clusterName,
              formData.nodesNames
            ));
          },
          cancel: function(){
            dialogPromise.reject(clusterSetup.const.CANCEL);
          },
        }
      );
    });


  }).then(function(setupData){
    clusterSetup.state.multiStepErrors = [];
    return api.clusterSetup(
      {
        setupData: setupData,
        setupCoordinatingNode: setupCoordinatingNode
      },
      {
        confirm: function(msgs){
          return tools.submit.confirmForce("setup cluster", msgs);
        },
      }
    );

  }).then(function(){
    clusterSetup.dialog.resetMessages([]);
    return api.rememberCluster(formData.clusterName, formData.nodesNames);

  }).then(function(){
    return promise.with(function(dialogPromise){
      clusterSetup.step.clusterStart(formData.clusterName, {
        finish: function(){
          clusterSetup.dialog.setSubmitStartAbility(false);
          dialogPromise.resolve(clusterSetup.data.start());
        },
      });
    });

  }).then(function(start){
    if (start) {
      return api.clusterStart(formData.clusterName, { all: true });
    }

  }).then(function(){
    Pcs.update();
    clusterSetup.dialog.reset();
    clusterSetup.dialog.close();

  }).fail(function(rejectCode, data){
    clusterSetup.dialog.setSubmitAbility(true);
    clusterSetup.dialog.setSubmitAdvancedAbility(true);
    clusterSetup.dialog.setSubmitStartAbility(true);
    switch(rejectCode){
      case api.err.CAN_ADD_CLUSTER_OR_NODES.FAILED:
        clusterSetup.submit.onCallFail(data.XMLHttpRequest, [400]);
        break;

      case api.err.NODES_AUTH_CHECK.FAILED:
        alert("ERROR: Unable to contact server");
        break;

      case api.err.NODES_AUTH_CHECK.WITH_ERR_NODES:
        auth_nodes_dialog(data.failNodes, function(){
          clusterSetup.submit.run(useAdvancedOptions);
        });
        break;

      case api.err.SEND_KNOWN_HOSTS.FAILED:
        clusterSetup.submit.onCallFail(data.XMLHttpRequest);
        break;

      case api.err.SEND_KNOWN_HOSTS.PCSD_ERROR:
        clusterSetup.dialog.resetMessages([{type: "error", msg: data.message}]);
        break;

      case clusterSetup.const.BACK_TO_NODES:
        clusterSetup.step.clusterNameNodes();
        break;

      case clusterSetup.const.CANCEL:
        clusterSetup.dialog.close();
        break;

      case api.err.CLUSTER_SETUP.FAILED:
        clusterSetup.submit.onCallFail(data.XMLHttpRequest);
        break;

      case api.err.CLUSTER_SETUP.PCS_LIB_ERROR:
        clusterSetup.step.clusterNameNodes();
        clusterSetup.state.multiStepErrors = data.msgList;
        clusterSetup.dialog.resetMessages([]);
        break;

      case api.err.CLUSTER_SETUP.CONFIRMATION_DENIED:
        clusterSetup.dialog.close();
        break;

      case api.err.CLUSTER_SETUP.PCS_LIB_EXCEPTION:
        clusterSetup.step.clusterNameNodes();
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
