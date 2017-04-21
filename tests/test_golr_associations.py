from ontobio.golr.golr_associations import search_associations, search_associations_compact, GolrFields, select_distinct_subjects, get_objects_for_subject, get_subjects_for_object

M=GolrFields()

HUMAN_SHH = 'NCBIGene:6469'
HOLOPROSENCEPHALY = 'HP:0001360'
TWIST_ZFIN = 'ZFIN:ZDB-GENE-050417-357'
DVPF = 'GO:0009953'

def test_select_distinct():
    results = select_distinct_subjects(subject_category='gene',
                                       object_category='phenotype',
                                       subject_taxon='NCBITaxon:9606')
    assert len(results) > 0

def test_go_assocs():
    results = search_associations(subject=TWIST_ZFIN,
                                  object_category='function'
    )
    assert len(results) > 0

def test_go_assocs_compact():
    assocs = search_associations_compact(subject=TWIST_ZFIN,
                                          object_category='function'
    )
    assert len(assocs) == 1
    
    
def test_pheno_assocs():
    results = search_associations(subject=TWIST_ZFIN,
                                  object_category='phenotype'
    )
    assert len(results) > 0

def test_pheno_assocs_compact():
    assocs = search_associations_compact(subject=TWIST_ZFIN,
                                          object_category='phenotype'
    )
    assert len(assocs) == 1
    
def test_pheno_objects():
    results = search_associations(subject=TWIST_ZFIN,
                                  fetch_objects=True,
                                  rows=0,
                                  object_category='phenotype'
    )
    objs = results['objects']
    assert len(objs) > 1

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
    results = search_associations(subject=TWIST_ZFIN,
                                  object_category='disease'
    )
    assert len(results) > 0
    
