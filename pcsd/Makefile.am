EXTRA_DIST		= \
			  pam/pcsd.debian \
			  pam/pcsd.fedora \
			  test/cib1.xml \
			  test/cluster.conf \
			  test/corosync.conf \
			  test/crm1.xml \
			  test/known-hosts \
			  test/pcsd_test_utils.rb \
			  test/pcs_settings.conf \
			  test/test_all_suite.rb \
			  test/test_auth.rb \
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
			  api_v1.rb \
			  auth.rb \
			  bootstrap.rb \
			  capabilities.rng \
			  capabilities.xml \
			  cfgsync.rb \
			  cluster_entity.rb \
			  cluster.rb \
			  config.rb \
			  corosyncconf.rb \
			  fenceagent.rb \
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

pcsdviewsdir		= ${pcsddir}/views

dist_pcsdviews_DATA	= \
			  views/_acls.erb \
			  views/_cluster_list.erb \
			  views/_configure.erb \
			  views/_dialogs.erb \
			  views/login.erb \
			  views/main.erb \
			  views/manage.erb \
			  views/nodes.erb \
			  views/_permissions_cluster.erb \
			  views/permissions.erb \
			  views/_resource.erb \
			  views/_resource_list.erb

pcsdpubdir		= ${pcsddir}/public
dist_pcsdpub_DATA	= \
			  public/ui_instructions.html

pcsdpubjsdir		= ${pcsddir}/public/js
dist_pcsdpubjs_DATA	= \
			  public/js/api.js \
			  public/js/cluster-destroy.js \
			  public/js/cluster-setup.js \
			  public/js/ember-1.4.0.js \
			  public/js/handlebars-v1.2.1.js \
			  public/js/jquery-1.9.1.min.js \
			  public/js/jquery-ui-1.10.1.custom.min.js \
			  public/js/node-add.js \
			  public/js/node-remove.js \
			  public/js/nodes-ember.js \
			  public/js/pcsd.js \
			  public/js/tools.js

pcsdpubjsdevdir		= ${pcsddir}/public/js/dev
dist_pcsdpubjsdev_DATA	= \
			  public/js/dev/clusters-overview-mock.js \
			  public/js/dev/cluster_status.mock.js \
			  public/js/dev/dev.js \
			  public/js/dev/tests-cluster-destroy.js \
			  public/js/dev/tests-cluster-setup.js \
			  public/js/dev/tests-node-add.js \
			  public/js/dev/tests-node-remove.js

pcsdpubimagesdir	= ${pcsddir}/public/images
dist_pcsdpubimages_DATA	= \
			  public/images/action-icons.png \
			  public/images/favicon.png \
			  public/images/field_bg.png \
			  public/images/HAM-logo.png \
			  public/images/Shell_bg.png

pcsdpubcssdir		= ${pcsddir}/public/css
dist_pcsdpubcss_DATA	= \
			  public/css/jquery-ui-1.10.1.custom.css \
			  public/css/liberation.css \
			  public/css/overpass.css \
			  public/css/style.css

pcsdpubcssimgsdir	= ${pcsddir}/public/css/images
dist_pcsdpubcssimgs_DATA= \
			  public/css/images/animated-overlay.gif \
			  public/css/images/pbar-ani.gif \
			  public/css/images/ui-bg_flat_30_cccccc_40x100.png \
			  public/css/images/ui-bg_flat_50_5c5c5c_40x100.png \
			  public/css/images/ui-bg_glass_20_555555_1x400.png \
			  public/css/images/ui-bg_glass_40_0078a3_1x400.png \
			  public/css/images/ui-bg_glass_40_ffc73d_1x400.png \
			  public/css/images/ui-bg_gloss-wave_25_333333_500x100.png \
			  public/css/images/ui-bg_highlight-soft_80_eeeeee_1x100.png \
			  public/css/images/ui-bg_inset-soft_25_000000_1x100.png \
			  public/css/images/ui-bg_inset-soft_30_f58400_1x100.png \
			  public/css/images/ui-icons_222222_256x240.png \
			  public/css/images/ui-icons_4b8e0b_256x240.png \
			  public/css/images/ui-icons_a83300_256x240.png \
			  public/css/images/ui-icons_cccccc_256x240.png \
			  public/css/images/ui-icons_ffffff_256x240.png

pcsd_fonts		= \
			  LiberationSans-BoldItalic.ttf;LiberationSans:style=BoldItalic \
			  LiberationSans-Bold.ttf;LiberationSans:style=Bold \
			  LiberationSans-Italic.ttf;LiberationSans:style=Italic \
			  LiberationSans-Regular.ttf;LiberationSans:style=Regular \
			  Overpass-Bold.ttf;Overpass:style=Bold \
			  Overpass-Regular.ttf;Overpass:style=Regular

clean-local:
	rm -f test/*.tmp

install-data-local:
	$(MKDIR_P) $(DESTDIR)/$(sysconfdir)/pam.d
	$(INSTALL_DATA) $(srcdir)/pam/pcsd.$(DISTROEXT) $(DESTDIR)/$(sysconfdir)/pam.d/pcsd
	$(MKDIR_P) $(DESTDIR)/${pcsdpubcssdir}
	$(foreach font,$(pcsd_fonts),\
		$(eval font_file = $(word 1,$(subst ;, ,$(font)))) \
		$(eval font_def = $(word 2,$(subst ;, ,$(font)))) \
		$(eval font_path = $(shell $(FCMATCH) '--format=%{file}' '$(font_def)')) \
		$(if $(font_path),ln -s -f $(font_path) $(DESTDIR)/${pcsdpubcssdir}/$(font_file);,$(error Font $(font_def) not found)) \
	)
if INSTALL_EMBEDDED_GEMS
	$(MKDIR_P) $(DESTDIR)${GEM_HOME}
	cp -rp ../${PCSD_BUNDLED_DIR_LOCAL}/* $(DESTDIR)${GEM_HOME}
	rm -rf $(DESTDIR)${GEM_HOME}/cache
endif
	$(MKDIR_P) -m 0700 $(DESTDIR)$(localstatedir)/log/pcsd
	$(MKDIR_P) -m 0700 $(DESTDIR)$(localstatedir)/lib/pcsd

uninstall-local:
	rm -rf $(DESTDIR)/$(sysconfdir)/pam.d/pcsd
	rmdir $(DESTDIR)/$(sysconfdir)/pam.d 2>/dev/null || :
	$(foreach font,$(pcsd_fonts),\
		$(eval font_file = $(word 1,$(subst ;, ,$(font)))) \
		$(if $(font_file),rm -f $(DESTDIR)/${pcsdpubcssdir}/$(font_file);,$(error Font $(font_file) not found)) \
	)
	rmdir $(DESTDIR)/${pcsdpubcssdir} || :
if INSTALL_EMBEDDED_GEMS
	rm -rf $(DESTDIR)/${GEM_HOME}
endif
	rmdir $(DESTDIR)/$(localstatedir)/log/pcsd 2>/dev/null || :
	rmdir $(DESTDIR)/$(localstatedir)/lib/pcsd 2>/dev/null || :
