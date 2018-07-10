"""
Test Generate RDF from Assocs
"""
import rdflib
from rdflib.namespace import RDFS

from ontobio.io.gafparser import GafParser
from ontobio.rdfgen.assoc_rdfgen import TurtleRdfWriter, CamRdfTransform
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory

POMBASE = "tests/resources/truncated-pombase.gaf"
ONT = "tests/resources/go-truncated-pombase.json"

def test_parse():
    ont = OntologyFactory().create(ONT)
    p = GafParser()
    assocs = p.parse(open(POMBASE, "r"))
    #gen(assocs,SimpleAssocRdfTransform(),'simple')
    gen(assocs, CamRdfTransform(), 'cam')

def test_rdfgen_includes_taxon_in_subject():

    assoc = {
        'source_line': 'PomBase\tSPAC25B8.17\typf1\t\tGO:1990578\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:4896\t20150305\tPomBase\t\t',
        'subject': {
            'id': 'PomBase:SPAC25B8.17',
            'label': 'ypf1',
            'type': 'protein',
            'fullname': 'intramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)',
            'synonyms': ['ppp81'],
            'taxon': {'id': 'NCBITaxon:4896'}
        },
        'object': {
            'id': 'GO:1990578',
            'taxon': 'NCBITaxon:4896'
        },
        'negated': False,
        'qualifiers': [],
        'aspect': 'C',
        'relation': {'id': 'part_of'},
        'evidence': {
            'type': 'ISO',
            'has_supporting_reference': ['GO_REF:0000024'],
            'with_support_from': ['SGD:S000001583']
        },
        'provided_by': 'PomBase',
        'date': '20150305'
    }


    gaf_transformer = CamRdfTransform()
    gaf_transformer.translate(assoc)

    graph = gaf_transformer.writer.graph
    assert (rdflib.URIRef("http://identifiers.org/pombase/SPAC25B8.17"),
            rdflib.URIRef("http://purl.obolibrary.org/obo/RO_0002162"),
            rdflib.URIRef("http://purl.obolibrary.org/obo/NCBITaxon_4896")) in graph

    assert (rdflib.URIRef("http://identifiers.org/pombase/SPAC25B8.17"),
            RDFS.label,
            rdflib.Literal("ypf1")) in graph



def gen(assocs, tr, n):
    fn = 'tests/resources/{}.rdf'.format(n)
    tr.emit_header()
    for a in assocs:
        tr.translate(a)
    tr.writer.serialize(destination=open(fn,'wb'))
    #tr.writer.serialize(fn, 'ntriples')
