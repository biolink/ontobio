from ontobio.io.hpoaparser import HpoaParser
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory

ANNFILE = "tests/resources/truncated.hpoa"
ONT = "tests/resources/hp-truncated-hpoa.json"


def test_factory():
    ont = OntologyFactory().create(ONT)
    f = AssociationSetFactory()
    aset = f.create(ontology=ont, fmt='hpoa', file=ANNFILE)
    print("SUBJS: {}".format(aset.subjects))
    assert len(aset.subjects) > 40


def test_skim():
    p = HpoaParser()
    results = p.skim(open(ANNFILE,"r"))
    for r in results:
        print(str(r))
        (s,sn,o) = r
        assert o.startswith('HP:')
        assert s.startswith('DECIPHER:') or s.startswith('OMIM:') or s.startswith('ORPHANET:')


def test_parse_hpoa():
    p = HpoaParser()
    f = ANNFILE
    ont = OntologyFactory().create(ONT)
    results = p.parse(open(f, "r"))
    r1 = results[0]
    assert r1['evidence']['type'] == 'IEA'
    #assert r1['evidence']['has_supporting_reference'] == ['GO_REF:0000024']

    assert r1['object']['id'] == 'HP:0000252'
    assert r1['subject']['id'] == 'DECIPHER:1'
    assert r1['subject']['label'] == 'WOLF-HIRSCHHORN SYNDROME'
    for r in results:
        #print(str(r))
        sid = r['subject']['id']
        prov = r['provided_by']
        #assert prov == 'ANNFILE' or prov == 'UniProt'
        assert r['object']['id'].startswith('HP:')
        assert r['subject']['taxon']['id'] =='NCBITaxon:9606'

    for m in p.report.messages:
        print("MESSAGE: {}".format(m))
    assert len(p.report.messages) == 0
    print(p.report.to_markdown())


def test_validate_hp_idspaces():
    ont = OntologyFactory().create(ONT)
    p = HpoaParser()
    p.config.class_idspaces = ['FOOZ']
    assocs = p.parse(open(ANNFILE, "r"))
    for m in p.report.messages:
        print("MESSAGE: {}".format(m))

    assert len(assocs) == 0
    assert len(p.report.messages) > 1
    summary = p.report.to_report_json()
    assert summary['associations'] == 0
    assert summary['lines'] > 300
    print(p.report.to_markdown())

    p = HpoaParser()
    p.config.class_idspaces = ['HP']
    assocs = p.parse(open(ANNFILE, "r"))
    assert len(assocs) > 0
