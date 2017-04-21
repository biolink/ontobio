from ontobio.ontol_factory import OntologyFactory
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.assocmodel import AssociationSet
import logging
import random

CVP = 'MP:0004084' # cardiomyopathy
MUS = 'NCBITaxon:10090'

def test_construct():
    """
    enrichment test

    build a gene set from MP term for cardiomyopathy;
    test for enrichment against GO
    """
    ofactory = OntologyFactory()
    afactory = AssociationSetFactory()
    logging.info("Creating mp handle")
    mp = ofactory.create('obo:mp')
    logging.info("Getting pheno assocs")
    aset_phen = afactory.create(ontology=mp,
                                subject_category='gene',
                                object_category='phenotype',
                                taxon=MUS)
    
    logging.info("Creating go handle")
    ont = ofactory.create('go')
    logging.info("Getting go assocs")
    aset = afactory.create(ontology=ont,
                           subject_category='gene',
                           object_category='function',
                           taxon=MUS)

    logging.info("Getting sample")
    sample = aset_phen.query([CVP],[])
    logging.info("sample = {}".format(len(sample)))

    rs = aset.enrichment_test(sample, threshold=1e-2, labels=True, direction='less')
    for r in rs:
        print("UNDER: "+str(r))

    
    rs = aset.enrichment_test(sample, threshold=0.05, labels=True)
    for r in rs:
        print(str(r))


#test_construct()
