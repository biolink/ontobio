from ontobio.ontol_factory import OntologyFactory
from ontobio.ontol import Synonym
from ontobio.lexmap import LexicalMapEngine
import networkx as nx
import logging

def test_lexmap_basic():
    """
    Text lexical mapping
    """
    factory = OntologyFactory()
    print("Creating ont")
    ont = factory.create('tests/resources/lexmap_test.json')
    lexmap = LexicalMapEngine()
    lexmap.index_ontology(ont)

    
    print(lexmap.lmap)
    print(ont.all_synonyms())
    g = lexmap.get_xref_graph()
    for x,y,d in g.edges_iter(data=True):
        print("{}<->{} :: {}".format(x,y,d))
    for x in g.nodes():
        print("{} --> {}".format(x,lexmap.grouped_mappings(x)))
    assert g.has_edge('Z:2','ZZ:2') # roman numerals
    assert g.has_edge('Z:2','Y:2')  # case insensitivity
    assert g.has_edge('A:1','B:1')  # synonyms
    assert g.has_edge('B:1','A:1')  # bidirectional
    for x,y,d in g.edges_iter(data=True):
        print("{}<->{} :: {}".format(x,y,d))
        cpr = d[lexmap.CONDITIONAL_PR]
        assert cpr > 0 and cpr <= 1.0

    lexmap = LexicalMapEngine(config=dict(normalized_form_confidence=0.25,
                                          meaningful_ids=True,
                                          ontology_configurations=[dict(prefix='AA',
                                                                        normalized_form_confidence=0)]))

    ont.add_node('TEST:1', 'foo bar')
    ont.add_node('TEST:2', 'bar foo')
    ont.add_node('TEST:3', 'foo bar')
    ont.add_node('TEST:4', 'wiz')
    syn = Synonym('TEST:4', val='bar foo', pred='hasRelatedSynonym')
    ont.add_synonym(syn)
    ont.add_node('http://x.org/wiz#FooBar')
    ont.add_node('TEST:6', '123')
    ont.add_node('TEST:7', '123')
    ont.add_node('AA:1', 'foo bar')
    ont.add_node('AA:2', 'bar foo')
    for s in ont.synonyms('TEST:4'):
        print('S={}'.format(s))
    lexmap.index_ontology(ont)
    g = lexmap.get_xref_graph()
    for x,d in g['TEST:1'].items():
        print('XREF: {} = {}'.format(x,d))
    assert g.has_edge('TEST:1','TEST:2') # normalized
    assert int(g['TEST:1']['TEST:2']['score']) == 25
    assert int(g['TEST:1']['TEST:3']['score']) == 100
    assert int(g['TEST:1']['TEST:4']['score']) < 25
    assert g.has_edge('TEST:3','http://x.org/wiz#FooBar')  # IDs and CamelCase
    assert not g.has_edge('TEST:6','TEST:7') # should omit syns with no alphanumeric

    # test exclude normalized form
    assert not g.has_edge('AA:1','AA:2')
    
def test_lexmap_multi():
    """
    Text lexical mapping
    """
    factory = OntologyFactory()
    print("Creating ont")
    files = ['x','m','h','bto']
    onts = [factory.create('tests/resources/autopod-{}.json'.format(f)) for f in files]
    lexmap = LexicalMapEngine()
    lexmap.index_ontologies(onts)
    #print(lexmap.lmap)
    #print(ont.all_synonyms())
    g = lexmap.get_xref_graph()
    for x in g.nodes():
        print("{} --> {}".format(x,lexmap.grouped_mappings(x)))
    for x,y,d in g.edges_iter(data=True):
        cl = nx.ancestors(g,x)
        print("{} '{}' <-> {} '{}' :: {} CLOSURE={}".format(x,lexmap.label(x),y,lexmap.label(y),d,len(cl)))
        cpr = d[lexmap.CONDITIONAL_PR]
        assert cpr > 0 and cpr <= 1.0
    unmapped = lexmap.unmapped_nodes(g)
    print('U: {}'.format(len(unmapped)))
    unmapped = lexmap.unmapped_nodes(g, rs_threshold=4)
    print('U4: {}'.format(len(unmapped)))

    cliques = lexmap.cliques(g)
    maxc = max(cliques, key=len)
    print('CLIQUES: {}'.format(cliques))
    print('MAX CLIQUES: {}'.format(maxc))
    df = lexmap.as_dataframe(g)
    print(df.to_csv(sep="\t"))
