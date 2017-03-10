#!/usr/bin/env python

import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='graphjoiner',
    version='0.4.0b15',
    description='Implementing GraphQL with joins',
    long_description=read("README.rst"),
    author='Michael Williamson',
    author_email='mike@zwobble.org',
    url='http://github.com/healx/python-graphjoiner',
    packages=['graphjoiner', 'graphjoiner.declarative'],
    keywords="graphql graph join ",
    install_requires=["graphql-core>=1.0.1,<1.1", "attrs>=16.1.0,<17", "six"],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
)

