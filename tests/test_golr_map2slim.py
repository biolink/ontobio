from ontobio.ontol_factory import OntologyFactory
from ontobio.golr.golr_associations import search_associations, GolrFields, map2slim

M=GolrFields()

HUMAN_SHH = 'NCBIGene:6469'
HOLOPROSENCEPHALY = 'HP:0001360'
TWIST_ZFIN = 'ZFIN:ZDB-GENE-050417-357'
DVPF = 'GO:0009953'
SUBJECTS = [TWIST_ZFIN,'ZFIN:ZDB-GENE-040426-1432']
SLIM = ['GO:0001525','GO:0048731','GO:0005634','GO:0005794']

def test_map2slim_golr():
    results = map2slim(subjects=SUBJECTS,
                       slim=SLIM,
                       object_category='function')

    assert len(results) > 0
    n_found = 0
    for r in results:
        n_found = n_found+1
        print("Subject: {} Slim:{} Assocs:{}".format(r['subject'],r['slim'],len(r['assocs'])))
    assert n_found > 0

#def test_map2slim_ont():
#    ont = OntologyFactory().create('go')
#    relations=['subClassOf', 'BFO:0000050']
#    m = ont.create_slim_mapping(subset_nodes=SLIM, relations=relations)
#    print(str(m))
#    assert m['GO:0005798'] == ['GO:0005794']
#
#    searchresult = search_associations(subjects=SUBJECTS,
#                                       object_category='function')
#
#    ok = False
#    for a in searchresult['associations']:
#        gene = a['subject']['id']
#        cid = a['object']['id']
#        mcids = m.get(cid)
#        ## e.g. ZFIN:ZDB-GENE-050417-357 : GO:0060037 -> ['GO:0048731']
#        print("{} : {} -> {}".format(gene, cid, mcids))
#        if gene == 'ZFIN:ZDB-GENE-050417-357' and mcids == ['GO:0048731']:
#            ok = True
#    assert ok
