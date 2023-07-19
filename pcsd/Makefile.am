EXTRA_DIST		= \
			  pam/pcsd.debian \
			  pam/pcsd.fedora \
			  pam/pcsd.opencloudos \
			  test/cib1.xml \
			  test/corosync.conf \
			  test/crm1.xml \
			  test/crm2.xml \
			  test/crm2_new_roles.xml \
			  test/known-hosts \
			  test/pcsd_test_utils.rb \
			  test/pcs_settings.conf \
			  test/test_all_suite.rb \
			  test/test_cfgsync.rb \
			  test/test_cluster_entity.rb \
			  test/test_cluster.rb \
			  test/test_config.rb \
			  test/test_corosyncconf.rb \
			  test/test_pcs.rb \
			  test/test_permissions.rb \
			  test/test_resource.rb

MAINTAINERCLEANFILES	= Makefile.in

# install
man8_MANS		= pcsd.8

defconfigdir		= $(CONF_DIR)
dist_defconfig_DATA	= conf/pcsd

logrotatedir		= $(sysconfdir)/logrotate.d
logrotate_DATA		= logrotate/pcsd

servicedir		= $(SYSTEMD_UNIT_DIR)
service_DATA		= pcsd.service pcsd-ruby.service

pcsddir			= $(LIB_DIR)/pcsd
pcsd_SCRIPTS		= \
			  pcsd \
			  pcsd-cli.rb

dist_pcsd_DATA		= \
			  auth.rb \
			  bootstrap.rb \
			  capabilities.rng \
			  capabilities.xml \
			  cfgsync.rb \
			  cluster_entity.rb \
			  cluster.rb \
			  config.rb \
			  corosyncconf.rb \
			  pcsd_action_command.rb \
			  pcsd-cli-main.rb \
			  pcsd_exchange_format.rb \
			  pcsd_file.rb \
			  pcsd.rb \
			  pcsd_remove_file.rb \
			  pcs.rb \
			  permissions.rb \
			  remote.rb \
			  resource.rb \
			  rserver.rb

pcsd_DATA		= \
			  settings.rb

pcsdpubdir		= ${pcsddir}/public
dist_pcsdpub_DATA	= \
			  public/ui_instructions.html

clean-local:
	rm -f test/*.tmp

install-data-local:
	$(MKDIR_P) $(DESTDIR)/$(sysconfdir)/pam.d
	$(INSTALL_DATA) $(srcdir)/pam/pcsd.$(DISTROEXT) $(DESTDIR)/$(sysconfdir)/pam.d/pcsd
if INSTALL_EMBEDDED_GEMS
	$(MKDIR_P) $(DESTDIR)${GEM_HOME}
	cp -rp ../${PCSD_BUNDLED_DIR_ROOT_LOCAL}/* $(DESTDIR)${GEM_HOME}
	rm -rf $(DESTDIR)${GEM_HOME}/cache
endif
	$(MKDIR_P) -m 0700 $(DESTDIR)$(localstatedir)/log/pcsd
	$(MKDIR_P) -m 0700 $(DESTDIR)$(localstatedir)/lib/pcsd

uninstall-local:
	rm -rf $(DESTDIR)/$(sysconfdir)/pam.d/pcsd
	rmdir $(DESTDIR)/$(sysconfdir)/pam.d 2>/dev/null || :
if INSTALL_EMBEDDED_GEMS
	rm -rf $(DESTDIR)/${GEM_HOME}
endif
	rmdir $(DESTDIR)/$(localstatedir)/log/pcsd 2>/dev/null || :
	rmdir $(DESTDIR)/$(localstatedir)/lib/pcsd 2>/dev/null || :
