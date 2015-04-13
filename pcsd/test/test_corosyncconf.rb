require 'test/unit'

require 'pcsd_test_utils.rb'
require 'corosyncconf.rb'

class TestCorosyncConfSection < Test::Unit::TestCase
  def test_empty_section
    section = CorosyncConf::Section.new('mySection')
    assert_nil(section.parent)
    assert_equal(section, section.root)
    assert_equal('mySection', section.name)
    assert_equal([], section.attributes)
    assert_equal([], section.sections)
    assert_equal('', section.text)
  end

  def test_attribute_add
    section = CorosyncConf::Section.new('mySection')

    section.add_attribute('name1', 'value1')
    assert_equal(
      [
        ['name1', 'value1'],
      ],
      section.attributes
    )

    section.add_attribute('name2', 'value2')
    assert_equal(
      [
        ['name1', 'value1'],
        ['name2', 'value2'],
      ],
      section.attributes
    )

    section.add_attribute('name2', 'value2')
    assert_equal(
      [
        ['name1', 'value1'],
        ['name2', 'value2'],
        ['name2', 'value2'],
      ],
      section.attributes
    )
  end

  def test_attribute_get
    section = CorosyncConf::Section.new('mySection')
    section.add_attribute('name1', 'value1')
    section.add_attribute('name2', 'value2')
    section.add_attribute('name3', 'value3')
    section.add_attribute('name2', 'value2a')

    assert_equal(
      [
        ['name1', 'value1'],
        ['name2', 'value2'],
        ['name3', 'value3'],
        ['name2', 'value2a'],
      ],
      section.attributes
    )
    assert_equal(
      [
        ['name1', 'value1'],
      ],
      section.attributes('name1')
    )
    assert_equal(
      [
        ['name2', 'value2'],
        ['name2', 'value2a'],
      ],
      section.attributes('name2')
    )
    assert_equal(
      [],
      section.attributes('nameX')
    )
  end

  def test_attribute_set
    section = CorosyncConf::Section.new('mySection')

    section.set_attribute('name1', 'value1')
    assert_equal(
      [
        ['name1', 'value1'],
      ],
      section.attributes
    )

    section.set_attribute('name1', 'value1')
    assert_equal(
      [
        ['name1', 'value1'],
      ],
      section.attributes
    )

    section.set_attribute('name1', 'value1a')
    assert_equal(
      [
        ['name1', 'value1a'],
      ],
      section.attributes
    )

    section.set_attribute('name2', 'value2')
    assert_equal(
      [
        ['name1', 'value1a'],
        ['name2', 'value2'],
      ],
      section.attributes
    )

    section.set_attribute('name1', 'value1')
    assert_equal(
      [
        ['name1', 'value1'],
        ['name2', 'value2'],
      ],
      section.attributes
    )

    section.add_attribute('name3', 'value3')
    section.add_attribute('name2', 'value2')
    assert_equal(
      [
        ['name1', 'value1'],
        ['name2', 'value2'],
        ['name3', 'value3'],
        ['name2', 'value2'],
      ],
      section.attributes
    )
    section.set_attribute('name2', 'value2a')
    assert_equal(
      [
        ['name1', 'value1'],
        ['name2', 'value2a'],
        ['name3', 'value3'],
      ],
      section.attributes
    )

    section.add_attribute('name1', 'value1')
    section.add_attribute('name1', 'value1')
    section.set_attribute('name1', 'value1')
    assert_equal(
      [
        ['name1', 'value1'],
        ['name2', 'value2a'],
        ['name3', 'value3'],
      ],
      section.attributes
    )
  end

  def test_attribute_change
    section = CorosyncConf::Section.new('mySection')
    section.add_attribute('name1', 'value1')
    section.add_attribute('name2', 'value2')
    section.add_attribute('name3', 'value3')
    section.add_attribute('name2', 'value2')

    attrib = section.attributes[1]
    attrib[0] = 'name2a'
    attrib[1] = 'value2a'
    assert_equal(
      [
        ['name1', 'value1'],
        ['name2a', 'value2a'],
        ['name3', 'value3'],
        ['name2', 'value2'],
      ],
      section.attributes
    )
  end

  def test_attribute_del
    section = CorosyncConf::Section.new('mySection')
    section.add_attribute('name1', 'value1')
    section.add_attribute('name2', 'value2')
    section.add_attribute('name3', 'value3')
    section.add_attribute('name2', 'value2')

    section.del_attribute(section.attributes[1])
    assert_equal(
      [
        ['name1', 'value1'],
        ['name3', 'value3'],
      ],
      section.attributes
    )

    section.del_attribute(['name3', 'value3'])
    assert_equal(
      [
        ['name1', 'value1'],
      ],
      section.attributes
    )

    section.del_attribute(['name3', 'value3'])
    assert_equal(
      [
        ['name1', 'value1'],
      ],
      section.attributes
    )
  end

  def test_attribute_del_by_name
    section = CorosyncConf::Section.new('mySection')
    section.add_attribute('name1', 'value1')
    section.add_attribute('name2', 'value2')
    section.add_attribute('name3', 'value3')
    section.add_attribute('name2', 'value2')

    section.del_attributes_by_name('nameX')
    assert_equal(
      [
        ['name1', 'value1'],
        ['name2', 'value2'],
        ['name3', 'value3'],
        ['name2', 'value2'],
      ],
      section.attributes
    )

    section.del_attributes_by_name('name2', 'value2')
    assert_equal(
      [
        ['name1', 'value1'],
        ['name3', 'value3'],
      ],
      section.attributes
    )

    section.add_attribute('name2', 'value2')
    section.add_attribute('name2', 'value2a')
    assert_equal(
      [
        ['name1', 'value1'],
        ['name3', 'value3'],
        ['name2', 'value2'],
        ['name2', 'value2a'],
      ],
      section.attributes
    )
    section.del_attributes_by_name('name2', 'value2')
    assert_equal(
      [
        ['name1', 'value1'],
        ['name3', 'value3'],
        ['name2', 'value2a'],
      ],
      section.attributes
    )

    section.add_attribute('name3', 'value3a')
    assert_equal(
      [
        ['name1', 'value1'],
        ['name3', 'value3'],
        ['name2', 'value2a'],
        ['name3', 'value3a'],
      ],
      section.attributes
    )
    section.del_attributes_by_name('name3')
    assert_equal(
      [
        ['name1', 'value1'],
        ['name2', 'value2a'],
      ],
      section.attributes
    )
  end

  def test_section_add
    root = CorosyncConf::Section.new('root')
    child1 = CorosyncConf::Section.new('child1')
    child1a = CorosyncConf::Section.new('child1a')
    child2 = CorosyncConf::Section.new('child2')

    root.add_section(child1)
    child1.add_section(child1a)
    root.add_section(child2)
    assert_nil(root.parent)
    assert_equal('root', child1.parent.name)
    assert_equal('child1', child1a.parent.name)
    assert_equal('root', child2.parent.name)
    assert_equal("\
child1 {
    child1a {
    }
}

