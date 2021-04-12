# to build official release tarballs, handle tagging and publish.

project = pcs

deliverables = $(project)-$(version).sha256 \
               $(project)-$(version).tar.bz2 \
               $(project)-$(version).tar.gz \
               $(project)-$(version).tar.xz


.PHONY: all
all: tag tarballs


.PHONY: checks
checks:
ifeq (,$(version))
	@echo ERROR: need to define version=
	@exit 1
endif
	@if [ ! -d .git ]; then \
		echo This script needs to be executed from top level cluster git tree; \
		exit 1; \
	fi
	@if [ -n "$$(git status --untracked-files=no --porcelain 2>/dev/null)" ]; then \
		echo Stash or rollback the uncommitted changes in git first; \
		exit 1; \
	fi


.PHONY: setup
setup: checks
	./autogen.sh
	./configure
	$(MAKE) maintainer-clean


.PHONY: tag
tag: setup ./tag-$(version)

tag-$(version):
ifeq (,$(release))
	@echo Building test release $(version), no tagging
	echo '$(version)' > .tarball-version
else
	# following will be captured by git-version-gen automatically
	git tag -a -m "v$(version) release" v$(version) HEAD
	@touch $@
endif


.PHONY: tarballs
tarballs: tag
	./autogen.sh
	./configure
	$(MAKE) distcheck


.PHONY: sha256
sha256: $(project)-$(version).sha256

$(deliverables): tarballs

$(project)-$(version).sha256:
	# checksum anything from deliverables except for in-prep checksums file
	sha256sum $(deliverables:$@=) | sort -k2 > $@


.PHONY: publish
publish:
ifeq (,$(release))
	@echo Building test release $(version), no publishing!
else
	git push --follow-tags origin
	@echo Hey you!  Yeah you, looking somewhere else!
	@echo Remember to notify cluster-devel/RH and users/ClusterLabs MLs.
endif


.PHONY: clean
clean:
	rm -rf $(project)* tag-* .tarball-version
