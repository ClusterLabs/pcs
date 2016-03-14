#!/usr/bin/env python

from setuptools import setup

setup(
    name='pcs',
    version='0.9.149',
    description='Pacemaker Configuration System',
    author='Chris Feist',
    author_email='cfeist@redhat.com',
    url='http://github.com/feist/pcs',
    packages=['pcs', 'pcs.lib', 'pcs.lib.cib'],
    package_data={'pcs':['bash_completion.d.pcs','pcs.8']},
    entry_points={
        'console_scripts': [
            'pcs = pcs.cli:main',
        ],
    },
)
