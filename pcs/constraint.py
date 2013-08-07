import sys
import usage
import utils
import resource
import xml.dom.minidom
import xml.etree.ElementTree as ET
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parseString
from collections import defaultdict

def constraint_cmd(argv):
    if len(argv) == 0:
        argv = ["list"]

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.constraint(argv)
    elif (sub_cmd == "location"):
        if len (argv) == 0:
            sub_cmd2 = "show"
        else:
            sub_cmd2 = argv.pop(0)

        if (sub_cmd2 == "add"):
            location_add(argv)
        elif (sub_cmd2 == "remove"):
            location_add(argv,True)
        elif (sub_cmd2 == "show"):
            location_show(argv)
        elif len(argv) >= 2:
            if argv[0] == "rule":
                location_rule([sub_cmd2] + argv)
            else:
                location_prefer([sub_cmd2] + argv)
        else:
            usage.constraint()
            sys.exit(1)
    elif (sub_cmd == "order"):
        if (len(argv) == 0):
            sub_cmd2 = "show"
        else:
            sub_cmd2 = argv.pop(0)

        if (sub_cmd2 == "set"):
            order_set(argv)
        elif (sub_cmd2 == "remove"):
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
        elif (sub_cmd2 == "remove"):
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
    elif (sub_cmd == "ref"):
        constraint_ref(argv)
    elif (sub_cmd == "rule"):
        constraint_rule(argv)
    else:
        usage.constraint()
        sys.exit(1)

def colocation_show(argv):
    if "--full" in utils.pcs_options:
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

# There are two acceptable syntaxes
# Deprecated - colocation add <src> <tgt> [score] [options]
# Supported - colocation add [role] <src> with [role] <tgt> [score] [options]
def colocation_add(argv):
    if len(argv) < 2:
        usage.constraint()
        sys.exit(1)

    role1 = ""
    role2 = ""
    if len(argv) > 2:
        if not utils.is_score_or_opt(argv[2]):
            if argv[2] == "with":
                role1 = argv.pop(0).lower().capitalize()
                resource1 = argv.pop(0)
            else:
                resource1 = argv.pop(0)

            argv.pop(0) # Pop 'with'

            if len(argv) == 1:
                resource2 = argv.pop(0)
            else:
                if utils.is_score_or_opt(argv[1]):
                    resource2 = argv.pop(0)
                else:
                    role2 = argv.pop(0).lower().capitalize()
                    resource2 = argv.pop(0)
        else:
            resource1 = argv.pop(0)
            resource2 = argv.pop(0)
    else:
        resource1 = argv.pop(0)
        resource2 = argv.pop(0)

    if not utils.is_valid_constraint_resource(resource1):
        utils.err("Resource '" + resource1 + "' does not exist")

    if not utils.is_valid_constraint_resource(resource2):
        utils.err("Resource '" + resource2 + "' does not exist")

    score,nv_pairs = parse_score_options(argv)

    (dom,constraintsElement) = getCurrentConstraints()
    cl_id = utils.find_unique_id(dom, "colocation-" + resource1 + "-" +
            resource2 + "-" + score)

# If one role is specified, the other should default to "started"
    if role1 != "" and role2 == "":
        role2 = "Started"
    if role2 != "" and role1 == "":
        role1 = "Started"

    element = dom.createElement("rsc_colocation")
    element.setAttribute("id",cl_id)
    element.setAttribute("rsc",resource1)
    element.setAttribute("with-rsc",resource2)
    element.setAttribute("score",score)
    if role1 != "":
        element.setAttribute("rsc-role", role1)
    if role2 != "":
        element.setAttribute("with-rsc-role", role2)
    for nv_pair in nv_pairs:
        element.setAttribute(nv_pair[0], nv_pair[1])
    constraintsElement.appendChild(element)
    xml_constraint_string = constraintsElement.toxml()
    args = ["cibadmin", "-c", "-R", "--xml-text", xml_constraint_string]
    output,retval = utils.run(args)
    if output != "":
        print output

