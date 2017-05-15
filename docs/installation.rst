.. _installation:

Installation
============

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

Ontobio requires Python version 3.4 or higher

With pyvenv
-----------

::

    cd ontobio
    pyvenv venv
    source venv/bin/activate
    export PYTHONPATH=.:$PYTHONPATH
    pip install -r requirements.txt

