.. _analyses:

Ontology-Based Analyses
=======================

.. warning ::

    In the future the analysis methods may migrate from the `AssociationSet`
    class to dedicated analysis engine classes.

Enrichment
----------

See the `Notebook example <http://nbviewer.jupyter.org/github/biolink/ontobio/blob/master/notebooks/Phenotype_Enrichment.ipynb>`_

OntoBio allows for generalized gene set enrichment: given a set of
annotations that map genes to descriptor terms, and an input set of
genes, and a background set, find what terms are enriched in the input
set compared to the background.

With OntoBio, enrichment tests work for any annotation corpus, not
necessarily just gene-oriented. For example,
disease-phenotype. However, care must be taken with underlying
assumptions with non-gene sets.

The very first thing you need to do before an enrichment analysis is
fetch both an `Ontology` object and an `AsssociationSet` object. This
could be a mix of local files or remote service/database. See
:ref:`inputs` for details.

Assume that we are using a remote ontology and local GAF:     

.. code-block:: python

    from ontobio import OntologyFactory
    from ontobio import AssociationSetFactory
    ofactory = OntologyFactory()
    afactory = AssociationSetFactory()
    ont = ofactory.create('go')
    aset = afactory.create_from_gaf('my.gaf', ontology=ont)

Assume also that we have a set of sample and background gene IDs, the
test is:    
    
.. code-block:: python

    enr = aset.enrichment_test(subjects=gene_ids, background=background_gene_ids, threshold=0.00005, labels=True)    

This returns a list of dicts (**TODO** - decide if we want to make
this an object and follow a standard class model)

**NOTE** the input gene IDs *must* be the same ones used in the
AssociationSet. If you load from a GAF, this is the IDs that are
formed by combining col1 and col2, separated by a
":". E.g. UniProtKB:P123456

What if you have different IDs? Or what if you just have a list of
gene symbols? In this case you will need to *map* these names or IDs,
the subject of the next section.

Reproducibility
~~~~~~~~~~~~~~~

For reproducible analyses, use a **versioned PURL** for the ontology

Command line wrapper
~~~~~~~~~~~~~~~~~~~~

You can use the `ontobio-assoc` command to run enrichment
analyses. Some examples:

Create a gene set for all genes in "regulation of bone development"
(GO:1903010). Find other terms for which this is enriched (in human)

.. code-block:: console

    # find all mouse genes that have 'abnormal synaptic transmission' phenotype
    # (using remote sparql service for MP, and default (Monarch) for associations
    ontobio-assoc.py -v -r mp -T NCBITaxon:10090 -C gene phenotype query -q MP:0003635 > genes.txt

    # get IDs
    cut -f1 -d ' ' genes.txt > genes.ids

    # enrichment, using GO
    ontobio-assoc.py  -r go -T NCBITaxon:10090 -C gene function enrichment -s genes.ids

    # resulting GO terms are not very surprising...
    2.48e-12 GO:0045202 synapse
    2.87e-11 GO:0044456 synapse part
    3.66e-08 GO:0007270 neuron-neuron synaptic transmission
    3.95e-08 GO:0098793 presynapse
    1.65e-07 GO:0099537 trans-synaptic signaling
    1.65e-07 GO:0007268 chemical synaptic transmission
    

Further reading
~~~~~~~~~~~~~~~

For API docs, see `enrichment_test in AssociationSet model <http://ontobio.readthedocs.io/en/latest/api.html#assocation-object-model>`_

Identifier Mapping
------------------

**TODO**

Semantic Similarity
-------------------

**TODO**

To follow progress, see `this PR <https://github.com/biolink/ontobio/pull/49>`_

Slimming
--------

**TODO**

Graph Reduction
---------------

**TODO**

Lexical Analyses
----------------

See the `lexmap API docs <http://ontobio.readthedocs.io/en/latest/api.html#lexmap>`_

You can also use the command line:

.. code-block:: console

   ontobio-lexmap.py ont1.json ont2.json > mappings.tsv

The inputs can be any kind of handle - a local ontology file or a
remote ontology accessed via services.

For example, this will work:

   ontobio-lexmap.py mp hp wbphenotype > mappings.tsv

See :ref:`inputs` for more details.

For examples of lexical mapping pipelines, see:

- `<https://github.com/cmungall/sweet-obo-alignment>`_
- `<https://github.com/monarch-initiative/monarch-disease-ontology/tree/master/src/icd10>_

These have examples of customizing configuration using a yaml file.
