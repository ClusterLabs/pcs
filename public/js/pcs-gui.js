function verify_remove() {
  var list_of_nodes = "<ul>";
  var nodes_to_remove = 0;
  $("#node_list :checked").each(function (index,element) {
    list_of_nodes += "<li>" + element.getAttribute("res_id")+"</li>";
    nodes_to_remove++;
  });
  list_of_nodes += "</ul>";
  if (nodes_to_remove != 0) {
    $("#resource_to_remove").replaceWith(list_of_nodes);
    $("#verify_remove").dialog({title: 'Resource Removal',
      modal: true, resizable: false, heigh: 140,
      buttons: {
	"Remove resource(s)": function() {
	  $(this).dialog("close");
	},
      Cancel: function() {
	$(this).dialog("close");
      }}
    });
  } else {
    alert("You must select at least one node.");
  }
}
