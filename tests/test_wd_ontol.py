from ontobio.ontol_factory import OntologyFactory
from ontobio.sparql.wikidata_ontology import EagerWikidataOntology
import ontobio.sparql.wikidata as wd
import logging

PTSD = 'DOID:2055'

def test_wd_ontol_eager():
    """
    test Eager implementation
    """
    xrefs = wd.fetchall_xrefs('HP')
    print("XRs: {}".format(list(xrefs.items())[:10]))
    [doid] = wd.map_id(PTSD, 'DOID')
    logging.info("ID={}".format(doid))
    ont = EagerWikidataOntology('wdq:'+doid)
    logging.info("ONT={}".format(ont))
    for n in ont.nodes():
        logging.info("N={}".format(n))
        logging.info("N={} {}".format(n, ont.label(n)))
        for a in ont.ancestors(n):
            logging.info("A={} {}".format(a, ont.label(a)))        

def test_factory():
    """
    test ontology factory using wikidata as source and using PTSD.

    """
    f = OntologyFactory()
    ont = f.create('wdq:Q544006')
    for n in ont.nodes():
        print('{} "{}"'.format(n,ont.label(n)))
    qids = ont.search('anxiety%')
    assert len(qids) > 0
    print(qids)
    nodes = ont.traverse_nodes(qids, up=True, down=True)
    print(nodes)
    assert len(nodes) > 0
    labels = [ont.label(n) for n in nodes]
    print(labels)
    # Note: it's possible wd may change rendering this false
    assert 'Fear of frogs' in labels
    from ontobio.io.ontol_renderers import GraphRenderer
    w = GraphRenderer.create('tree')
    w.write(ont, query_ids=qids)

            
