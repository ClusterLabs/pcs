#!/usr/bin/env python2

from distutils.core import setup

setup(name='pcs',
    version='0.9.142',
    description='Pacemaker Configuration System',
    author='Chris Feist',
    author_email='cfeist@redhat.com',
    url='http://github.com/feist/pcs',
    packages=['pcs'],
    package_data={'pcs':['bash_completion.d.pcs','pcs.8']},
    py_modules=['pcs']
    )
