#!/usr/bin/env python

import os
from setuptools import find_packages, setup

# Package meta-data.
NAME = 'my_first_goat'
DESCRIPTION = (
    'Discord bot helping to manage gaming discord server (members and loot messages)'
)
URL = None  # 'https://github.com/me/myproject'
EMAIL = 'kossak.git@gmail.com'
AUTHOR = 'Kossak'
REQUIRES_PYTHON = '>=3.6.0'

REQUIRED = []

here = os.path.abspath(os.path.dirname(__file__))
packages = find_packages(exclude=('tests',))

if not REQUIRED:
    with open(os.path.join(here, 'requirements.txt')) as f:
        REQUIRED = f.read().splitlines()

with open(os.path.join(here, 'README.rst')) as f:
    long_description = '\n' + f.read()

# get package version:
with open(os.path.join(here, NAME, '__version__.py')) as f:
    text = f.read()
    if '\'' in text:
        sep = '\''
    else:
        sep = '"'
    VERSION = text.split(sep)[1]

# SETUP
setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=long_description,
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    packages=packages,
    entry_points='''
          [console_scripts]
          my_first_goat = my_first_goat.__main__:main
          ''',
    install_requires=REQUIRED,
    package_data={NAME: ['data/config_template.toml']},
    include_package_data=True,
    license='MIT',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
    ],
)
