
Welcome to ontobio's documentation!
===================================

.. image:: https://travis-ci.org/biolink/ontobio.png?branch=master

Library for working with ontologies and ontology associations.

Provides:

* Transparent access to both local files (obo-json, GAF) and remote services (OntoBee,
  GO, Monarch, Wikidata)
* Powerful graph operations for traversing logical structure of
  ontologies
* object model for working with ontology metadata elements (synonyms,
  etc)
* Access to gene product functional annotations in GO
* Access to gene/variant/disease/genotype etc info from Monarch
* Simple basis for building bioinformatics analyses and applications
  (e.g. enrichment)
* Underpinnings for web service APIs
* Rich command line access for non-programmers (see :doc:`commandline`)
* Examples in :doc:`notebooks`
  
Compatibility
=============

ontobio requires Python 3.4+.

Installation
============

You can install flask-restplus with pip:

.. code-block:: console

    $ pip install ontobio

Documentation
=============

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   quickstart
   commandline
   notebooks
   concepts
   inputs
   outputs
   identifiers
   analyses
   ontologies_advanced

API Reference
-------------

If you are looking for information on a specific function, class or
method, this part of the documentation is for you.

.. toctree::
   :maxdepth: 2

   api

Additional Notes
----------------

.. toctree::
   :maxdepth: 2

   contributing
   changelog

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
