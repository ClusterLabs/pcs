import sys
import usage
import utils
import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parseString
from collections import defaultdict

def constraint_cmd(argv):
    if len(argv) == 0:
        argv = ["list"]

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.constraint()
    elif (sub_cmd == "location"):
        if len (argv) == 0:
            sub_cmd2 = "show"
        else:
            sub_cmd2 = argv.pop(0)

        if (sub_cmd2 == "add"):
            location_add(argv)
        elif (sub_cmd2 == "rm"):
            location_add(argv,True)
        elif (sub_cmd2 == "show"):
            location_show(argv)
        elif len(argv) >= 2:
            location_prefer([sub_cmd2] + argv)
        else:
            usage.constraint()
            sys.exit(1)
    elif (sub_cmd == "order"):
        if (len(argv) == 0):
            sub_cmd2 = "show"
        else:
            sub_cmd2 = argv.pop(0)

        if (sub_cmd2 == "list"):
            order_list(argv)
        elif (sub_cmd2 == "add"):
            order_add(argv)
        elif (sub_cmd2 == "rm"):
            order_rm(argv)
        elif (sub_cmd2 == "show"):
            order_show(argv)
        else:
            order_start([sub_cmd2] + argv)
    elif (sub_cmd == "colocation"):
        if (len(argv) == 0):
            sub_cmd2 = "show"
        else:
            sub_cmd2 = argv.pop(0)

        if (sub_cmd2 == "add"):
            colocation_add(argv)
        elif (sub_cmd2 == "rm"):
            colocation_rm(argv)
        elif (sub_cmd2 == "show"):
            colocation_show(argv)
        else:
            usage.constraint()
            sys.exit(1)
    elif (sub_cmd == "rm"):
        constraint_rm(argv)
    elif (sub_cmd == "show" or sub_cmd == "list"):
        location_show(argv)
        order_show(argv)
        colocation_show(argv)
    elif (sub_cmd == "all"):
        location_show(["all"])
        order_show(["all"])
        colocation_show(["all"])
    elif (sub_cmd == "ref"):
        constraint_ref(argv)
    else:
        usage.constraint()
        sys.exit(1)

def colocation_show(argv):
    if (len(argv) != 0 and argv[0] == "all"):
        showDetail = True
    else:
        showDetail = False

    (dom,constraintsElement) = getCurrentConstraints()

    print "Colocation Constraints:"
    for co_loc in constraintsElement.getElementsByTagName('rsc_colocation'):
        co_resource1 = co_loc.getAttribute("rsc")
        co_resource2 = co_loc.getAttribute("with-rsc")
        co_id = co_loc.getAttribute("id")
        co_score = co_loc.getAttribute("score")
        score_text = "" if (co_score == "INFINITY") and not showDetail else " (" + co_score + ")"
        co_id_out = ""
        for attr in co_loc.attributes.items():
            name = attr[0]
            value = attr[1]
            if name != "rsc" and name != "with-rsc" and name != "id" and name != "score":
                co_id_out += " (" + name+":"+value+")"

        if showDetail:
            co_id_out += " (id:"+co_id+")"

        print "  " + co_resource1 + " with " + co_resource2 + score_text + co_id_out

def colocation_rm(argv):
    elementFound = False
    if len(argv) < 2:
        usage.constraint()
        sys.exit(1)

    (dom,constraintsElement) = getCurrentConstraints()

    resource1 = argv[0]
    resource2 = argv[1]

    for co_loc in constraintsElement.getElementsByTagName('rsc_colocation')[:]:
        if co_loc.getAttribute("rsc") == resource1 and co_loc.getAttribute("with-rsc") == resource2:
            constraintsElement.removeChild(co_loc)
            elementFound = True
        if co_loc.getAttribute("rsc") == resource2 and co_loc.getAttribute("with-rsc") == resource1:
            constraintsElement.removeChild(co_loc)
            elementFound = True

    if elementFound == True:
        xml_constraint_string = constraintsElement.toxml()
        args = ["cibadmin", "-c", "-R", "--xml-text", xml_constraint_string]
        output,retval = utils.run(args)
        if output != "":
            print output
    else:
        print "No matching resources found in ordering list"


# When passed an array of arguments if the first argument doesn't have an '='
# then it's the score, otherwise they're all arguments
# Return a tuple with the score and array of name,value pairs
def parse_score_options(argv):
    if len(argv) == 0:
        return "INFINITY",[]

    arg_array = []
    first = argv[0]
    if first.find('=') != -1:
        score = "INFINITY"
    else:
        score = argv.pop(0)

    for arg in argv:
        args = arg.split('=')
        if (len(args) != 2):
            continue
        arg_array.append(args)
    return (score, arg_array)