child2 {
}
",
      root.text
    )

    child2.add_section(child1a)
    assert_equal('child2', child1a.parent.name)
    assert_equal("\
child1 {
}

child2 {
    child1a {
    }
}
",
      root.text
    )

    assert_raise CorosyncConf::CircularParentshipException do
      child1a.add_section(child1a)
    end
    assert_raise CorosyncConf::CircularParentshipException do
      child1a.add_section(child2)
    end
    assert_raise CorosyncConf::CircularParentshipException do
      child1a.add_section(root)
    end
  end

  def test_section_get
    root = CorosyncConf::Section.new('root')
    child1 = CorosyncConf::Section.new('child1')
    child2 = CorosyncConf::Section.new('child2')
    childa1 = CorosyncConf::Section.new('childA')
    childa2 = CorosyncConf::Section.new('childA')
    childa3 = CorosyncConf::Section.new('childA')
    childa4 = CorosyncConf::Section.new('childA')
    childb1 = CorosyncConf::Section.new('childB')
    childb2 = CorosyncConf::Section.new('childB')
    childa1.add_attribute('id', '1')
    childa2.add_attribute('id', '2')
    childa3.add_attribute('id', '3')
    childa4.add_attribute('id', '4')
    childb1.add_attribute('id', '5')
    childb2.add_attribute('id', '6')
    root.add_section(child1)
    root.add_section(child2)
    child1.add_section(childa1)
    child1.add_section(childa2)
    child1.add_section(childb1)
    child2.add_section(childa3)
    child2.add_section(childb2)
    child2.add_section(childa4)
    assert_equal("\
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
",
      root.text
    )

    assert_equal("\
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
",
      root.sections.collect { |section| section.text }.join("---\n")
    )

    assert_equal("\
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
",
      root.sections('child1').collect { |section| section.text }.join("---\n")
    )

    assert_equal("\
childA {
    id: 1
}
---
childA {
    id: 2
}
",
      child1.sections('childA').collect { |section| section.text }.join("---\n")
    )

    assert_equal(
      '',
      child1.sections('child2').collect { |section| section.text }.join("---\n")
    )
  end

  def test_section_del
    root = CorosyncConf::Section.new('')
    child1 = CorosyncConf::Section.new('child1')
    child2 = CorosyncConf::Section.new('child2')
    childa1 = CorosyncConf::Section.new('childA')
    childa2 = CorosyncConf::Section.new('childA')
    childa3 = CorosyncConf::Section.new('childA')
    childa4 = CorosyncConf::Section.new('childA')
    childb1 = CorosyncConf::Section.new('childB')
    childb2 = CorosyncConf::Section.new('childB')
    childa1.add_attribute('id', '1')
    childa2.add_attribute('id', '2')
    childa3.add_attribute('id', '3')
    childa4.add_attribute('id', '4')
    childb1.add_attribute('id', '5')
    childb2.add_attribute('id', '6')
    root.add_section(child1)
    root.add_section(child2)
    child1.add_section(childa1)
    child1.add_section(childa2)
    child1.add_section(childb1)
    child2.add_section(childa3)
    child2.add_section(childb2)
    child2.add_section(childa4)
    assert_equal("\
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
",
      root.text
    )

    child2.del_section(childb2)
    assert_nil(childb2.parent)
    assert_equal("\
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
",
      root.text
    )

    root.del_section(child2)
    assert_nil(child2.parent)
    assert_equal("\
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
",
      root.text
    )

    root.del_section(child2)

    assert_equal('child1', childa1.parent.name)
    child2.del_section(childa1)
    assert_equal('child1', childa1.parent.name)

    child1.del_section(childb1)
    assert_nil(childb1.parent)
    assert_equal("\
child1 {
    childA {
        id: 1
    }

    childA {
        id: 2
    }
}
",
      root.text
    )

    child1.del_section(childa1)
    assert_nil(childa1.parent)
    child1.del_section(childa2)
    assert_nil(childa2.parent)
    assert_equal("\
child1 {
}
",
      root.text
    )

    root.del_section(child1)
    assert_nil(child1.parent)
    assert_equal('', root.text)
  end

  def test_get_root
    root = CorosyncConf::Section.new('root')
    child1 = CorosyncConf::Section.new('child1')
    child1a = CorosyncConf::Section.new('child1a')
    root.add_section(child1)
    child1.add_section(child1a)

    assert_equal('root', root.root.name)
    assert_equal('root', child1.root.name)
    assert_equal('root', child1a.root.name)
  end

  def test_text
    root = CorosyncConf::Section.new('root')
    assert_equal('', root.text)

    root.add_attribute("name1", "value1")
    assert_equal("name1: value1\n", root.text)

    root.add_attribute("name2", "value2")
    root.add_attribute("name2", "value2a")
    root.add_attribute("name3", "value3")
    assert_equal("\
name1: value1
name2: value2
name2: value2a
name3: value3
",
      root.text
    )

    child1 = CorosyncConf::Section.new('child1')
    root.add_section(child1)
    assert_equal("\
name1: value1
name2: value2
name2: value2a
name3: value3

child1 {
}
",
      root.text
    )

    child1.add_attribute("name1.1", "value1.1")
    child1.add_attribute("name1.2", "value1.2")
    assert_equal("\
name1: value1
name2: value2
name2: value2a
name3: value3

child1 {
    name1.1: value1.1
    name1.2: value1.2
}
",
      root.text
    )

    child2 = CorosyncConf::Section.new('child2')
    child2.add_attribute("name2.1", "value2.1")
    root.add_section(child2)
    assert_equal("\
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
",
      root.text
    )

    child2a = CorosyncConf::Section.new('child2a')
    child2a.add_attribute("name2.a.1", "value2.a.1")
    child2.add_section(child2a)
    assert_equal("\
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
",
      root.text
    )

    child3 = CorosyncConf::Section.new('child3')
    root.add_section(child3)
    child3.add_section(CorosyncConf::Section.new('child3a'))
    child3.add_section(CorosyncConf::Section.new('child3b'))
    assert_equal("\
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
",
      root.text
    )
  end
