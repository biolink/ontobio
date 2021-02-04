import pytest

from ontobio import ontol
from ontobio import ontol_factory

def test_missing_node_is_none():
    ontology = ontol_factory.OntologyFactory().create("tests/resources/goslim_generic.json")

    assert ontology.node("GO:0") == None

def test_merge_copies_logical_definitions():
    pombe_ontology = ontol_factory.OntologyFactory().create("tests/resources/goslim_pombe.json")
    assert len(pombe_ontology.all_logical_definitions) == 0
    nucleus_ontology = ontol_factory.OntologyFactory().create("tests/resources/nucleus.json")
    assert len(nucleus_ontology.all_logical_definitions) == 2
    # Test logical definition copy in merge
    pombe_ontology.merge([nucleus_ontology])
    assert len(pombe_ontology.all_property_chain_axioms) == 2

def test_merge_copies_property_chain_axioms():
    nucleus_ontology = ontol_factory.OntologyFactory().create("tests/resources/nucleus.json")
    assert len(nucleus_ontology.all_property_chain_axioms) == 0
    goslim_ontology = ontol_factory.OntologyFactory().create("tests/resources/goslim_generic.json")
    assert len(goslim_ontology.all_property_chain_axioms) == 2
    # Test property chain axiom copy in merge
    nucleus_ontology.merge([goslim_ontology])
    assert len(nucleus_ontology.all_property_chain_axioms) == 2

def test_ontology_synonyms():
    ontology = ontol_factory.OntologyFactory().create("tests/resources/nucleus_new.json")
    syn = ontology.synonyms("GO:0005634")

    assert syn[0].__dict__ == ontol.Synonym("GO:0005634", val="cell nucleus", pred="hasExactSynonym", lextype=None,
                        xrefs=[], ontology=None, confidence=1.0, synonymType="http://purl.obolibrary.org/obo/go-test#systematic_synonym").__dict__
