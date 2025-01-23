from ontobio.golr.golr_query import GolrAssociationQuery, GolrSearchQuery
import logging

HUMAN_SHH = 'NCBIGene:6469'
HOLOPROSENCEPHALY = 'HP:0001360'
TWIST_ZFIN = 'ZFIN:ZDB-GENE-050417-357'
DVPF = 'GO:0009953'
DANIO_RERIO = 'NCBITaxon:7955'

    
def test_pheno_assocs():
    q = GolrAssociationQuery(subject=TWIST_ZFIN,
                  object_category='phenotype')
    print("Q={}".format(q))
    print("Q.subject={}".format(q.subject))
    print("Q.evidec={}".format(q.evidence))
    params = q.solr_params()
    print("PARAMS={}".format(params))
    results = q.exec()
    print("RES={}".format(results))
    assert len(results) > 0


def test_go_assocs():
    q = GolrAssociationQuery(subject=TWIST_ZFIN,
                  object_category='function')
    print(f"Q={q}")
    print(f"Q.subject={q.subject}")
    print(f"Q.evidec={q.evidence}")
    params = q.solr_params()
    print(f"PARAMS={params}")
    results = q.exec()
    print(f"RES={results}")
    fc = results['facet_counts']
    assert fc['taxon_label']['Danio rerio'] > 0

    assocs = results['associations']
    assert len(assocs) > 0
    assoc = assocs[0]
    print(f"ASSOC={assoc}")
    assert assoc['subject']['id'] == TWIST_ZFIN
    assert assoc['subject']['taxon']['id'] == DANIO_RERIO
    term_id = assoc['object']['id']
    ROWS = 100
    q = GolrAssociationQuery(
        object_taxon_direct=DANIO_RERIO,
        object_direct=term_id,
        object_category='function',
        rows = ROWS
    )
    found = False
    results = q.exec()['associations']
    for assoc in results:
        print(f"A={assoc}")
        if assoc['subject']['id'] == TWIST_ZFIN:
            found = True
    if not found:
        if results['numFound'] > ROWS:
            logging.error(f"Did not find twist in query for {term_id}")
            assert False
        else:
            logging.warning(f"Test may be incomplete, consider incremening ROWS")