end

class TestCorosyncConfParser < Test::Unit::TestCase
  def test_empty
    assert_equal('', CorosyncConf::parse_string('').text)
  end

  def test_attributes
    string = "\
name:value\
"
    parsed = "\
name: value
"
    assert_equal(parsed, CorosyncConf::parse_string(string).text)

    string = "\
name:value
name:value
"
    parsed = "\
name: value
name: value
"
    assert_equal(parsed, CorosyncConf::parse_string(string).text)

    string = "\
  name1:value1  
name2  :value2
name3:  value3
  name4  :  value4  
"
    parsed = "\
name1: value1
name2: value2
name3: value3
name4: value4
"
    assert_equal(parsed, CorosyncConf::parse_string(string).text)

    string = "\
name:foo:value
"
    parsed = "\
name: foo:value
"
    root = CorosyncConf::parse_string(string)
    assert_equal(
      [['name', 'foo:value']],
      root.attributes
    )
    assert_equal(parsed, root.text)

    string = "\
name :  
"
    parsed = "\
name: 
"
    root = CorosyncConf::parse_string(string)
    assert_equal(
      [['name', '']],
      root.attributes
    )
    assert_equal(parsed, root.text)
  end

  def test_section
    string = "\
section1 {
}\
"
    parsed = "\
section1 {
}
"
    assert_equal(parsed, CorosyncConf::parse_string(string).text)

    string = "\
section1 {
    section1a   {
  }
  section1b        {       
     }    
}
"
    parsed = "\
section1 {
    section1a {
    }

    section1b {
    }
}
"
    assert_equal(parsed, CorosyncConf::parse_string(string).text)

    string = "\
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
"
    parsed = "\
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
"
    assert_equal(parsed, CorosyncConf::parse_string(string).text)

    string = "\
section1 {
    section1a {
    }

    section1b {
    }
}
}
"
    assert_raise CorosyncConf::ParseErrorException do
      CorosyncConf::parse_string(string)
    end

    string = "\
section1 {
    section1a {

    section1b {
    }
}
"
    assert_raise CorosyncConf::ParseErrorException do
      CorosyncConf::parse_string(string)
    end

    string = "\
section1 {
"
    assert_raise CorosyncConf::ParseErrorException do
      CorosyncConf::parse_string(string)
    end

    string = "\
}
"
    assert_raise CorosyncConf::ParseErrorException do
      CorosyncConf::parse_string(string)
    end
  end

  def test_comment
    string= "\
# junk1
name1: value1
  #junk2
