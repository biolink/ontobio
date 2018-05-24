from ontobio.ontol_factory import OntologyFactory

def test_obo_read():
    ont = OntologyFactory().create("tests/resources/goslim_pombe.obo")

    assert len(ont.graph) == 54