"""
Test Generate RDF from Assocs
"""
import rdflib
from rdflib.namespace import RDFS
from rdflib import compare

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

def test_rdfgen_includes_taxon_in_gp_class():

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

    rdfWriter = TurtleRdfWriter(label="pombase_single.ttl")
    gaf_transformer = CamRdfTransform(writer=rdfWriter)
    gaf_transformer.translate(assoc)
    gaf_transformer.provenance()

    gp_res = rdfWriter.graph.query(gene_product_class_query())
    for row in gp_res:
        assert str(row["cls"]) == "http://identifiers.org/pombase/SPAC25B8.17"
        assert str(row["taxon"]) == "http://purl.obolibrary.org/obo/NCBITaxon_4896"


def gene_product_class_query():
    return """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX NCBITaxon: <http://purl.obolibrary.org/obo/NCBITaxon_>
        PREFIX RO: <http://purl.obolibrary.org/obo/RO_>
        SELECT ?cls ?taxon
        WHERE {
            ?cls rdfs:subClassOf [ a owl:Restriction ;
                owl:onProperty RO:0002162 ;
                owl:someValuesFrom ?taxon ] .
        }
    """

def gen(assocs, tr, n):
    fn = 'tests/resources/{}.rdf'.format(n)
    tr.emit_header()
    for a in assocs:
        tr.translate(a)
    tr.writer.serialize(destination=open(fn,'wb'))
    #tr.writer.serialize(fn, 'ntriples')