name2: value2#junk3
name3: value3 #junk4
name4 # junk5: value4
#junk6 name5: value5
#junk7
"
    parsed = "\
name1: value1
name2: value2#junk3
name3: value3 #junk4
name4 # junk5: value4
"
    assert_equal(parsed, CorosyncConf::parse_string(string).text)

    string= "\
# junk1
section1 { # junk2
}
section2 # junk2 {
}
section3 {
} #junk3
"
    parsed = "\
section1 {
}

section2 # junk2 {
}

section3 {
}
"
    assert_equal(parsed, CorosyncConf::parse_string(string).text)

    string = "\
section {
#}
"
    assert_raise CorosyncConf::ParseErrorException do
      CorosyncConf::parse_string(string)
    end

    string = "\
#section {
}
"""
    assert_raise CorosyncConf::ParseErrorException do
      CorosyncConf::parse_string(string)
    end
  end

  def test_full
    string = "\
# Please read the corosync.conf.5 manual page
totem {
	version: 2

	# crypto_cipher and crypto_hash: Used for mutual node authentication.
	# If you choose to enable this, then do remember to create a shared
	# secret with 'corosync-keygen'.
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
	# running in the foreground (when invoking 'corosync -f')
	to_stderr: no
	# Log to a log file. When set to 'no', the 'logfile' option
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
"
    parsed = "\
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
"
    assert_equal(parsed, CorosyncConf::parse_string(string).text)

    string = "\
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
"
    parsed = "\
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
"
    assert_equal(parsed, CorosyncConf::parse_string(string).text)
  end
end