def order_show(argv):
    if "--full" in utils.pcs_options:
        showDetail = True
    else:
        showDetail = False

    (dom,constraintsElement) = getCurrentConstraints()

    resource_order_sets = []
    print "Ordering Constraints:"
    for ord_loc in constraintsElement.getElementsByTagName('rsc_order'):
        oc_resource1 = ord_loc.getAttribute("first")
        if oc_resource1 == "":
            resource_order_sets.append(ord_loc)
            continue
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

    if len(resource_order_sets) != 0:
        print "  Resource Sets:"
        for ro in resource_order_sets:
            output = ""
            for rs in ro.getElementsByTagName("resource_set"):
                output += " set"
                for rr in rs.getElementsByTagName("resource_ref"):
                    output += " " + rr.getAttribute("id")
                for name,value in rs.attributes.items():
                    if name == "id":
                        continue
                    output += " " + name + "=" + value
                if showDetail:
                    output += " (id:"+rs.getAttribute("id")+")"
            if showDetail:
                output += " (id:" + ro.getAttribute("id") + ")"
            print "   "+output

def order_set(argv,retval = False):
    current_set = []
    current_nodes = []
    for i in range(len(argv)):
        if argv[i] == "set" and len(argv) >= i:
            current_set = current_set + order_set(argv[i+1:], True)
            break
        current_nodes.append(argv[i])
    current_set = [current_nodes] + current_set

    if retval:
        return current_set
    else:
        cib = utils.get_cib_etree()
        constraints = cib.find(".//constraints")
        if constraints == None:
            constraints = ET.SubElement(cib, "constraints")
        rsc_order = ET.SubElement(constraints,"rsc_order")
        rsc_order.set("id", utils.find_unique_id(cib,"pcs_rsc_order"))
        for o_set in current_set:
            res_set = ET.SubElement(rsc_order,"resource_set")
            res_set.set("id", utils.find_unique_id(cib,"pcs_rsc_set"))
            for opts in o_set:
                if opts.find("=") != -1:
                    key,val = opts.split("=")
                    res_set.set(key,val)
                else:
                    se = ET.SubElement(res_set,"resource_ref")
                    se.set("id",opts)
        utils.replace_cib_configuration(cib)

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

    if not utils.is_valid_constraint_resource(resource1):
        utils.err("Resource '" + resource1 + "' does not exist")

    if not utils.is_valid_constraint_resource(resource2):
        utils.err("Resource '" + resource2 + "' does not exist")

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
        utils.err("Unable to create constraint, similar constraint already exists: %s" % order_id)

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
    elif "--full" in utils.pcs_options:
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
    datespechash = defaultdict(list)
    all_loc_constraints = constraintsElement.getElementsByTagName('rsc_location')

    print "Location Constraints:"
    for rsc_loc in all_loc_constraints:
        lc_node = rsc_loc.getAttribute("node")
        lc_rsc = rsc_loc.getAttribute("rsc")
        lc_id = rsc_loc.getAttribute("id")
        lc_score = rsc_loc.getAttribute("score")
        lc_name = "Resource: " + lc_rsc

        rules = rsc_loc.getElementsByTagName('rule')
        if len(rules) > 0:
            for rule in rules:
                exphash = []
                rule_score = rule.getAttribute("score")
                rule_string = ""
                for n,v in rule.attributes.items():
                    if n != "id":
                        rule_string += n + "=" + v + " " 
                rule_id = rule.getAttribute("id")
                for exp in rule.childNodes:
                    if exp.nodeType == xml.dom.minidom.Node.TEXT_NODE:
                        continue
                    exp_string = ""
                    exp_string_start = ""
                    if exp.tagName == "expression":
                        if "value" in exp.attributes.keys():
                            exp_string_start = exp.getAttribute("attribute") + " " + exp.getAttribute("operation") + " " + exp.getAttribute("value")
                        else:
                            exp_string_start = exp.getAttribute("operation") + " " + exp.getAttribute("attribute")

                    for n,v in exp.attributes.items():
                        if exp.tagName == "expression" and (n == "attribute" or n == "operation" or n == "value"):
                            continue
                        if n != "id":
                            exp_string += n + "=" + v + " " 
                        if n == "operation" and v == "date_spec":
                            for ds in exp.childNodes:
                                if ds.nodeType == xml.dom.minidom.Node.TEXT_NODE:
                                    continue
                                ds_string = ""
                                for n2,v2 in ds.attributes.items():
                                    if n2 != "id":
                                        ds_string += n2 + "=" + v2+ " "
                                datespechash[exp.getAttribute("id")].append([ds.getAttribute("id"),ds_string])

                    exp_full_string = ""
                    if exp_string_start != "":
                        exp_full_string = exp_string_start + " "
                    exp_full_string += exp_string

                    exphash.append([exp.getAttribute("id"),exp_full_string])
                ruleshash[lc_name].append([rule_id, rule_string, exphash]) 

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
        show_location_rules(ruleshash,showDetail,datespechash)
    else:
        rsclist.sort()
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
                        print "(score:"+options[2]+")",
                    if showDetail:
                        print "(id:"+options[0]+")",
                print ""
            miniruleshash={}
            miniruleshash["Resource: " + rsc] = ruleshash["Resource: " + rsc]
            show_location_rules(miniruleshash,showDetail,datespechash, True)

