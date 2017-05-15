.. _concepts:

Basic Concepts
==============


Ontologies
----------

.. currentmodule:: ontobio.ontol

We leverage :mod:`networkx`

* `obographs <http://https://github.com/geneontology/obographs>`_
* `motivation <http://douroucouli.wordpress.com/2016/10/04/a-developer-friendly-json-exchange-format-for-ontologies/>`_

Class: :class:`Ontology`                   

.. code-block:: python

    from ontobio.ontol_factory import OntologyFactory
    ont = OntologyFactory().create("go")
    [nucleus] = ont.search('nucleus')
    ancestors = ont.ancestors(nucleus)
    

Alternatives
^^^^^^^^^^^^

Ontobio is aimed primarily at bioinformatics applications, which
typically have lightweight ontology requirements: navigation and
grouping via graph structures, access to basic metadata such as
synonyms. 


  
Associations
------------

.. currentmodule:: ontobio.assocmodel

The association model is a generalization of the GO
association/annotation model. The typical scenario is to link a
biological entity (gene, gene product, protein complex, variant or
allele, disease, individual organism) to a descriptive ontology class,
via a defined relationship type, plus metadata such as provenance and
evidence. Note that it can be generalized further also link two
entities (e.g. gene-gene, such as homology or relationship) or two
ontology classes. In fact the distinction between *entities* and
*ontology nodes* is one of convenience.

Categories
^^^^^^^^^^

**TODO**

Lightweight vs Complete
^^^^^^^^^^^^^^^^^^^^^^^

For many purposes, it is only necessary to use a very lightweight
representation of associations, as a collection of pairwise mappings
between *subjects* and *objects*. This can be found in the class :class:`AssociationSet`. An association set can be constructed using a
particular set of criteria - e.g. all GO annotations to all zebrafish
genes.

For other purposes it is necessary to have a full-blown
representation, in which each association is modeled complete with
evidence, provenance and so on. **TODO** Link to documentation.

Example Asssociation Set
^^^^^^^^^^^^^^^^^^^^^^^^

This example shows a simple set of pairwise associations:

.. code-block:: python

    from ontobio.assoc_factory import AssociationSetFactory
    afactory = AssociationSetFactory()
    aset = afactory.create(ontology=ont,
                           subject_category='gene',
                           object_category='function',
                           taxon='NCBITaxon:7955') ## Zebrafish

Assocations vs ontology edges
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The distinction between an *association* (aka *annotation*) and an
ontology edge is primarily one of convenience. For example, it is
possible to combine diseases, phenotypes and the associations between
them in one graph, with relationship type *has-phenotype* connecting
these. Similary, gene could be added to a GO molecular function graph, connecting via
*capable-of*.

By stratifying the two sets of entities and using a different data
structure to connect these, we make it easier to define and perform
certain operations, e.g. enrichment, semantic similarity, machine
learning, etc.

But we also
provide means of interconverting between these two perspectives
(**TODO**).
                           
See also
^^^^^^^^

* `GPAD <https://github.com/geneontology/go-annotation/tree/master/specs>`_
* `OBAN <https://github.com/EBISPOT/OBAN>`_

Class: :class:`AssociationSet`                   

Identifiers
-----------

Ontobio uses CURIEs to identify entities, e.g. OMIM:123,
GO:0001850. See :doc:`identifiers` for more information

