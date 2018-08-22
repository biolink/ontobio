from ontobio.ontol_factory import OntologyFactory
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.assocmodel import AssociationSet
from ontobio.io.gafparser import GafParser
import logging
import random

NUCLEUS = 'GO:0005634'
CYTOPLASM = 'GO:0005737'
MITO = 'GO:0005739'
MOUSE = 'NCBITaxon:10090'
TRANSCRIPTION_FACTOR = 'GO:0003700'
TRANSPORTER = 'GO:0005215'
PART_OF = 'BFO:0000050'


def test_remote_go():
    """
    factory test
    """
    ofactory = OntologyFactory()
    afactory = AssociationSetFactory()
    ont = ofactory.create('go').subontology(relations=['subClassOf', PART_OF])
    aset = afactory.create(ontology=ont,
                           subject_category='gene',
                           object_category='function',
                           taxon=MOUSE)

    rs = aset.query([TRANSCRIPTION_FACTOR],[])
    print("Mouse genes annotated to TF: {} {}".format(rs, len(rs)))
    for g in rs:
        print("  Gene: {} {}".format(g,aset.label(g)))
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

HUMAN='NCBITaxon:9606'
PD = 'DOID:14330'

def test_remote_disease():
    """
    factory test
    """
    ofactory = OntologyFactory()
    afactory = AssociationSetFactory()
    ont = ofactory.create('doid')
    aset = afactory.create(ontology=ont,
                           subject_category='disease',
                           object_category='phenotype',
                           taxon=HUMAN)

    rs = aset.query_associations([PD])
    print("Gene Assocs to PD: {} {}".format(rs, len(rs)))


POMBASE = "tests/resources/truncated-pombase.gaf"
INTRACELLULAR='GO:0005622'
G1 = 'PomBase:SPBC902.04'
def test_gaf():
    """
    Test loading from gaf
    """
    ofactory = OntologyFactory()
    afactory = AssociationSetFactory()
    ont = ofactory.create('go')
    aset = afactory.create_from_gaf(open(POMBASE,"r"),
                                    ontology=ont)
    print(str(aset))
    genes = aset.query([INTRACELLULAR])
    for g in genes:
        print("G={} '{}'".format(g, aset.label(g)))
    assert G1 in genes

def test_create_from_file_no_fmt():
    """
    Test loading from gaf while setting fmt to None
    """
    ont = OntologyFactory().create('go')
    f = AssociationSetFactory()
    aset = f.create(ontology=ont, fmt=None, file=POMBASE)
    print("SUBJS: {}".format(aset.subjects))
    assert len(aset.subjects) > 100


def test_remote_go_pombase():
    ont = OntologyFactory().create('go')
    f = AssociationSetFactory()
    aset = f.create(ontology=ont, fmt='gaf', file=POMBASE)
    print("SUBJS: {}".format(aset.subjects))
    assert len(aset.subjects) > 100