def show_location_rules(ruleshash,showDetail,datespechash,noheader=False):
    for rsc in ruleshash:
        if not noheader:
            print "  " + rsc
        for res_id,rule,exphash in ruleshash[rsc]:
            print "      Rule: " + rule,
            if showDetail:
                print "(id:%s)" % (res_id),
            print ""
            for exp_id,exp in exphash:
                print "        Expression: " + exp,
                if showDetail:
                    print "(id:%s)" % (exp_id),
                print ""
                for ds_id, ds in datespechash[exp_id]:
                    print "          Date Spec: " + ds,
                    if showDetail:
                        print "(id:%s)" % (ds_id),
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
        if not utils.is_valid_constraint_resource(resource_name):
            utils.err("Resource " + resource_name + "' does not exist")

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
        utils.err("resource location id: " + constraint_id + " not found.")

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

def location_rule(argv):
    if len(argv) < 3:
        usage.constraint("location rule")
        sys.exit(1)
    
    res_name = argv.pop(0)

    (dom, constraintsElement) = getCurrentConstraints()

    lc = dom.createElement("rsc_location")
    lc_id = utils.find_unique_id(dom, "location-" + res_name)
    lc.setAttribute("id", lc_id)
    lc.setAttribute("rsc", res_name)

    rule = utils.getRule(dom, lc, argv)
    lc.appendChild(rule)
    constraintsElement.appendChild(lc)

    utils.replace_cib_configuration(dom)
    
# Grabs the current constraints and returns the dom and constraint element
def getCurrentConstraints():
    current_constraints_xml = utils.get_cib_xpath('//constraints')

    if current_constraints_xml == "":
        utils.err("unable to process cib")
    # Verify current constraint doesn't already exist
    # If it does we replace it with the new constraint
    dom = parseString(current_constraints_xml)
    constraintsElement = dom.getElementsByTagName('constraints')[0]
    return (dom, constraintsElement)