def colocation_add(argv):
    if len(argv) < 2:
        usage.constraint()
        sys.exit(1)

    resource1 = argv.pop(0)
    resource2 = argv.pop(0)

    if not utils.does_resource_exist(resource1):
        print "Error: Resource '" + resource1 + "' does not exist"
        sys.exit(1)

    if not utils.does_resource_exist(resource2):
        print "Error: Resource '" + resource2 + "' does not exist"
        sys.exit(1)

    score,nv_pairs = parse_score_options(argv)

    (dom,constraintsElement) = getCurrentConstraints()
    cl_id = utils.find_unique_id(dom, "colocation-" + resource1 + "-" +
            resource2 + "-" + score)

    element = dom.createElement("rsc_colocation")
    element.setAttribute("id",cl_id)
    element.setAttribute("rsc",resource1)
    element.setAttribute("with-rsc",resource2)
    element.setAttribute("score",score)
    for nv_pair in nv_pairs:
        element.setAttribute(nv_pair[0], nv_pair[1])
    constraintsElement.appendChild(element)
    xml_constraint_string = constraintsElement.toxml()
    args = ["cibadmin", "-c", "-R", "--xml-text", xml_constraint_string]
    output,retval = utils.run(args)
    if output != "":
        print output

def order_show(argv):
    if (len(argv) != 0 and argv[0] == "all"):
        showDetail = True
    else:
        showDetail = False

    (dom,constraintsElement) = getCurrentConstraints()

    print "Ordering Constraints:"
    for ord_loc in constraintsElement.getElementsByTagName('rsc_order'):
        oc_resource1 = ord_loc.getAttribute("first")
        oc_resource2 = ord_loc.getAttribute("then")
        first_action = ord_loc.getAttribute("first-action")
        then_action = ord_loc.getAttribute("then-action")
        if first_action != "":
            first_action = first_action + " "
        if then_action != "":
            then_action = then_action + " "
        oc_id = ord_loc.getAttribute("id")
        oc_score = ord_loc.getAttribute("score")
        oc_kind = ord_loc.getAttribute("kind")
        oc_sym = ""
        oc_id_out = ""
        if ord_loc.getAttribute("symmetrical") == "false":
            oc_sym = " (non-symmetrical)"
        if oc_kind != "":
            oc_score = oc_kind
        if oc_kind == "" and oc_score == "":
            oc_score = "Mandatory"
        score_text = "" if (oc_score == "INFINITY" or oc_score == "Mandatory") and not showDetail else " (" + oc_score + ")"
        if showDetail:
            oc_id_out = " (id:"+oc_id+")"
        print "  " + first_action + oc_resource1 + " then " + then_action + oc_resource2 + score_text + oc_sym + oc_id_out

def order_list(argv):
    for i in range(0,len(argv)-1):
        order_add([argv[i], argv[i+1], "INFINITY"])

def order_rm(argv):
    if len(argv) == 0:
        usage.constraint()
        sys.exit(1)

    elementFound = False
    (dom,constraintsElement) = getCurrentConstraints()

    for resource in argv:
        for ord_loc in constraintsElement.getElementsByTagName('rsc_order')[:]:
            if ord_loc.getAttribute("first") == resource or ord_loc.getAttribute("then") == resource:
                constraintsElement.removeChild(ord_loc)
                elementFound = True

    if elementFound == True:
        xml_constraint_string = constraintsElement.toxml()
        args = ["cibadmin", "-c", "-R", "--xml-text", xml_constraint_string]
        output,retval = utils.run(args)
        if output != "":
            print output
    else:
        print "No matching resources found in ordering list"

def order_start(argv):
    if len(argv) < 3:
        usage.constraint()
        sys.exit(1)

    first_action = "start"
    then_action = "start"
    action = argv[0]
    if action == "start" or action == "promote" or action == "stop" or action == "demote":
            first_action = action
            argv.pop(0)

    resource1 = argv.pop(0)
    if argv.pop(0) != "then":
        usage.constraint()
        sys.exit(1)
    
    if len(argv) == 0:
        usage.constraint()
        sys.exit(1)

    action = argv[0]
    if action == "start" or action == "promote" or action == "stop" or action == "demote":
            then_action = action
            argv.pop(0)

    if len(argv) == 0:
        usage.constraint()
        sys.exit(1)
    resource2 = argv.pop(0)

    order_options = []
    if len(argv) != 0:
        order_options = order_options + argv[:]

    order_options.append("first-action="+first_action)
    order_options.append("then-action="+then_action)
    order_add([resource1, resource2] + order_options)

