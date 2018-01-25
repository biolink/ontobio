"""
Test Generate RDF from Assocs
"""
from ontobio.io.gafparser import GafParser
from ontobio.rdfgen.assoc_rdfgen import SimpleAssocRdfTransform, CamRdfTransform, TurtleRdfWriter
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory

POMBASE = "tests/resources/truncated-pombase.gaf"
ONT = "tests/resources/go-truncated-pombase.json"

def test_parse():
    ont = OntologyFactory().create(ONT)
    p = GafParser()
    assocs = p.parse(open(POMBASE,"r"))
    #gen(assocs,SimpleAssocRdfTransform(),'simple')
    rdf_writer = TurtleRdfWriter()
    gen(assocs,CamRdfTransform(writer=rdf_writer),'cam',rdf_writer)

def gen(assocs, tr, n, rdf_writer):
    fn = 'tests/resources/{}.rdf'.format(n)
    tr.emit_header()
    print("Writing {} assocs".format(len(assocs)))
    for a in assocs:
        tr.translate(a)
    print("Serializing {} assocs".format(len(assocs)))
    rdf_writer.serialize(destination=open(fn,'w'))
    #tr.writer.serialize(fn, 'ntriples')