# If returnStatus is set, then we don't error out, we just print the error
# and return false
def constraint_rm(argv,returnStatus=False, constraintsElement=None):
    if len(argv) < 1:
        usage.constraint()
        sys.exit(1)

    bad_constraint = False
    if len(argv) != 1:
        for arg in argv:
            if not constraint_rm([arg],True):
                bad_constraint = True
        if bad_constraint:
            sys.exit(1)
        return
    else:
        c_id = argv.pop(0)

    elementFound = False

    if not constraintsElement:
        (dom, constraintsElement) = getCurrentConstraints()
        use_cibadmin = True
    else:
        use_cibadmin = False
        
    for co in constraintsElement.childNodes[:]:
        if co.nodeType != xml.dom.Node.ELEMENT_NODE:
            continue
        if co.getAttribute("id") == c_id:
            constraintsElement.removeChild(co)
            elementFound = True

    if elementFound == True:
        if use_cibadmin:
            xml_constraint_string = constraintsElement.toxml()
            args = ["cibadmin", "-c", "-R", "--xml-text", xml_constraint_string]
            output,retval = utils.run(args)
            if output != "":
                print output
    else:
        print >> sys.stderr, "Error: Unable to find constraint - '%s'" % c_id
        if not returnStatus:
            sys.exit(1)

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

def constraint_rule(argv):
    if len(argv) < 2:
        usage.constraint("rule")
        sys.exit(1)

    found = False
    command = argv.pop(0)


    constraint_id = None
    rule_id = None
    cib = utils.get_cib_etree()

    if command == "add":
        constraint_id = argv.pop(0)
        constraint = None

        rule_type = "expression"
        if len(argv) != 0:
            if argv[1].find('=') == -1:
                rule_type = argv[1]

        if rule_type != "expression" and rule_type != "date_expression":
            utils.err("rule_type must either be expression or date_expression")

        for a in cib.findall(".//configuration//"):
            if a.get("id") == constraint_id and a.tag == "rsc_location":
                found = True
                constraint = a

        if not found:
            utils.err("Unable to find constraint: " + constraint_id)

        rule = ET.SubElement(constraint,"rule")
        expression = ET.SubElement(rule,rule_type)
        args = resource.convert_args_to_tuples(argv)
        dict_args = dict()
        for k,v in args:
            dict_args[k] = v
        if rule_type == "expression": 
            if "operation" not in dict_args or "attribute" not in dict_args:
                utils.err("with rule_type: expression you must specify an attribute and operation")
        elif rule_type == "date_expression":
            if "operation" not in dict_args or ("start" not in dict_args and "stop" not in dict_args):
                utils.err("with rule_type: date_expression you must specify an operation and a start/end")

        for arg in args:
            if arg[0] == "id" or arg[0] == "score":
                rule.set(arg[0], arg[1])
            else:
                expression.set(arg[0],arg[1])

        if rule.get("score") == None and rule.get("score-attribute") == None:
            rule.set("score", "INFINITY")

        dom = utils.get_cib_dom()
        if rule.get("id") == None:
            rule.set("id", utils.find_unique_id(dom,constraint.get("id") + "-rule"))
        if expression.get("id") == None:
            expression.set("id", utils.find_unique_id(dom,rule.get("id") + "-expr"))
        if "score" in constraint.attrib:
            del constraint.attrib["score"]
        if "node" in constraint.attrib:
            del constraint.attrib["node"]

        utils.replace_cib_configuration(cib)

    elif command == "rm":
        temp_id = argv.pop(0)
        constraints = cib.find('.//constraints')
        loc_cons = cib.findall('.//rsc_location')

        rules = cib.findall('.//rule')
        for loc_con in loc_cons:
            for rule in loc_con:
                if rule.get("id") == temp_id:
                    if len(loc_con) > 1:
                        print "Removing Rule:",rule.get("id")
                        loc_con.remove(rule)
                        found = True
                        break
                    else:
                        print "Removing Constraint:",loc_con.get("id") 
                        constraints.remove(loc_con)
                        found = True
                        break

            if found == True:
                break

        if found:
            utils.replace_cib_configuration(cib)
        else:
            utils.err("unable to find rule with id: %s" % temp_id)
    else:
        usage.constraint("rule")
        sys.exit(1)
