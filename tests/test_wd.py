from ontobio.ontol_factory import OntologyFactory
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.assocmodel import AssociationSet
import ontobio.sparql.wikidata as wd
import logging

PTSD = 'DOID:2055'

def test_wd_sparql_ptsd():
    """
    TODO

    test using PTSD
    """
    xrefs = wd.fetchall_xrefs('HP')
    print("XRs: {}".format(list(xrefs.items())[:10]))
    [doid] = wd.map_id(PTSD, 'DOID')
    genes = wd.fetchall_sp(doid, 'genetic_association')
    logging.info("GENES: {}".format(genes))
    proteins = wd.canned_query('disease2protein', doid)
    logging.info("PROTEINS: {}".format(proteins))

    for p in proteins:
        print(p)
    
    ofactory = OntologyFactory()
    afactory = AssociationSetFactory()
    ont = ofactory.create('go')
    aset = afactory.create(ontology=ont,
                           subject_category='protein',
                           object_category='function',
                           taxon='NCBITaxon:9606')

    
    
    rs = aset.enrichment_test(proteins, threshold=1e-2, labels=True, direction='less')
    for r in rs:
        print("UNDER: "+str(r))

    for p in proteins:
        print("{} {}".format(p, aset.label(p)))
        for t in aset.annotations(p):
            print("  {} {}".format(t,ont.label(t)))
        
