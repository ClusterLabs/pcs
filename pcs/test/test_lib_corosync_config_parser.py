from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools import pcs_unittest as unittest

from pcs.test.tools.misc import ac

from pcs.lib.corosync import config_parser


class SectionTest(unittest.TestCase):

    def test_empty_section(self):
        section = config_parser.Section("mySection")
        self.assertEqual(section.parent, None)
        self.assertEqual(section.get_root(), section)
        self.assertEqual(section.name, "mySection")
        self.assertEqual(section.get_attributes(), [])
        self.assertEqual(section.get_sections(), [])
        self.assertTrue(section.empty)
        ac(str(section), "")

    def test_is_section_empty(self):
        section = config_parser.Section("mySection")
        self.assertTrue(section.empty)

        section = config_parser.Section("mySection")
        section.add_attribute("name", "value")
        self.assertFalse(section.empty)

        section = config_parser.Section("mySection")
        section.add_section(config_parser.Section("subSection"))
        self.assertFalse(section.empty)

        section = config_parser.Section("mySection")
        section.add_attribute("name", "value")
        section.add_section(config_parser.Section("subSection"))
        self.assertFalse(section.empty)

    def test_attribute_add(self):
        section = config_parser.Section("mySection")

        section.add_attribute("name1", "value1")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
            ]
        )

        section.add_attribute("name2", "value2")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name2", "value2"],
            ]
        )

        section.add_attribute("name2", "value2")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name2", "value2"],
                ["name2", "value2"],
            ]
        )

    def test_attribute_get(self):
        section = config_parser.Section("mySection")
        section.add_attribute("name1", "value1")
        section.add_attribute("name2", "value2")
        section.add_attribute("name3", "value3")
        section.add_attribute("name2", "value2a")

        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name2", "value2"],
                ["name3", "value3"],
                ["name2", "value2a"],
            ]
        )
        self.assertEqual(
            section.get_attributes("name1"),
            [
                ["name1", "value1"],
            ]
        )
        self.assertEqual(
            section.get_attributes("name2"),
            [
                ["name2", "value2"],
                ["name2", "value2a"],
            ]
        )
        self.assertEqual(
            section.get_attributes("nameX"),
            []
        )

    def test_attribute_set(self):
        section = config_parser.Section("mySection")

        section.set_attribute("name1", "value1")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
            ]
        )

        section.set_attribute("name1", "value1")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
            ]
        )

        section.set_attribute("name1", "value1a")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1a"],
            ]
        )

        section.set_attribute("name2", "value2")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1a"],
                ["name2", "value2"],
            ]
        )

        section.set_attribute("name1", "value1")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name2", "value2"],
            ]
        )

        section.add_attribute("name3", "value3")
        section.add_attribute("name2", "value2")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name2", "value2"],
                ["name3", "value3"],
                ["name2", "value2"],
            ]
        )
        section.set_attribute("name2", "value2a")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name2", "value2a"],
                ["name3", "value3"],
            ]
        )

        section.add_attribute("name1", "value1")
        section.add_attribute("name1", "value1")
        section.set_attribute("name1", "value1")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name2", "value2a"],
                ["name3", "value3"],
            ]
        )

    def test_attribute_change(self):
        section = config_parser.Section("mySection")
        section.add_attribute("name1", "value1")
        section.add_attribute("name2", "value2")
        section.add_attribute("name3", "value3")
        section.add_attribute("name2", "value2")

        attr = section.get_attributes()[1]
        attr[0] = "name2a"
        attr[1] = "value2a"
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name2a", "value2a"],
                ["name3", "value3"],
                ["name2", "value2"],
            ]
        )

    def test_attribute_del(self):
        section = config_parser.Section("mySection")
        section.add_attribute("name1", "value1")
        section.add_attribute("name2", "value2")
        section.add_attribute("name3", "value3")
        section.add_attribute("name2", "value2")

        section.del_attribute(section.get_attributes()[1])
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name3", "value3"],
            ]
        )

        section.del_attribute(["name3", "value3"])
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
            ]
        )

        section.del_attribute(["name3", "value3"])
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
            ]
        )

    def test_attribute_del_by_name(self):
        section = config_parser.Section("mySection")
        section.add_attribute("name1", "value1")
        section.add_attribute("name2", "value2")
        section.add_attribute("name3", "value3")
        section.add_attribute("name2", "value2")

        section.del_attributes_by_name("nameX")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name2", "value2"],
                ["name3", "value3"],
                ["name2", "value2"],
            ]
        )

        section.del_attributes_by_name("name2", "value2")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name3", "value3"],
            ]
        )

        section.add_attribute("name2", "value2")
        section.add_attribute("name2", "value2a")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name3", "value3"],
                ["name2", "value2"],
                ["name2", "value2a"],
            ]
        )
        section.del_attributes_by_name("name2", "value2")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name3", "value3"],
                ["name2", "value2a"],
            ]
        )

        section.add_attribute("name3", "value3a")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name3", "value3"],
                ["name2", "value2a"],
                ["name3", "value3a"],
            ]
        )
        section.del_attributes_by_name("name3")
        self.assertEqual(
            section.get_attributes(),
            [
                ["name1", "value1"],
                ["name2", "value2a"],
            ]
        )

    def test_section_add(self):
        root = config_parser.Section("root")
        child1 = config_parser.Section("child1")
        child1a = config_parser.Section("child1a")
        child2 = config_parser.Section("child2")

        root.add_section(child1)
        child1.add_section(child1a)
        root.add_section(child2)
        self.assertEqual(root.parent, None)
        self.assertEqual(child1.parent.name, "root")
        self.assertEqual(child1a.parent.name, "child1")
        self.assertEqual(child2.parent.name, "root")
        ac(str(root), """\
child1 {
    child1a {
    }
}

child2 {
}
""")

        child2.add_section(child1a)
        self.assertEqual(child1a.parent.name, "child2")
        ac(str(root), """\
child1 {
}

child2 {
    child1a {
    }
}
""")

        self.assertRaises(
            config_parser.CircularParentshipException,
            child1a.add_section, child1a
        )
        self.assertRaises(
            config_parser.CircularParentshipException,
            child1a.add_section, child2
        )
        self.assertRaises(
            config_parser.CircularParentshipException,
            child1a.add_section, root
        )

    def test_section_get(self):
        root = config_parser.Section("")
        child1 = config_parser.Section("child1")
        child2 = config_parser.Section("child2")
        childa1 = config_parser.Section("childA")
        childa2 = config_parser.Section("childA")
        childa3 = config_parser.Section("childA")
        childa4 = config_parser.Section("childA")
        childb1 = config_parser.Section("childB")
        childb2 = config_parser.Section("childB")
        childa1.add_attribute("id", "1")
        childa2.add_attribute("id", "2")
        childa3.add_attribute("id", "3")
        childa4.add_attribute("id", "4")
        childb1.add_attribute("id", "5")
        childb2.add_attribute("id", "6")
        root.add_section(child1)
        root.add_section(child2)
        child1.add_section(childa1)
        child1.add_section(childa2)
        child1.add_section(childb1)
        child2.add_section(childa3)
        child2.add_section(childb2)
        child2.add_section(childa4)
        ac(str(root), """\
child1 {
    childA {
        id: 1
    }

    childA {
        id: 2
    }

    childB {
        id: 5
    }
}

child2 {
    childA {
        id: 3
    }

    childB {
        id: 6
    }

    childA {
        id: 4
    }
}
""")

        ac(
            "---\n".join([str(x) for x in root.get_sections()]),
            """\
child1 {
    childA {
        id: 1
    }

    childA {
        id: 2
    }

    childB {
        id: 5
    }
}
---
child2 {
    childA {
        id: 3
    }

    childB {
        id: 6
    }

    childA {
        id: 4
    }
}
""")

        ac(
            "---\n".join([str(x) for x in root.get_sections("child1")]),
            """\
child1 {
    childA {
        id: 1
    }

    childA {
        id: 2
    }

    childB {
        id: 5
    }
}
""")

        ac(
            "---\n".join([str(x) for x in child1.get_sections("childA")]),
            """\
childA {
    id: 1
}
---
childA {
    id: 2
}
""")

        ac(
            "---\n".join([str(x) for x in child1.get_sections("child2")]),
            ""
        )

    def test_section_del(self):
        root = config_parser.Section("")
        child1 = config_parser.Section("child1")
        child2 = config_parser.Section("child2")
        childa1 = config_parser.Section("childA")
        childa2 = config_parser.Section("childA")
        childa3 = config_parser.Section("childA")
        childa4 = config_parser.Section("childA")
        childb1 = config_parser.Section("childB")
        childb2 = config_parser.Section("childB")
        childa1.add_attribute("id", "1")
        childa2.add_attribute("id", "2")
        childa3.add_attribute("id", "3")
        childa4.add_attribute("id", "4")
        childb1.add_attribute("id", "5")
        childb2.add_attribute("id", "6")
        root.add_section(child1)
        root.add_section(child2)
        child1.add_section(childa1)
        child1.add_section(childa2)
        child1.add_section(childb1)
        child2.add_section(childa3)
        child2.add_section(childb2)
        child2.add_section(childa4)
        ac(str(root), """\
child1 {
    childA {
        id: 1
    }

    childA {
        id: 2
    }

    childB {
        id: 5
    }
}

child2 {
    childA {
        id: 3
    }

    childB {
        id: 6
    }

    childA {
        id: 4
    }
}
""")

        child2.del_section(childb2)
        self.assertEqual(childb2.parent, None)
        ac(str(root), """\
child1 {
    childA {
        id: 1
    }

    childA {
        id: 2
    }

    childB {
        id: 5
    }
}

child2 {
    childA {
        id: 3
    }

    childA {
        id: 4
    }
}
""")

        root.del_section(child2)
        self.assertEqual(child2.parent, None)
        ac(str(root), """\
child1 {
    childA {
        id: 1
    }

    childA {
        id: 2
    }

    childB {
        id: 5
    }
}
""")

        self.assertRaises(ValueError, root.del_section, child2)

        self.assertEqual(childa1.parent.name, "child1")
        self.assertRaises(ValueError, child2.del_section, childa1)
        self.assertEqual(childa1.parent.name, "child1")

        child1.del_section(childb1)
        self.assertEqual(childb1.parent, None)
        ac(str(root), """\
child1 {
    childA {
        id: 1
    }

    childA {
        id: 2
    }
}
""")

        child1.del_section(childa1)
        self.assertEqual(childa1.parent, None)
        child1.del_section(childa2)
        self.assertEqual(childa2.parent, None)
        ac(str(root), """\
child1 {
}
""")

        root.del_section(child1)
        self.assertEqual(child1.parent, None)
        ac(str(root), "")

    def test_get_root(self):
        root = config_parser.Section("root")
        child1 = config_parser.Section("child1")
        child1a = config_parser.Section("child1a")
        root.add_section(child1)
        child1.add_section(child1a)

        self.assertEqual(root.get_root().name, "root")
        self.assertEqual(child1.get_root().name, "root")
        self.assertEqual(child1a.get_root().name, "root")

    def test_str(self):
        root = config_parser.Section("root")
        ac(str(root), "")

        root.add_attribute("name1", "value1")
        ac(str(root), "name1: value1\n")

        root.add_attribute("name2", "value2")
        root.add_attribute("name2", "value2a")
        root.add_attribute("name3", "value3")
        ac(str(root), """\
name1: value1
name2: value2
name2: value2a
name3: value3
""")

        child1 = config_parser.Section("child1")
        root.add_section(child1)
        ac(str(root), """\
name1: value1
name2: value2
name2: value2a
name3: value3

child1 {
}
""")

        child1.add_attribute("name1.1", "value1.1")
        child1.add_attribute("name1.2", "value1.2")
        ac(str(root), """\
name1: value1
name2: value2
name2: value2a
name3: value3

child1 {
    name1.1: value1.1
    name1.2: value1.2
}
""")

        child2 = config_parser.Section("child2")
        child2.add_attribute("name2.1", "value2.1")
        root.add_section(child2)
        ac(str(root), """\
name1: value1
name2: value2
name2: value2a
name3: value3

child1 {
    name1.1: value1.1
    name1.2: value1.2
}

child2 {
    name2.1: value2.1
}
""")

        child2a = config_parser.Section("child2a")
        child2a.add_attribute("name2.a.1", "value2.a.1")
        child2.add_section(child2a)
        ac(str(root), """\
name1: value1
name2: value2
name2: value2a
name3: value3

child1 {
    name1.1: value1.1
    name1.2: value1.2
}

child2 {
    name2.1: value2.1

    child2a {
        name2.a.1: value2.a.1
    }
}
""")

        child3 = config_parser.Section("child3")
        root.add_section(child3)
        child3.add_section(config_parser.Section("child3a"))
        child3.add_section(config_parser.Section("child3b"))
        ac(str(root), """\
name1: value1
name2: value2
name2: value2a
name3: value3

child1 {
    name1.1: value1.1
    name1.2: value1.2
}

child2 {
    name2.1: value2.1

    child2a {
        name2.a.1: value2.a.1
    }
}

child3 {
    child3a {
    }

    child3b {
    }
}
""")


