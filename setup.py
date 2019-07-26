#!/usr/bin/python3

import os

from setuptools import setup, Command, find_packages
from setuptools import Distribution
from setuptools.command.install import install


class CleanCommand(Command):
    user_options = []
    def initialize_options(self):
        #pylint: disable=attribute-defined-outside-init
        self.cwd = None
    def finalize_options(self):
        #pylint: disable=attribute-defined-outside-init
        self.cwd = os.getcwd()
    def run(self):
        assert os.getcwd() == self.cwd, 'Must be in package root: %s' % self.cwd
        os.system('rm -rf ./build ./dist ./*.pyc ./*.egg-info')

# The following classes (_ScriptDirSpy and ScriptDir) allows to get script
# directory.
#
# The root reason for introduction `scriptdir` command was the error in
# setuptools, which caused wrong shebang in script files
# (see https://github.com/pypa/setuptools/issues/188 and
# https://bugzilla.redhat.com/1353934). As a workaround the shebang was
# corrected in pcs Makefile, however hardcoded path didn't work on some systems,
# so there was a need to get a reliable path to a script (or bin) directory.
#
# Alternative approach would be correct shebang here in `setup.py`. However, it
# would mean to deal with possible user options (like --root, --prefix,
# --install-lib etc. - or its combinations) consistently with setuptools (and it
# can be patched in some OS).
class _ScriptDirSpy(install):
    """
    Fake install. Its task is to make the scripts directory path accessible to
    caller.
    """
    def run(self):
        self.distribution.install_scripts = self.install_scripts

class ScriptDir(Command):
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass

    def run(self):
        """
        Print script directory to stdout.

        Unfortunately, setuptools automatically prints "running scriptdir" on
        stdout. So, for example, the output will look like this:
        running scriptdir
        /usr/local/bin

        The shell command `tail` can be used to get only the relevant line:
        `python setup.py scriptdir | tail --lines=1`

        """

        # pylint: disable=no-self-use
        # Create fake install to get a setuptools script directory path.
        dist = Distribution({'cmdclass': {'install': _ScriptDirSpy}})
        dist.dry_run = True
        dist.parse_config_files()
        command = dist.get_command_obj('install')
        command.ensure_finalized()
        command.run()
        print(dist.install_scripts)

setup(
    name='pcs',
    version='0.10.2',
    description='Pacemaker Configuration System',
    author='Chris Feist',
    author_email='cfeist@redhat.com',
    url='https://github.com/ClusterLabs/pcs',
    packages=find_packages(exclude=["pcs_test", "pcs_test.*"]),
    package_data={'pcs':[
        'bash_completion',
        'pcs.8',
        'pcs',
    ]},
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'pcs = pcs.app:main',
            'pcsd = pcs.run:daemon',
            'pcs_snmp_agent = pcs.run:pcs_snmp_agent',
            'pcs_internal = pcs.pcs_internal:main',
        ],
    },
    cmdclass={
        'clean': CleanCommand,
        'scriptdir': ScriptDir,
    }
)