def order_add(argv,returnElementOnly=False):
    if len(argv) < 2:
        usage.constraint()
        sys.exit(1)

    resource1 = argv.pop(0)
    resource2 = argv.pop(0)

    if not utils.does_resource_exist(resource1):
        print "Error: Resource '" + resource1 + "' does not exist"
        sys.exit(1)

    if not utils.does_resource_exist(resource2):
        print "Error: Resource '" + resource2 + "' does not exist"
        sys.exit(1)

    sym = "true" if (len(argv) == 0 or argv[0] != "nonsymmetrical") else "false"

    order_options = []
    if len(argv) != 0:
        if argv[0] == "nonsymmetrical" or argv[0] == "symmetrical":
            argv.pop(0)
        for arg in argv:
            if arg.count("=") == 1:
                mysplit = arg.split("=")
                order_options.append((mysplit[0],mysplit[1]))

    if len(argv) != 0:
        options = " (Options: " + " ".join(argv)+")"
    else:
        options = ""

    scorekind = "kind: Mandatory"
    id_suffix = "mandatory"
    for opt in order_options:
        if opt[0] == "score":
            scorekind = "score: " + opt[1]
            id_suffix = opt[1]
            break
        if opt[0] == "kind":
            scorekind = "kind: " + opt[1]
            id_suffix = opt[1]
            break

    print "Adding " + resource1 + " " + resource2 + " ("+scorekind+")" + options

    order_id = "order-" + resource1 + "-" + resource2 + "-" + id_suffix
    if utils.does_id_exist(utils.get_cib_dom(), order_id):
        print "Error: Unable to create constraint, similar constraint already exists: %s" % order_id
        sys.exit(1)

    (dom,constraintsElement) = getCurrentConstraints()
    element = dom.createElement("rsc_order")
    element.setAttribute("id",order_id)
    element.setAttribute("first",resource1)
    element.setAttribute("then",resource2)
    for order_opt in order_options:
        element.setAttribute(order_opt[0], order_opt[1])
    if (sym == "false"):
        element.setAttribute("symmetrical", "false")
    constraintsElement.appendChild(element)

    if returnElementOnly == False:
        xml_constraint_string = constraintsElement.toxml()
        args = ["cibadmin", "-o", "constraints", "-R", "--xml-text", xml_constraint_string]
        output,retval = utils.run(args)
        if output != "":
            print output
        if retval != 0:
            sys.exit(1)
    else:
        return element.toxml()

# Show the currently configured location constraints by node or resource
def location_show(argv):
    if (len(argv) != 0 and argv[0] == "nodes"):
        byNode = True
        showDetail = False
    elif (len(argv) != 0 and argv[0] == "all"):
        byNode = False
        showDetail = True
    else:
        byNode = False
        showDetail = False

    if len(argv) > 1:
        valid_noderes = argv[1:]
    else:
        valid_noderes = []

    (dom,constraintsElement) = getCurrentConstraints()
    nodehashon = {}
    nodehashoff = {}
    rschashon = {}
    rschashoff = {}
    ruleshash = defaultdict(list)
    all_loc_constraints = constraintsElement.getElementsByTagName('rsc_location')

    print "Location Constraints:"
    for rsc_loc in all_loc_constraints:
        lc_node = rsc_loc.getAttribute("node")
        lc_rsc = rsc_loc.getAttribute("rsc")
        lc_id = rsc_loc.getAttribute("id")
        lc_score = rsc_loc.getAttribute("score")

        rules = rsc_loc.getElementsByTagName('rule')
        if len(rules) > 0:
            for rule in rules:
                rule_score = rule.getAttribute("score")
                for exp in rule.getElementsByTagName('expression'):
                    attr = exp.getAttribute("attribute")
                    operation = exp.getAttribute("operation")
                    value = exp.getAttribute("value")
                    ruleshash[lc_rsc].append([lc_id,"%s %s %s" % (attr, operation, value), rule_score])

