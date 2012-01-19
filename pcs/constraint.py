import sys
import usage
import utils
import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parseString

def constraint_cmd(argv):
    if len(argv) == 0:
        usage.constraint()
        sys.exit(1)

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
        print sub_cmd
        usage.constraint()
        sys.exit(1)


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
