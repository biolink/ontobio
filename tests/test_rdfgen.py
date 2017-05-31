"""
Test Generate RDF from Assocs
"""
from ontobio.io.gafparser import GafParser
from ontobio.rdfgen.assoc_rdfgen import SimpleAssocGenerator,CamGenerator
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory

POMBASE = "tests/resources/truncated-pombase.gaf"
ONT = "tests/resources/go-truncated-pombase.json"

def test_parse():
    ont = OntologyFactory().create(ONT)
    p = GafParser()
    assocs = p.parse(open(POMBASE,"r"))
    gen1 = SimpleAssocGenerator()
    gen2 = CamGenerator()
    for a in assocs:
        gen1.translate(a)
        #gen2.translate(a)
