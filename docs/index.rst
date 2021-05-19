
Welcome to ontobio's documentation!
===================================

Library for working with ontologies and ontology associations.

Provides:

-  Transparent access to both local files
   (`obo-json <https://github.com/geneontology/obographs>`__,
   `GAF <http://ontobio.readthedocs.io/en/latest/inputs.html#local-gaf-or-gpad-association-files>`__)
   and remote services (OntoBee, GO/GOlr,
   `Monarch <http://monarchinitiative.org>`__, Wikidata)
-  Powerful graph operations for traversing logical structure of  ontologies
-  object model for working with ontology metadata elements (synonyms, etc)
-  Access to gene product functional annotations in GO
-  Access to gene/variant/disease/genotype etc info from Monarch
-  Simple basis for building bioinformatics analyses and applications (e.g.
   `enrichment <http://ontobio.readthedocs.io/en/latest/analyses.html#enrichment>`__)
-  Underpinnings for web service APIs
-  Rich command line access for non-programmers (see :doc:`commandline`)
-  Examples in :doc:`notebooks`
  
Compatibility
=============

ontobio requires Python 3.4+.

Contributing
============

https://github.com/biolink/ontobio

Installation
============

You can install ontobio with pip:

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
   go_rules

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
