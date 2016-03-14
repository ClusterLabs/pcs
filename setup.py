#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='pcs',
    version='0.9.149',
    description='Pacemaker Configuration System',
    author='Chris Feist',
    author_email='cfeist@redhat.com',
    url='http://github.com/feist/pcs',
    packages=find_packages(exclude=["*.test", "*.test.*", "test.*", "test"]),
    package_data={'pcs':['bash_completion.d.pcs','pcs.8']},
    entry_points={
        'console_scripts': [
            'pcs = pcs.cli:main',
        ],
    },
)
