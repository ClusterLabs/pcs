ifndef $(PYTHON)
	PYTHON = python
endif

test:
	$(PYTHON) test_utils.py ${pyunit_flags}
	$(PYTHON) test_corosync_conf.py ${pyunit_flags}
	$(PYTHON) test_cluster.py ${pyunit_flags}
	$(PYTHON) test_resource.py ${pyunit_flags}
	$(PYTHON) test_rule.py ${pyunit_flags}
	$(PYTHON) test_constraints.py ${pyunit_flags}
	$(PYTHON) test_stonith.py ${pyunit_flags}
	$(PYTHON) test_properties.py ${pyunit_flags}
	$(PYTHON) test_acl.py ${pyunit_flags}
	$(PYTHON) test_node.py ${pyunit_flags}
	$(PYTHON) test_library_acl.py ${pyunit_flags}
	$(PYTHON) test_library_status_info.py ${pyunit_flags}
	$(PYTHON) test_library_pacemaker.py ${pyunit_flags}
