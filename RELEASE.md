## How to release new pcs version

### Bump changelog version

* Run `make -f make/release.mk bump-changelog version=<version>`.
  * This will create commit with updated CHANGELOGE.md
* Merge commit to upstream (via PR or push it directly)

### Create tarballs with new release version

* Run
  `make -f make/release.mk tarballs version=<version>
  "configure_options=--enable-local-build"`
  * The <version> should be next pcs version (e.g. version=0.10.9)
* Test generated tarballs

### Create annotated tag

* Run
  `make -f make/release.mk tag version=<version>
  "configure_options=--enable-local-build" release=yes`
* If your upstream remote branch is origin, run
  `make -f make/release.mk publish release=yes`
  or `git push <remote> <tag>`
