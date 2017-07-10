"""
Test Generate RDF from Assocs
"""
from ontobio.io.gafparser import GafParser
from ontobio.rdfgen.assoc_rdfgen import SimpleAssocRdfTransform, CamRdfTransform
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory

POMBASE = "tests/resources/truncated-pombase.gaf"
ONT = "tests/resources/go-truncated-pombase.json"

def test_parse():
    ont = OntologyFactory().create(ONT)
    p = GafParser()
    assocs = p.parse(open(POMBASE,"r"))
    gen(assocs,SimpleAssocRdfTransform(),'simple')
    gen(assocs,CamRdfTransform(),'cam')

def gen(assocs, tr, n):
    fn = 'tests/resources/{}.rdf'.format(n)
    tr.emit_header()
    for a in assocs:
        tr.translate(a)
    tr.writer.serialize(fn, 'ntriples')
