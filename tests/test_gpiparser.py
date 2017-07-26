from ontobio.io.entityparser import GpiParser
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory

ONT = "tests/resources/go-truncated-pombase.json"
GPI = "tests/resources/truncated-mgi.gpi"

def test_parse_gpi():
    ont = OntologyFactory().create(ONT)
    p = GpiParser()
    p.config.remove_double_prefixes = True
    results = p.parse(open(GPI,"r"))
    for r in results:
        print(r)
    r1 = results[0]
    assert r1['label'] == 'a'
    assert r1['taxon']['id'] == 'NCBITaxon:10090'
    assert r1['full_name'] == 'nonagouti'
    assert r1['xrefs'] == ['UniProtKB:Q03288']
    assert r1['parents'] == []

    r2 = results[-1]
    assert r2['parents'] == ['MGI:109279']


    for m in p.report.messages:
        print("MESSAGE: {}".format(m))
    assert len(p.report.messages) == 0
    print(p.report.to_markdown())

def test_gpi_skips_lines_with_incorrect_collumns():
    parser = GpiParser()
    parsed = parser.parse_line("hello\tworld\tfoo\tbar")

    assert parsed[1] == []
