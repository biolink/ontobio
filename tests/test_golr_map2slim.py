from ontobio.golr.golr_associations import map2slim, GolrFields

M=GolrFields()

HUMAN_SHH = 'NCBIGene:6469'
HOLOPROSENCEPHALY = 'HP:0001360'
TWIST_ZFIN = 'ZFIN:ZDB-GENE-050417-357'
DVPF = 'GO:0009953'
SUBJECTS = [TWIST_ZFIN,'ZFIN:ZDB-GENE-040426-1432']

def test_map2slim():
    results = map2slim(subjects=SUBJECTS,
                       slim=['GO:0001525','GO:0048731','GO:0005634','GO:0005794'],
                       object_category='function')

    assert len(results) > 0
    n_found = 0
    for r in results:
        n_found = n_found+1
        print("Subject: {} Slim:{} Assocs:{}".format(r['subject'],r['slim'],len(r['assocs'])))
    assert n_found > 0


    
