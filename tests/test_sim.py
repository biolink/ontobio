from ontobio.ontol_factory import OntologyFactory
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.assocmodel import AssociationSet
from ontobio.io.gafparser import GafParser
from ontobio.sim import SimEngine
import logging
import random



POMBASE = "tests/resources/truncated-pombase.gaf"
INTRACELLULAR='GO:0005622'
G1 = 'PomBase:SPBC902.04'
def test_sim():
    """
    Test loading from gaf
    """
    ofactory = OntologyFactory()
    afactory = AssociationSetFactory()
    ont = ofactory.create('tests/resources/go-truncated-pombase.json')
    aset = afactory.create_from_gaf(open(POMBASE,"r"),
                                    ontology=ont)

    sim = SimEngine(aset)
    for g1 in aset.subjects:
        print("G1={} '{}'".format(g1, aset.label(g1)))
        for g2 in aset.subjects:
            print("  G2={} '{}'".format(g2, aset.label(g2)))
            jsim = sim.entity_jaccard_similarity(g1,g2)
            print("    SIM={}".format(jsim))

    

    
