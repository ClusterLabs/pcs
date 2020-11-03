EXTRA_DIST		= 

MAINTAINERCLEANFILES	= Makefile.in

# install
bashcompletiondir	= $(sysconfdir)/bash_completion.d
dist_bashcompletion_DATA= bash_completion/pcs

snmpmibsdir		= $(SNMP_MIB_DIR)
dist_snmpmibs_DATA	= snmp/mibs/PCMK-PCS-MIB.txt \
			  snmp/mibs/PCMK-PCS-V1-MIB.txt

dist_man8_MANS		= pcs.8 snmp/pcs_snmp_agent.8

sysconfigdir		= $(CONF_DIR)
dist_sysconfig_DATA	= snmp/conf/pcs_snmp_agent

servicedir		= $(SYSTEMD_UNIT_DIR)
service_DATA		= snmp/pcs_snmp_agent.service
