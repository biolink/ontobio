import os
import sys
import re
import subprocess

import setuptools

if sys.version_info.major < 3:
    sys.exit("Error: Python 3 is required")

directory = os.path.dirname(os.path.abspath(__file__))

# version
init_path = os.path.join(directory, 'ontobio', '__init__.py')
with open(init_path) as read_file:
    text = read_file.read()
pattern = re.compile(r"^__version__ = ['\"]([^'\"]*)['\"]", re.MULTILINE)
version = pattern.search(text).group(1)


setuptools.setup(
    name='ontobio',
    version=version,
    author='Chris Mungall',
    author_email='cmungall@gmail.com',
    url='https://github.com/biolink/ontobio',
    description='Library for working with OBO Library Ontologies and associations',
    long_description=open("README.rst").read(),
    license='BSD',
    packages=setuptools.find_packages(),
    package_data={"ontobio": ["ontobio/config.yaml"]},

    keywords='ontology graph obo owl sparql networkx network',
    classifiers=[
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        'Topic :: Scientific/Engineering :: Information Analysis',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering :: Visualization'
    ],

    include_package_data=True,

    # Dependencies
    install_requires=[
        'networkx==1.11',
        'jsobject',
        'pyyaml',
        'pysolr',
        'requests',
        'sparqlwrapper',
        'cachier',
        'prefixcommons',
        'marshmallow==3.0.0b3',
        'scipy',
        'pandas',
        'click'
    ],

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'dev': ['plotly'],
        'test': ['pytest'],
    },
    scripts=['bin/ogr.py', 'bin/ontobio-assoc.py', 'bin/ontobio-parse-assocs.py', 'bin/ontobio-lexmap.py', 'bin/rdfgen.py', 'bin/validate.py']
    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    #entry_points={
    #    'console_scripts': [
    #        'sample=sample:main',
    #    ],
    #},
)