class ParserTest(unittest.TestCase):

    def test_empty(self):
        ac(str(config_parser.parse_string("")), "")

    def test_attributes(self):
        string = """\
name:value\
"""
        parsed = """\
name: value
"""
        ac(str(config_parser.parse_string(string)), parsed)

        string = """\
name:value
name:value
"""
        parsed = """\
name: value
name: value
"""
        ac(str(config_parser.parse_string(string)), parsed)

        string = """\
  name1:value1  
name2  :value2
name3:  value3
  name4  :  value4  
"""
        parsed = """\
name1: value1
name2: value2
name3: value3
name4: value4
"""
        ac(str(config_parser.parse_string(string)), parsed)

        string = """\
name:foo:value
"""
        parsed = """\
name: foo:value
"""
        root = config_parser.parse_string(string)
        self.assertEqual(root.get_attributes(), [["name", "foo:value"]])
        ac(str(root), parsed)

        string = """\
name :  
"""
        parsed = """\
name: 
"""
        root = config_parser.parse_string(string)
        self.assertEqual(root.get_attributes(), [["name", ""]])
        ac(str(root), parsed)

    def test_section(self):
        string = """\
section1 {
}\
"""
        parsed = """\
section1 {
}
"""
        ac(str(config_parser.parse_string(string)), parsed)

        string = """\
section1 {
    section1a   {
  }
  section1b        {       
     }    
}
"""
        parsed = """\
section1 {
    section1a {
    }

    section1b {
    }
}
"""
        ac(str(config_parser.parse_string(string)), parsed)

        string = """\
section1 {
    section1a junk1 { junk2
    junk3 } junk4
    section1b junk5{junk6
    junk7}junk8
}
section2 {
   section2a {
   }
   section2b {
   }
}
"""
        parsed = """\
section1 {
    section1a junk1 {
    }

    section1b junk5 {
    }
}

section2 {
    section2a {
    }

    section2b {
    }
}
"""
        ac(str(config_parser.parse_string(string)), parsed)

        string = """\
section1 {
    section1a {
    }

    section1b {
    }
}
}
"""
        self.assertRaises(
            config_parser.UnexpectedClosingBraceException,
            config_parser.parse_string, string
        )

        string = """\
section1 {
    section1a {

    section1b {
    }
}
"""
        self.assertRaises(
            config_parser.MissingClosingBraceException,
            config_parser.parse_string, string
        )

        string = """\
section1 {
"""
        self.assertRaises(
            config_parser.MissingClosingBraceException,
            config_parser.parse_string, string
        )

        string = """\
}
"""
        self.assertRaises(
            config_parser.UnexpectedClosingBraceException,
            config_parser.parse_string, string
        )


    def test_comment(self):
        string= """\
# junk1
name1: value1
  #junk2
name2: value2#junk3
name3: value3 #junk4
name4 # junk5: value4
#junk6 name5: value5
#junk7
"""
        parsed = """\
name1: value1
name2: value2#junk3
name3: value3 #junk4
name4 # junk5: value4
"""
        ac(str(config_parser.parse_string(string)), parsed)

        string= """\
# junk1
section1 { # junk2
}
section2 # junk2 {
}
section3 {
} #junk3
"""
        parsed = """\
section1 {
}

section2 # junk2 {
}

section3 {
}
"""
        ac(str(config_parser.parse_string(string)), parsed)

        string = """\
section {
#}
"""
        self.assertRaises(
            config_parser.MissingClosingBraceException,
            config_parser.parse_string, string
        )

        string = """\
#section {
}
"""
        self.assertRaises(
            config_parser.UnexpectedClosingBraceException,
            config_parser.parse_string, string
        )

    def test_full(self):
        string = """\
# Please read the corosync.conf.5 manual page
totem {
	version: 2

	# crypto_cipher and crypto_hash: Used for mutual node authentication.
	# If you choose to enable this, then do remember to create a shared
	# secret with "corosync-keygen".
	# enabling crypto_cipher, requires also enabling of crypto_hash.
	crypto_cipher: none
	crypto_hash: none

	# interface: define at least one interface to communicate
	# over. If you define more than one interface stanza, you must
	# also set rrp_mode.
	interface {
                # Rings must be consecutively numbered, starting at 0.
		ringnumber: 0
		# This is normally the *network* address of the
		# interface to bind to. This ensures that you can use
		# identical instances of this configuration file
		# across all your cluster nodes, without having to
		# modify this option.
		bindnetaddr: 192.168.1.0
		# However, if you have multiple physical network
		# interfaces configured for the same subnet, then the
		# network address alone is not sufficient to identify
		# the interface Corosync should bind to. In that case,
		# configure the *host* address of the interface
		# instead:
		# bindnetaddr: 192.168.1.1
		# When selecting a multicast address, consider RFC
		# 2365 (which, among other things, specifies that
		# 239.255.x.x addresses are left to the discretion of
		# the network administrator). Do not reuse multicast
		# addresses across multiple Corosync clusters sharing
		# the same network.
		mcastaddr: 239.255.1.1
		# Corosync uses the port you specify here for UDP
		# messaging, and also the immediately preceding
		# port. Thus if you set this to 5405, Corosync sends
		# messages over UDP ports 5405 and 5404.
		mcastport: 5405
		# Time-to-live for cluster communication packets. The
		# number of hops (routers) that this ring will allow
		# itself to pass. Note that multicast routing must be
		# specifically enabled on most network routers.
		ttl: 1
	}
}

logging {
	# Log the source file and line where messages are being
	# generated. When in doubt, leave off. Potentially useful for
	# debugging.
	fileline: off
	# Log to standard error. When in doubt, set to no. Useful when
	# running in the foreground (when invoking "corosync -f")
	to_stderr: no
	# Log to a log file. When set to "no", the "logfile" option
	# must not be set.
	to_logfile: yes
	logfile: /var/log/cluster/corosync.log
	# Log to the system log daemon. When in doubt, set to yes.
	to_syslog: yes
	# Log debug messages (very verbose). When in doubt, leave off.
	debug: off
	# Log messages with time stamps. When in doubt, set to on
	# (unless you are only logging to syslog, where double
	# timestamps can be annoying).
	timestamp: on
	logger_subsys {
		subsys: QUORUM
		debug: off
	}
}

quorum {
	# Enable and configure quorum subsystem (default: off)
	# see also corosync.conf.5 and votequorum.5
	#provider: corosync_votequorum
}
"""
        parsed = """\
totem {
    version: 2
    crypto_cipher: none
    crypto_hash: none

    interface {
        ringnumber: 0
        bindnetaddr: 192.168.1.0
        mcastaddr: 239.255.1.1
        mcastport: 5405
        ttl: 1
    }
}

logging {
    fileline: off
    to_stderr: no
    to_logfile: yes
    logfile: /var/log/cluster/corosync.log
    to_syslog: yes
    debug: off
    timestamp: on

    logger_subsys {
        subsys: QUORUM
        debug: off
    }
}

quorum {
}
"""
        ac(str(config_parser.parse_string(string)), parsed)

        string = """\
# Please read the corosync.conf.5 manual page
totem {
	version: 2

	crypto_cipher: none
	crypto_hash: none

	interface {
		ringnumber: 0
		bindnetaddr: 10.16.35.0
		mcastport: 5405
		ttl: 1
	}
	transport: udpu
}

logging {
	fileline: off
	to_logfile: yes
	to_syslog: yes
	logfile: /var/log/cluster/corosync.log
	debug: off
	timestamp: on
	logger_subsys {
		subsys: QUORUM
		debug: off
	}
}

nodelist {
	node {
		ring0_addr: 10.16.35.101
		nodeid: 1
	}

	node {
		ring0_addr: 10.16.35.102
		nodeid: 2
	}

	node {
		ring0_addr: 10.16.35.103
	}

	node {
		ring0_addr: 10.16.35.104
	}

	node {
		ring0_addr: 10.16.35.105
	}
}

quorum {
	# Enable and configure quorum subsystem (default: off)
	# see also corosync.conf.5 and votequorum.5
	#provider: corosync_votequorum
}
"""
        parsed = """\
totem {
    version: 2
    crypto_cipher: none
    crypto_hash: none
    transport: udpu

    interface {
        ringnumber: 0
        bindnetaddr: 10.16.35.0
        mcastport: 5405
        ttl: 1
    }
}

logging {
    fileline: off
    to_logfile: yes
    to_syslog: yes
    logfile: /var/log/cluster/corosync.log
    debug: off
    timestamp: on

    logger_subsys {
        subsys: QUORUM
        debug: off
    }
}

nodelist {
    node {
        ring0_addr: 10.16.35.101
        nodeid: 1
    }

    node {
        ring0_addr: 10.16.35.102
        nodeid: 2
    }

    node {
        ring0_addr: 10.16.35.103
    }

    node {
        ring0_addr: 10.16.35.104
    }

    node {
        ring0_addr: 10.16.35.105
    }
}

quorum {
}
"""
        ac(str(config_parser.parse_string(string)), parsed)
