import pytest

from ontobio import ontol
from ontobio import ontol_factory

def test_missing_node_is_none():
    ontology = ontol_factory.OntologyFactory().create("tests/resources/goslim_generic.json")

    assert ontology.node("GO:0") == None

def test_ontology_synonyms():
    ontology = ontol_factory.OntologyFactory().create("tests/resources/nucleus_new.json")
    syn = ontology.synonyms("GO:0005634")

    assert syn[0].__dict__ == ontol.Synonym("GO:0005634", val="cell nucleus", pred="hasExactSynonym", lextype=None,
                        xrefs=[], ontology=None, confidence=1.0, synonymType="http://purl.obolibrary.org/obo/go-test#systematic_synonym").__dict__
