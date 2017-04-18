from ontobio.ontol_factory import OntologyFactory
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.assocmodel import AssociationSet
import logging
import random

NUCLEUS = 'GO:0005634'
CYTOPLASM = 'GO:0005737'
MITO = 'GO:0005739'
MOUSE = 'NCBITaxon:10090'
TRANSCRIPTION_FACTOR = 'GO:0003700'
TRANSPORTER = 'GO:0005215'

def test_remote_go():
    """
    factory test
    """
    ofactory = OntologyFactory()
    afactory = AssociationSetFactory()
    ont = ofactory.create('go')
    aset = afactory.create(ontology=ont,
                           subject_category='gene',
                           object_category='function',
                           taxon=MOUSE)
    
    rs = aset.query([TRANSCRIPTION_FACTOR],[])
    print("Mouse genes annotated to TF: {} {}".format(rs, len(rs)))
    set_tf = rs
    
    rs = aset.query([NUCLEUS],[])
    print("Mouse genes annotated to nucleus: {} {}".format(rs, len(rs)))
    set_nucleus = rs
    assert(len(rs) > 100)
    
    rs = aset.query([TRANSCRIPTION_FACTOR, NUCLEUS],[])
    print("Mouse TF genes annotated to nucleus: {} {}".format(rs, len(rs)))
    assert(len(rs) > 100)
    set_nucleus_tf = rs
    assert(len(rs) < len(set_nucleus))

    rs = aset.query([NUCLEUS],[TRANSCRIPTION_FACTOR])
    print("Mouse non-TF genes annotated to nucleus: {} {}".format(rs, len(rs)))
    assert(len(rs) > 100)
    set_nucleus_non_tf = rs
    assert(len(rs) < len(set_nucleus))
    assert(len(set_nucleus_tf) + len(set_nucleus_non_tf) == len(set_nucleus))

    enr = aset.enrichment_test(subjects=set_tf, labels=True)
    print("ENRICHMENT (tf): {}".format(enr))
    [match] = [x for x in enr if x['c'] == NUCLEUS]
    print("ENRICHMENT (tf) for NUCLEUS: {}".format(match))
    assert match['p'] < 0.00001
    
