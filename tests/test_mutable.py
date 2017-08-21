from ontobio import Ontology, Synonym
from ontobio import GraphRenderer

def test_mutable():
    """
    Test mutability of ontology class
    """
    ont = Ontology()
    ont.add_node('TEST:1', 'foo bar')
    ont.add_node('TEST:2', 'bar foo')
    ont.add_node('TEST:3', 'foo bar')
    ont.add_node('TEST:4', 'wiz')
    syn = Synonym('TEST:4', val='bar foo', pred='hasExactSynonym')
    ont.add_synonym(syn)
    w = GraphRenderer.create('obo')
    w.write(ont)
    for n in ont.nodes():
        meta = ont._meta(n)
        print('{} -> {}'.format(n,meta))

    assert ont.label('TEST:1') == 'foo bar'
    assert ont.synonyms('TEST:1') == []
    assert ont.synonyms('TEST:4')[0].val == 'bar foo'
