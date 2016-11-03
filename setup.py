#!/usr/bin/env python

import os

from setuptools import setup, Command, find_packages

class CleanCommand(Command):
    user_options = []
    def initialize_options(self):
        self.cwd = None
    def finalize_options(self):
        self.cwd = os.getcwd()
    def run(self):
        assert os.getcwd() == self.cwd, 'Must be in package root: %s' % self.cwd
        os.system('rm -rf ./build ./dist ./*.pyc ./*.egg-info')

setup(
    name='pcs',
    version='0.9.155',
    description='Pacemaker Configuration System',
    author='Chris Feist',
    author_email='cfeist@redhat.com',
    url='https://github.com/ClusterLabs/pcs',
    packages=find_packages(),
    package_data={'pcs':[
        'bash_completion.sh',
        'pcs.8',
        'pcs',
        'test/resources/*.xml',
        'test/resources/*.conf',
    ]},
    entry_points={
        'console_scripts': [
            'pcs = pcs.app:main',
        ],
    },
    cmdclass={
        'clean': CleanCommand,
    }
)
