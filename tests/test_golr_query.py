from ontobio.golr.golr_query import GolrAssociationQuery


HUMAN_SHH = 'NCBIGene:6469'
HOLOPROSENCEPHALY = 'HP:0001360'
TWIST_ZFIN = 'ZFIN:ZDB-GENE-050417-357'
DVPF = 'GO:0009953'

    
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
    print("Q={}".format(q))
    print("Q.subject={}".format(q.subject))
    print("Q.evidec={}".format(q.evidence))
    params = q.solr_params()
    print("PARAMS={}".format(params))
    results = q.exec()
    print("RES={}".format(results))
    assert len(results) > 0
    
