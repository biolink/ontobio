import pytest

from ontobio import ontol
from ontobio import ontol_factory

def test_missing_node_is_none():
    ontology = ontol_factory.OntologyFactory().create("tests/resources/goslim_generic.json")
    
    assert ontology.node("GO:0") == None