# NEED TO FIX FOR GROUP LOCATION CONSTRAINTS (where there are children of
# rsc_location)
        if lc_score == "":
            lc_score = "0";

        if lc_score == "INFINITY":
            positive = True
        elif lc_score == "-INFINITY":
            positive = False
        elif int(lc_score) >= 0:
            positive = True
        else:
            positive = False

        if positive == True:
            nodeshash = nodehashon
            rschash = rschashon
        else:
            nodeshash = nodehashoff
            rschash = rschashoff

        if lc_node in nodeshash:
            nodeshash[lc_node].append((lc_id,lc_rsc,lc_score))
        else:
            nodeshash[lc_node] = [(lc_id, lc_rsc,lc_score)]

        if lc_rsc in rschash:
            rschash[lc_rsc].append((lc_id,lc_node,lc_score))
        else:
            rschash[lc_rsc] = [(lc_id,lc_node,lc_score)]

    nodelist = list(set(nodehashon.keys() + nodehashoff.keys()))
    rsclist = list(set(rschashon.keys() + rschashoff.keys()))

    if byNode == True:
        for node in nodelist:
            if len(valid_noderes) != 0:
                if node not in valid_noderes:
                    continue
            print "  Node: " + node

            if (node in nodehashon):
                print "    Allowed to run:"
                for options in nodehashon[node]:
                    print "      " + options[1] +  " (" + options[0] + ")",
                    if (options[2] == "INFINITY"):
                        print ""
                    else:
                        print "Score: "+ options[2]

            if (node in nodehashoff):
                print "    Not allowed to run:"
                for options in nodehashoff[node]:
                    print "      " + options[1] +  " (" + options[0] + ")",
                    if (options[2] == "-INFINITY"):
                        print ""
                    else:
                        print "Score: "+ options[2]
    else:
        for rsc in rsclist:
            if len(valid_noderes) != 0:
                if rsc not in valid_noderes:
                    continue
            print "  Resource: " + rsc
            if (rsc in rschashon):
                for options in rschashon[rsc]:
                    if options[1] == "":
                        continue
                    print "    Enabled on:",
                    print options[1],
                    if options[2] != "INFINITY" or showDetail:
                        print "(score:"+options[2]+")",
                    if showDetail:
                        print "(id:"+options[0]+")",
                    print
            if (rsc in rschashoff):
                print "    Disabled on:",
                for options in rschashoff[rsc]:
                    print options[1],
                    if options[2] != "-INFINITY" or showDetail:
                        print "("+options[2]+")",
                    if showDetail:
                        print "(id:"+options[0]+")",
                print ""
    for rsc in ruleshash:
        for res_id,rule,score in ruleshash[rsc]:
            print "    Rule: " + rule + " (score:%s)" % (score),
            if showDetail:
                print "(id:%s)" % (res_id),
            print ""

def location_prefer(argv):
    rsc = argv.pop(0)
    prefer_option = argv.pop(0)

    if prefer_option == "prefers":
        prefer = True
    elif prefer_option == "avoids":
        prefer = False
    else:
        usage.constraint()
        sys.exit(1)


    for nodeconf in argv:
        nodeconf_a = nodeconf.split("=",1)
        if len(nodeconf_a) == 1:
            node = nodeconf_a[0]
            if prefer:
                score = "INFINITY"
            else:
                score = "-INFINITY"
        else:
            score = nodeconf_a[1]
            if not prefer:
                if score[0] == "-":
                    score = score[1:]
                else:
                    score = "-" + score
            node = nodeconf_a[0]
        location_add(["location-" +rsc+"-"+node+"-"+score,rsc,node,score])
        

def location_add(argv,rm=False):
    if len(argv) != 4 and (rm == False or len(argv) < 1): 
        usage.constraint()
        sys.exit(1)

    constraint_id = argv.pop(0)

    # If we're removing, we only care about the id
    if (rm == True):
        resource_name = ""
        node = ""
        score = ""
    else:
        resource_name = argv.pop(0)
        node = argv.pop(0)
        score = argv.pop(0)
        # If resource doesn't exist, we error out
        if not utils.does_resource_exist(resource_name):
            print "Error: Resource " + resource_name + "' does not exist"
            sys.exit(1)

    # Verify current constraint doesn't already exist
    # If it does we replace it with the new constraint
    (dom,constraintsElement) = getCurrentConstraints()
    elementsToRemove = []

    # If the id matches, or the rsc & node match, then we replace/remove
    for rsc_loc in constraintsElement.getElementsByTagName('rsc_location'):
        if (constraint_id == rsc_loc.getAttribute("id")) or \
                (rsc_loc.getAttribute("rsc") == resource_name and \
                rsc_loc.getAttribute("node") == node and not rm):
            elementsToRemove.append(rsc_loc)

    for etr in elementsToRemove:
        constraintsElement.removeChild(etr)

    if (rm == True and len(elementsToRemove) == 0):
        print "Resource location id: " + constraint_id + " not found."
        sys.exit(1)

    if (not rm):
        element = dom.createElement("rsc_location")
        element.setAttribute("id",constraint_id)
        element.setAttribute("rsc",resource_name)
        element.setAttribute("node",node)
        element.setAttribute("score",score)
        constraintsElement.appendChild(element)
    xml_constraint_string = constraintsElement.toxml()

    args = ["cibadmin", "-c", "-R", "--xml-text", xml_constraint_string]
    output,retval = utils.run(args)
    if output != "":
        print output

