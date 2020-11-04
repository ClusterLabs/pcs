EXTRA_DIST		= 

MAINTAINERCLEANFILES	= Makefile.in \
			  logrotate/pcsd \
			  pcsd.service pcsd-ruby.service

# install
dist_man8_MANS		= pcsd.8

defconfigdir		= $(CONF_DIR)
dist_defconfig_DATA	= conf/pcsd

logrotatedir		= $(sysconfdir)/logrotate.d
logrotate_DATA		= logrotate/pcsd

servicedir		= $(SYSTEMD_UNIT_DIR)
service_DATA		= pcsd.service pcsd-ruby.service
