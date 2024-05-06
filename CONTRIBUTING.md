# Contributing to the pcs project

## Running pcs and its test suite

### Python virtual environment
* Using Python virtual environment (pyenv) is highly recommended, as it
  provides means of isolating development packages from system-wide packages.
  It allows to install specific versions of python packages, which pcs depends
  on, independently on the rest of the system.
* In this tutorial, we choose to create a pyenv in `~/pyenvs/pcs` directory.
* Create a base directory: `mkdir ~/pyenvs`
* Create a pyenv: `python3 -m venv --system-site-packages ~/pyenvs/pcs`
* To activate the pyenv, run `source ~/pyenvs/pcs/bin/activate` or
  `. ~/pyenvs/pcs/bin/activate`
* To deactivate the pyenv, run `deactivate`

### Configure pcs
* Go to pcs directory.
* If you created a pyenv according to the previous section, make sure it is
  activated.
* Run `./autogen.sh`.
  * This generates `configure` script based on `configure.ac` file.
  * It requires an annotated tag to be present in git repository. The easiest
    way to accomplish that is to add the upstream pcs repository as a remote
    repository.
* Run `./configure`.
  * This checks all the dependencies and creates various files (including
    `Makefile` files) based on theirs `*.in` templates.
  * To list available options and their description, run `./configure -h`.
  * Recommended setup for development is to run
    `./configure --enable-local-build --enable-dev-tests
    --enable-destructive-tests --enable-concise-tests --enable-webui`
* Run `make`.
  * This downloads and installs dependencies, such as python modules and
    rubygems.

### Run pcs and pcsd
* To run pcs, type `pcs/pcs`.
* To run pcsd, type `sripts/pcsd.sh`.

### Pcs test suite
* To run all the tests, type `make check`.
  * You may run specific tests like this:
    * `make black_check`
    * `make isort_check`
    * `make mypy`
    * `make pylint`
    * `make tests_tier0`
    * `make tests_tier1`
    * `make pcsd-tests`
  * To run specific tests from python test suite, type `pcs_test/suite <test>`
* When `make check` passes, you may want to run `make distcheck`.
  * This generates a distribution tarball and checks it.
  * The check is done by extracting files from the tarball, running
    `./configure` and `make check`.
  * Note, that `./configure` is run with no options, so it requires
    dependencies to be installed system wide. This can be overridden by running
    `make distcheck DISTCHECK_CONFIGURE_FLAGS='<flag>...'`.
  * The point of this test is to make sure all necessary files are present in
    the tarball.
* To run black code formatter, type `make black`.
* To run isort code formatter, type `make isort`.

### Distribution tarball
* To create a tarball for distribution, run `make dist`.
* The user of the tarball is supposed to run `./configure` with options they
  see fit. Then, they can run `make` with any target they need.

### Important notes
* All system-dependent paths must be located in `pcs/settings.py.in` and
  `pcsd/settings.rb.in` files.
* Do not forget to run `./configure` after changing any `*.in` file.
* All files meant to be distributed must be listed in `EXTRA_DIST` variable in
  `Makefile.am` file in specific directory (`pcs`, `pcs/pcs`, `pcs/pcs_tests`,
  `pcs/pcsd`), with the exception of files created by autoconf / automake.
