MAINTAINERCLEANFILES	= Makefile.in

pcsdatadir			= $(LIB_DIR)/pcs/data
dist_pcsdata_DATA		= \
			  ocf-1.0.rng \
			  ocf-1.1.rng

uninstall-local:
	rmdir $(DESTDIR)/$(pcsdatadir) 2>/dev/null || :
