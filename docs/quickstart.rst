.. _quickstart:

Quick start
===========

.. currentmodule:: ontobio

This guide assumes you have already installed ontobio.  If not, then follow the steps in the
:ref:`installation` section.

Command Line
------------

You can use a lot of the functionality without coding a line of
python, via the command line wrappers in the `bin` directory. For
example, to search on ontology for matching labels:

::

   ogr.py -r mp %cerebellum%

See the :ref:`commandline` section for more details.


Notebooks
---------

We provide `Jupyter Notebooks <http://nbviewer.jupyter.org/github/biolink/ontobio/tree/master/notebooks/>`_
to illustrate the functionality of the python library. These can also
be used interactively.

See the :ref:`notebooks` section for more details.

Python
------

This code example shows some of the basics of working with remote
ontologies and associations

.. code-block:: python

    from ontobio.ontol_factory import OntologyFactory
    from ontobio.assoc_factory import AssociationSetFactory

    ## label IDs for convenience
    MOUSE = 'NCBITaxon:10090'
    NUCLEUS = 'GO:0005634'
    TRANSCRIPTION_FACTOR = 'GO:0003700'
    PART_OF = 'BFO:0000050'

    ## Create an ontology object containing all of GO, with relations filtered
    ofactory = OntologyFactory()
    ont = ofactory.create('go').subontology(relations=['subClassOf', PART_OF])

    ## Create an AssociationSet object with all mouse GO annotations
    afactory = AssociationSetFactory()
    aset = afactory.create(ontology=ont,
                           subject_category='gene',
                           object_category='function',
                           taxon=MOUSE)

    genes = aset.query([TRANSCRIPTION_FACTOR],[NUCLEUS])
    print("Mouse TF genes NOT annotated to nucleus: {}".format(len(genes)))
    for g in genes:
        print("  Gene: {} {}".format(g,aset.label(g)))

See the notebooks for more examples. For more documentation on
specific components, see the rest of these docs, or skip forward to
the :doc:`api` docs.


Web Services
------------

See the :doc:`biolink` section
