.. _installation:

Installation
============

Ontobio requires Python version 3.4 or higher

Install with pip:

::

    pip install ontobio

Development Version
-------------------

The development version can be downloaded from GitHub.

::

    git clone https://github.com/biolink/ontobio.git
    cd ontobio
    pip install -e .[dev,test]


Alternately, pip can be directly used to install the master (or other) branch from git, as a pip requirement:

::

    pip install git+https://github.com/biolink/ontobio@master#egg=ontobio


With pyvenv
-----------

::

    cd ontobio
    pyvenv venv
    source venv/bin/activate
    export PYTHONPATH=.:$PYTHONPATH
    pip install -r requirements.txt

