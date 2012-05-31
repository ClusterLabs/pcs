import sys
import usage
import utils
import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parseString

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

        if (sub_cmd2 == "force"):
            location_force(argv)
        elif (sub_cmd2 == "forcerm"):
            location_force(argv,True)
        elif (sub_cmd2 == "add"):
            location_add(argv)
        elif (sub_cmd2 == "rm"):
            location_add(argv,True)
        elif (sub_cmd2 == "show"):
            location_show(argv)
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
            order_show()
        else:
            usage.constraint()
            sys.exit(1)
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
            colocation_show()
        else:
            usage.constraint()
            sys.exit(1)

    elif (sub_cmd == "show" or sub_cmd == "list"):
        location_show([])
        order_show()
        colocation_show()
    else:
        print sub_cmd
        usage.constraint()
        sys.exit(1)

def colocation_show():
    (dom,constraintsElement) = getCurrentConstraints()

    print "Colocation Constraints:"
    for co_loc in constraintsElement.getElementsByTagName('rsc_colocation'):
        co_resource1 = co_loc.getAttribute("rsc")
        co_resource2 = co_loc.getAttribute("with-rsc")
        co_id = co_loc.getAttribute("id")
        co_score = co_loc.getAttribute("score")
        score_text = "" if (co_score == "INFINITY") else " (" + co_score + ")"
        print "  " + co_resource1 + " with " + co_resource2 + score_text

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


def colocation_add(argv):
    if len(argv) < 2:
        usage.constraint()
        sys.exit(1)

    resource1 = argv.pop(0)
    resource2 = argv.pop(0)
    score = "INFINITY" if (len(argv) == 0) else argv.pop(0)
    cl_id = "colocation-" + resource1 + "-" + resource2 + "-" + score

    (dom,constraintsElement) = getCurrentConstraints()
    element = dom.createElement("rsc_colocation")
    element.setAttribute("id",cl_id)
    element.setAttribute("rsc",resource1)
    element.setAttribute("with-rsc",resource2)
    element.setAttribute("score",score)
    constraintsElement.appendChild(element)
    xml_constraint_string = constraintsElement.toxml()
    args = ["cibadmin", "-c", "-R", "--xml-text", xml_constraint_string]
    output,retval = utils.run(args)
    if output != "":
        print output



def order_show():
    (dom,constraintsElement) = getCurrentConstraints()

    print "Ordering Constraints:"
    for ord_loc in constraintsElement.getElementsByTagName('rsc_order'):
        oc_resource1 = ord_loc.getAttribute("first")
        oc_resource2 = ord_loc.getAttribute("then")
        oc_id = ord_loc.getAttribute("id")
        oc_score = ord_loc.getAttribute("score")
        oc_sym = ""
        if ord_loc.getAttribute("symmetrical") == "false":
            oc_sym = " (non-symmetrical)"
        score_text = "" if (oc_score == "INFINITY") else " (" + oc_score + ")"
        print "  " + oc_resource1 + " then " + oc_resource2 + score_text + oc_sym

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



def order_add(argv,returnElementOnly=False):
    if len(argv) != 3 and len(argv) != 4:
        usage.constraint()
        sys.exit(1)

    resource1 = argv.pop(0)
    resource2 = argv.pop(0)
    score = argv.pop(0)
    sym = "true" if (len(argv) == 0 or argv.pop(0) != "nonsymmetrical") else "false"
    order_id = "order-" + resource1 + "-" + resource2 + "-" + score

    print "Adding " + resource1 + " " + resource2 + " score: " + score + " Symmetrical: "+sym

    (dom,constraintsElement) = getCurrentConstraints()
    element = dom.createElement("rsc_order")
    element.setAttribute("id",order_id)
    element.setAttribute("first",resource1)
    element.setAttribute("then",resource2)
    element.setAttribute("score",score)
    if (sym == "false"):
        element.setAttribute("symmetrical", "false")
    constraintsElement.appendChild(element)

    if returnElementOnly == False:
        xml_constraint_string = constraintsElement.toxml()
        args = ["cibadmin", "-c", "-R", "--xml-text", xml_constraint_string]
        output,retval = utils.run(args)
        if output != "":
            print output
    else:
        return element.toxml()

def location_force(argv, remove=False):
    if len(argv) != 2 and len(argv) != 3:
        usage.constraint()
        sys.exit(1)

    on = True

    rsc = argv[0]
    if len(argv) == 2:
        node = argv[1]
    else:
        if (argv[1] != "on") and (argv[1] != "off"):
            usage.constraint()
            sys.exit(1)
        if (argv[1] == "off"):
            on = False
        node = argv[2]

    loc_id = "loc_" + node + "_" + rsc
    if (on == True):
        location_add([loc_id,rsc,node,"INFINITY"],remove)
    else:
        location_add([loc_id,rsc,node,"-INFINITY"],remove)


# Show the currently configured location constraints by node or resource
def location_show(argv):
    if (len(argv) != 0 and argv[0] == "nodes"):
        byNode = True
    else:
        byNode = False

    if len(argv) > 1:
        valid_noderes = argv[1:]
    else:
        valid_noderes = []

    (dom,constraintsElement) = getCurrentConstraints()
    nodehashon = {}
    nodehashoff = {}
    rschashon = {}
    rschashoff = {}

    print "Location Constraints:"
    for rsc_loc in constraintsElement.getElementsByTagName('rsc_location'):
        lc_node = rsc_loc.getAttribute("node")
        lc_rsc = rsc_loc.getAttribute("rsc")
        lc_id = rsc_loc.getAttribute("id")
        lc_score = rsc_loc.getAttribute("score")

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
                print "    Enabled on:",
                for options in rschashon[rsc]:
                    print options[1],
                    if options[2] != "INFINITY":
                        print "("+options[2]+") ",
                print ""
            if (rsc in rschashoff):
                print "    Disabled on:",
                for options in rschashoff[rsc]:
                    print options[1],
                    if options[2] != "-INFINITY":
                        print "("+options[2]+") ",
                print ""


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

    # Verify current constraint doesn't already exist
    # If it does we replace it with the new constraint
    dom = parseString(current_constraints_xml)
    constraintsElement = dom.getElementsByTagName('constraints')[0]
    return (dom, constraintsElement)
