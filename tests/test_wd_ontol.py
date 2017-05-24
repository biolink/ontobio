from ontobio.ontol_factory import OntologyFactory
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.assocmodel import AssociationSet
from ontobio.sparql.wikidata_ontology import EagerWikidataOntology
import ontobio.sparql.wikidata as wd
import logging

PTSD = 'DOID:2055'

def test_wd_sparql_ptsd():
    """
    test using PTSD
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
