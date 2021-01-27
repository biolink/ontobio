from ontobio.rdfgen import relations
from ontobio.model import association

def test_relations_curie_expand():
    uri = relations.curie_to_obo_uri(association.Curie.from_str("GO:1234567"))
    assert uri == "http://purl.obolibrary.org/obo/GO_1234567"


def test_relations_curie_contract():
    curie = relations.obo_uri_to_curie("http://purl.obolibrary.org/obo/GO_1234567")
    assert curie == association.Curie(namespace="GO", identity="1234567")

