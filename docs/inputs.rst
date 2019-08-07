.. _inputs:

Inputs
======

Ontobio is designed to work with either *local* files or with *remote*
information accessed via Services.

Access is generally mediated using a *factory* object. The client
requests an ontology via a *handle* to the factory, and the factory
will return with the relevant implementation instantiated.

.. currentmodule:: ontobio.ontol_factory

Local JSON ontology files
-------------------------

You can load an ontology from disk (or a URL) that conforms to the
`obographs <http://https://github.com/geneontology/obographs>`_ JSON standard.

Command line example:

::

   ogr.py -r path/to/my/file.json

Code example, using an :class:`OntologyFactory`

.. code-block:: python

    from ontobio.ontol_factory import OntologyFactory
    ont = OntologyFactory().create("/path/to/my/file.json")

   
Local OWL and OBO-Format files
------------------------------

Requirement: OWLTools

Command line example:

::

   ogr.py -r path/to/my/file.owl

Code example, using an :class:`OntologyFactory`

.. code-block:: python

    from ontobio.ontol_factory import OntologyFactory
    ont = OntologyFactory().create("/path/to/my/file.owl")


Local SKOS RDF Files
--------------------

SKOS is an RDF data model for representing thesauri and terminologies.

See the `SKOS primer <https://www.w3.org/TR/skos-primer/>`_ for more details.

Command line example:

::

   ogr.py -r path/to/my/skosfile.ttl

Code example, using an :class:`OntologyFactory`

.. code-block:: python

    from ontobio.ontol_factory import OntologyFactory
    ont = OntologyFactory().create("skos:/path/to/my/skosfile.ttl")
    
Remote SPARQL ontology access
-----------------------------

The default SPARQL service used is the OntoBee one, which provides
access to all OBO library ontologies

.. warning ::

    May change in future

Command line example:

::

   ogr.py -r cl

Note that the official OBO library prefix must be used, e.g. ``cl``,
``go``, ``hp``. See http://obofoundry.org/   
   
Code example, using an :class:`OntologyFactory`

.. code-block:: python

    from ontobio.ontol_factory import OntologyFactory
    ont = OntologyFactory().create("cl")

Remote SciGraph ontology access
-------------------------------

.. warning ::

    Experimental

Command line example:

::

   ogr.py -r scigraph:ontology

Code example, using an :class:`OntologyFactory`

.. code-block:: python

    from ontobio.ontol_factory import OntologyFactory
    ont = OntologyFactory().create("scigraph:ontology")


.. warning ::

    Since SciGraph contains multiple graphs interwoven together, care
    must be taken on queries that don't use relationship types, as
    ancestor/descendant lists may be large
    
    
Local GAF or GPAD association files
-----------------------------------

.. currentmodule:: ontobio.assocmodel

The :class:`ontobio.AssociationSet` class provides a lightweight way
of storing sets of associations.

.. currentmodule:: ontobio.assoc_factory

Code example: parse all associations from a GAF, and filter according
to provider:

.. code-block:: python

    p = GafParser()
    assocs = p.parse(open(POMBASE,"r"))
    pombase_assocs = [a for a in assocs if a['provided_by'] == 'UniProt']

Code example, creating `AssociationSet` objects, using an :class:`AssociationSetFactory`

.. code-block:: python

   
   afactory = AssociationSetFactory()
   aset = afactory.create_from_file(file=args.assocfile,ontology=ont)


Remote association access via GOlr
----------------------------------

.. currentmodule:: ontobio.golr.golr_query

GOlr is the name given to the Solr instance used by the Gene Ontology
and Planteome projects. This has been generalized for use with the
Monarch Initiative project.

GOlr provides fast access and faceted search on top of *Associations*
(see the :doc:`concepts` section for more on the concept of
associations). Ontobio provides both a transparent facade over GOlr,
and also direct access to advanced queries.

By default an *eager* loading strategy is used: given a set of query
criteria (minimally, subject and object *categories* plus a taxon, but
optionally including evidence etc), all asserted pairwise associations
are loaded into an association set. E.g.

.. code-block:: python

   aset = afactory.create(ontology=ont,
                           subject_category='gene',
                           object_category='function',
                           taxon=MOUSE)

Additionally, this is cached so future calls will not invoke the
service overhead.

For performing advanced analytic queries over the complete GOlr
database, see the :class:`GolrAssociationQuery` class. **TODO**
provide examples.


Remote association access via wikidata
--------------------------------------

.. currentmodule:: ontobio.sparql.wikidata

**TODO**

Use of caching
--------------

When using remote services to access ontology or association set
objects, caching is automatically used to avoid repeated
access. Currently an *eager* strategy is used, in which large blocks
are fetched in advance, though in future *lazy* strategies are
optionally employed.


To be implemented
-----------------

* Remote access to SciGraph/Neo4J
* Remote access to Chado databases
* Remote access to Knowledge Beacons
  
