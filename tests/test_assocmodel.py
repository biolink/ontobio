from ontobio.ontol_factory import OntologyFactory
from ontobio.assocmodel import AssociationSet
import logging
import random

QUALITY = 'PATO:0000001'
PLOIDY = 'PATO:0001374'
EUPLOID = 'PATO:0001393'
SHAPE = 'PATO:0000052'
Y_SHAPED = 'PATO:0001201'

def test_assoc_query():
    """
    reconstitution test
    """
    print("Making ont factory")
    factory = OntologyFactory()
    # default method is sparql
    print("Creating ont")
    ont = factory.create('pato')
    print("Creating assoc set")
    aset = AssociationSet(ontology=ont,
                        association_map={
                            'a': [],
                            'b': [EUPLOID],
                            'c': [Y_SHAPED],
                            'd': [EUPLOID, Y_SHAPED],
                        })

    rs = aset.query([],[])
    assert len(rs) == 4
    
    rs = aset.query([EUPLOID],[])
    assert len(rs) == 2
    assert 'b' in rs
    assert 'd' in rs

    rs = aset.query([EUPLOID, Y_SHAPED],[])
    assert len(rs) == 1
    assert 'd' in rs

    rs = aset.query([PLOIDY, SHAPE],[])
    assert len(rs) == 1
    assert 'd' in rs
    
    rs = aset.query([],[PLOIDY, SHAPE])
    assert len(rs) == 1
    assert 'a' in rs

    rs = aset.query([PLOIDY], [SHAPE])
    assert len(rs) == 1
    assert 'b' in rs

    rs = aset.query([EUPLOID], [Y_SHAPED])
    assert len(rs) == 1
    assert 'b' in rs

    rs = aset.query([EUPLOID], [PLOIDY])
    assert len(rs) == 0

    rs = aset.query([PLOIDY], [EUPLOID])
    assert len(rs) == 0

    rs = aset.query([QUALITY], [PLOIDY])
    assert len(rs) == 1
    assert 'c' in rs    

    rs = aset.query([SHAPE], [QUALITY])
    assert len(rs) == 0

    rs = aset.query([QUALITY], [QUALITY])
    assert len(rs) == 0

    for s1 in aset.subjects:
        for s2 in aset.subjects:
            sim = aset.jaccard_similarity(s1,s2)
            print("{} vs {} = {}".format(s1,s2,sim))
            if s1 == 'a' or s2 == 'a':
                assert sim == 0.0
            elif s1 == s2:
                assert sim == 1.0
            else:
                assert sim == aset.jaccard_similarity(s2,s1)

    terms1 = [QUALITY,PLOIDY,SHAPE]
    terms2 = [QUALITY,EUPLOID,Y_SHAPED]
    ilist = aset.query_intersections(terms1, terms2)
    print(str(ilist))

def test_enrichment():
    """
    enrichment
    """
    factory = OntologyFactory()
    ont = factory.create('pato')

    # gene set 'a' is biased to ploidy
    termprobs = [(QUALITY,0.8,0.8),
                 (PLOIDY,0.8,0.2),
                 (EUPLOID,0.7,0.01),
                 (SHAPE,0.2,0.75),
                 (Y_SHAPED,0.01,0.5)
    ]
    amap = {}
    geneset_a = []
    geneset_b = []
    for x in range(1,100):
        for y in ['a','b']:
            dts = []
            for (t,p1,p2) in termprobs:
                if y=='a':
                    p = p1
                else:
                    p = p2
                if random.random() < p:
                    dts.append(t)
            g = y + str(x)
            if y == 'a':
                geneset_a.append(g)
            else:
                geneset_b.append(g)
            amap[g] = dts
    logging.info(str(amap))
    aset = AssociationSet(ontology=ont,
                          association_map=amap)
    logging.info(str(aset))
    print(str(geneset_a))
    results = aset.enrichment_test(geneset_a, labels=True)
    print(str(results))
    print("EXPECTED: {} {}".format(PLOIDY, EUPLOID))
    results = aset.enrichment_test(geneset_b, labels=True)
    print(str(results))
    print("EXPECTED: {} {}".format(SHAPE, Y_SHAPED))
    
logging.basicConfig(level=logging.DEBUG)
test_enrichment()
