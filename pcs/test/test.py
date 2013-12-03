import xml.etree.ElementTree as ET


tree = ET.parse('temp.xml')
root = tree.getroot()
print type(tree)
print type(root)

if type(tree) == ET.ElementTree:
  print "ELEMENT"
else:
  print "FAIL"

check_id = "D4"
print root.find(".//primitive[id=D1]")
print root.find(".//primitive[@id='"+check_id+"']")

#for z in root.findall(".//*"):
#  print z

#for a in root.findall('*'):
#  print a

