"""
Tests for ontobio.golr.golr_associations
"""
from ontobio.golr.golr_associations import search_associations, search_associations_compact, select_distinct_subjects, get_objects_for_subject, get_subjects_for_object


HUMAN_SHH = 'HGNC:10848'
HOLOPROSENCEPHALY = 'HP:0001360'
TWIST_ZFIN = 'ZFIN:ZDB-GENE-050417-357'
DVPF = 'GO:0009953'
LSD = 'DOID:9455'
DANIO = 'NCBITaxon:7954'

def test_select_distinct():
    """
    Find distinct genes
    """
    results = select_distinct_subjects(subject_category='gene',
                                       object_category='phenotype',
                                       subject_taxon='NCBITaxon:9606')
    print("DISTINCT SUBJECTS={}".format(results))
    assert len(results) > 0

def test_go_assocs():
    """
    Test basic association search functionality
    """
    payload = search_associations(subject=TWIST_ZFIN,
                                  object_category='function'
    )
    assocs = payload['associations']
    assert len(assocs) > 0

def test_go_assocs_negated():
    """
    Test NOT is handled correctly
    """
    payload = search_associations(subject='MGI:1332638',
                                  object='GO:0005730',
                                  object_category='function'
    )
    assocs = payload['associations']
    assert len(assocs) > 0
    # we expect at least one of these to be negative
    neg_assocs = [a for a in assocs if a['negated']]
    assert len(neg_assocs) > 0
    # we also place NOT as a qualifier
    neg_assocs2 = [a for a in assocs if 'not' in a['qualifiers']]
    assert len(neg_assocs2) > 0
    
def test_go_assocs_compact():
    assocs = search_associations_compact(subject=TWIST_ZFIN,
                                          object_category='function'
    )
    assert len(assocs) == 1
    a = assocs[0]
    assert a['subject'] == TWIST_ZFIN
    objs = a['objects']
    assert 'GO:0002040' in objs

    # test reciprocal query
    for obj in objs:
        print("TEST FOR {}".format(obj))
        rassocs = search_associations_compact(object=obj,
                                              ##subject_category='gene',   # this is sometimes gene_product, protein.. in GO
                                              object_category='function',
                                              subject_taxon=DANIO,
                                              rows=-1)
        for a in rassocs:
            print("  QUERY FOR {} -> {}".format(obj,a))
        m = [a for a in rassocs if a['subject'] == TWIST_ZFIN]
        assert len(m) == 1
    
    
def test_pheno_assocs():
    payload = search_associations(subject=TWIST_ZFIN,
                                  object_category='phenotype'
    )
    assocs = payload['associations']
    assert len(assocs) > 0
    for a in assocs:
        print(str(a))
    assocs = [a for a in assocs if a['subject']['id'] == TWIST_ZFIN]
    assert len(assocs) > 0

def test_pheno_assocs_compact():
    assocs = search_associations_compact(subject=TWIST_ZFIN,
                                         rows=1000,
                                         object_category='phenotype'
    )
    assert len(assocs) == 1
    a = assocs[0]
    assert a['subject'] == TWIST_ZFIN
    assert 'ZP:0007631' in a['objects']
    
def test_pheno_objects():
    results = search_associations(subject=TWIST_ZFIN,
                                  fetch_objects=True,
                                  rows=0,
                                  object_category='phenotype'
    )
    objs = results['objects']
    print(str(objs))
    assert len(objs) > 1
    assert 'ZP:0007631' in objs
    
def test_func_objects():
    results = search_associations(subject=TWIST_ZFIN,
                                  fetch_objects=True,
                                  rows=0,
                                  object_category='function'
    )
    objs = results['objects']
    print(objs)
    assert DVPF in objs
    assert len(objs) > 1
    
def test_pheno_objects_shh_2():
    """
    Equivalent to above, using convenience method
    """
    objs = get_objects_for_subject(subject=HUMAN_SHH,
                                   object_category='phenotype')
    print(objs)
    assert HOLOPROSENCEPHALY in objs
    assert len(objs) > 50

def test_pheno2gene():
    """
    given a phenotype term, find genes
    """
    subjs = get_subjects_for_object(object=HOLOPROSENCEPHALY,
                                    subject_category='gene',
                                    subject_taxon='NCBITaxon:9606')
    print(subjs)
    print(len(subjs))
    assert HUMAN_SHH in subjs
    assert len(subjs) > 50
    
def test_disease_assocs():
    payload = search_associations(subject=HUMAN_SHH,
                                  object_category='disease'
    )
    print(str(payload))
    assocs = payload['associations']
    assert len(assocs) > 0

def test_disease2gene():
    payload = search_associations(subject=LSD,
                                  subject_category='disease',
                                  object_category='gene')
    assocs = payload['associations']
    for a in assocs:
        print(str(a))
    assert len(assocs) > 0
 
def test_species_facet():
    payload = search_associations(subject_category='gene',
                                  object_category='phenotype',
                                  facet_fields=['subject_taxon', 'subject_taxon_label'],
                                  rows=0)
    fcs = payload['facet_counts']
    print(str(fcs))
    assert 'Homo sapiens' in fcs['subject_taxon_label'].keys()
   
    