# Grabs the current constraints and returns the dom and constraint element
def getCurrentConstraints():
    current_constraints_xml = utils.get_cib_xpath('//constraints')

    if current_constraints_xml == "":
        print "Error: unable to process cib"
        sys.exit(1)
    # Verify current constraint doesn't already exist
    # If it does we replace it with the new constraint
    dom = parseString(current_constraints_xml)
    constraintsElement = dom.getElementsByTagName('constraints')[0]
    return (dom, constraintsElement)

def constraint_rm(argv):
    if len(argv) < 1:
        usage.constraint()
        sys.exit(1)

    if len(argv) != 1:
        for arg in argv:
            constraint_rm([arg])
        return
    else:
        c_id = argv.pop(0)

    elementFound = False
    (dom,constraintsElement) = getCurrentConstraints()

    for co in constraintsElement.childNodes[:]:
        if co.nodeType != xml.dom.Node.ELEMENT_NODE:
            continue
        if co.getAttribute("id") == c_id:
            constraintsElement.removeChild(co)
            elementFound = True

    if elementFound == True:
        xml_constraint_string = constraintsElement.toxml()
        args = ["cibadmin", "-c", "-R", "--xml-text", xml_constraint_string]
        output,retval = utils.run(args)
        if output != "":
            print output
    else:
        print "No matching resources found in ordering list"

def constraint_ref(argv):
    if len(argv) == 0:
        usage.constraint()
        sys.exit(1)

    for arg in argv:
        print "Resource: %s" % arg
        constraints = find_constraints_containing(arg)
        if len(constraints) == 0:
            print "  No Matches."
        else:
            for constraint in constraints:
                print "  " + constraint

def find_constraints_containing(resource_id):
    dom = utils.get_cib_dom()
    constraints_found = []

    resources = dom.getElementsByTagName("primitive")
    resource_match = None
    for res in resources:
        if res.getAttribute("id") == resource_id:
            resource_match = res
            break

    if resource_match:
        if resource_match.parentNode.tagName == "master" or resource_match.parentNode.tagName == "clone":
            constraints_found = find_constraints_containing(resource_match.parentNode.getAttribute("id"))

    constraints = dom.getElementsByTagName("constraints")
    if len(constraints) == 0:
        return []
    else:
        constraints = constraints[0]

    myConstraints = constraints.getElementsByTagName("rsc_colocation")
    myConstraints += constraints.getElementsByTagName("rsc_location")
    myConstraints += constraints.getElementsByTagName("rsc_order")
    attr_to_match = ["rsc", "first", "then", "with-rsc", "first", "then"]
    for c in myConstraints:
        for attr in attr_to_match:
            if c.getAttribute(attr) == resource_id:
                constraints_found.append(c.getAttribute("id"))
                break
    return constraints_found

# Re-assign any constraints referencing a resource to its parent (a clone
# or master)
def constraint_resource_update(old_id):
    dom = utils.get_cib_dom()
    resources = dom.getElementsByTagName("primitive")
    found_resource = None
    for res in resources:
        if res.getAttribute("id") == old_id:
            found_resource = res
            break

    new_id = None
    if found_resource:
        if found_resource.parentNode.tagName == "master" or found_resource.parentNode.tagName == "clone":
            new_id = found_resource.parentNode.getAttribute("id")

    if new_id:
        constraints = dom.getElementsByTagName("rsc_location")
        constraints += dom.getElementsByTagName("rsc_order")
        constraints += dom.getElementsByTagName("rsc_colocation")
        attrs_to_update=["rsc","first","then", "with-rsc"]
        for constraint in constraints:
            for attr in attrs_to_update:
                if constraint.getAttribute(attr) == old_id:
                    constraint.setAttribute(attr, new_id)


        update = dom.getElementsByTagName("constraints")[0].toxml()
        output, retval = utils.run(["cibadmin", "--replace", "-o", "constraints", "-X", update])

