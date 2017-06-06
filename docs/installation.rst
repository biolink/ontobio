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


With pyvenv
-----------

::

    cd ontobio
    pyvenv venv
    source venv/bin/activate
    export PYTHONPATH=.:$PYTHONPATH
    pip install -r requirements.txt

