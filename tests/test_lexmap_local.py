from ontobio import OntologyFactory
from ontobio import Synonym, Ontology
from ontobio.lexmap import LexicalMapEngine
import networkx as nx
import logging

# TODO move this
def test_merge():
    factory = OntologyFactory()
    print("Creating ont")
    ont = factory.create('tests/resources/lexmap_test.json')
    ont2 = Ontology()
    ont2.merge([ont])
    assert ont2.xref_graph is not None

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
    for (x,y,d) in g.edges(data=True):
        print("{}<->{} :: {}".format(x,y,d))
    for x in g.nodes():
        print("{} --> {}".format(x,lexmap.grouped_mappings(x)))
    assert g.has_edge('Z:2','ZZ:2') # roman numerals
    assert g.has_edge('Z:2','Y:2')  # case insensitivity
    assert g.has_edge('A:1','B:1')  # synonyms
    assert g.has_edge('B:1','A:1')  # bidirectional
    for (x,y,d) in g.edges(data=True):
        print("{}<->{} :: {}".format(x,y,d))
        cpr = d[lexmap.CONDITIONAL_PR]
        assert cpr > 0 and cpr <= 1.0

    df = lexmap.as_dataframe(g)
    print(df.to_csv(sep="\t"))
        
    lexmap = LexicalMapEngine(config=dict(synsets=[dict(word="",
                                                        synonym="ignoreme",
                                                        weight=-2.0)],
                                          normalized_form_confidence=0.25,
                                          abbreviation_confidence=0.5,
                                          meaningful_ids=True,
                                          ontology_configurations=[dict(prefix='AA',
                                                                        normalized_form_confidence=-1000)]))

    assert len(lexmap._get_config_val('NULL','synsets')) == 1
    assert lexmap._normalize_label('ignoreme foo', {'ignoreme':''}) == 'foo'
    assert lexmap._normalize_label('replaceme foo', {'replaceme':'zz'}) == 'foo zz'
    
    ont.add_node('TEST:1', 'foo bar')
    ont.add_node('TEST:2', 'bar foo')
    ont.add_node('TEST:3', 'foo bar')
    ont.add_node('TEST:4', 'wiz')
    syn = Synonym('TEST:4', val='bar foo', pred='hasRelatedSynonym')
    ont.add_synonym(syn)
    ont.add_node('http://x.org/wiz#FooBar')
    ont.add_node('TEST:6', '123')
    ont.add_node('TEST:7', '123')
    ont.add_node('TEST:8', 'bar ignoreme foo')
    ont.add_node('AA:1', 'foo bar')
    ont.add_node('AA:2', 'bar foo')
    ont.add_node('ABBREV:1', 'ABCD')
    ont.add_node('ABBREV:2', 'ABCD')
    for s in ont.synonyms('TEST:4'):
        print('S={}'.format(s))
    lexmap.index_ontology(ont)
    g = lexmap.get_xref_graph()
    for x,d in g['TEST:1'].items():
        print('XREF: {} = {}'.format(x,d))
    assert g.has_edge('TEST:1','TEST:2') # normalized
    logging.info('E 1-2 = {}'.format(g['TEST:1']['TEST:2']))
    assert int(g['TEST:1']['TEST:2']['score']) == 25
    assert int(g['TEST:1']['TEST:3']['score']) == 100
    assert int(g['TEST:1']['TEST:4']['score']) < 25
    assert g.has_edge('TEST:3','http://x.org/wiz#FooBar')  # IDs and CamelCase
    assert not g.has_edge('TEST:6','TEST:7') # should omit syns with no alphanumeric

    # test exclude normalized form
    assert not g.has_edge('AA:1','AA:2')

    # test custom synsets are used
    assert g.has_edge('TEST:8','TEST:2')
    assert g.has_edge('TEST:8','AA:2')
    assert not g.has_edge('TEST:8','AA:1') # do not normalize AAs

    assert lexmap.smap['ABBREV:1'][0].is_abbreviation()
    assert lexmap.smap['ABBREV:2'][0].is_abbreviation()
    assert g.has_edge('ABBREV:1','ABBREV:2')
    assert int(g['ABBREV:1']['ABBREV:2']['score']) == 25
    
    df = lexmap.unmapped_dataframe(g)
    print(df.to_csv())
    
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
    for (x,y,d) in g.edges(data=True):
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

def test_awe_1_to_many_flat():
    """
    Text axiom weight estimation, for a 1-to-many situation, where the many are not inter-related
    """
    ont = Ontology()
    lexmap = LexicalMapEngine(config={'cardinality_weights': [
        {'prefix1':'X',
         'prefix2':'Y',
         'cardinality':'1m',
         'weights':[-1.0, 1.0, -2.0, 0.0]
         }
        ]})
    
    ont.add_node('X:1', 'foo 1')
    ont.add_node('Y:1a', 'foo 1a')
    ont.add_synonym(Synonym('Y:1a', val='foo 1', pred='hasRelatedSynonym'))
    ont.add_node('Y:1b', 'foo 1b')
    ont.add_synonym(Synonym('Y:1b', val='foo 1', pred='hasExactSynonym'))
    lexmap.index_ontology(ont)
    xg = lexmap.get_xref_graph()
    df = lexmap.as_dataframe(xg)
    print(df.to_csv(sep="\t"))
    P = lexmap.weighted_axioms('X:1','Y:1a', xg)
    logging.info('P={}'.format(P))
    assert P[0] < P[1]
    assert P[1] > P[2]

def test_awe_1_to_many_inverse():
    """
    As previous test, but checking to ensure directionality in config is reversed
    """
    ont = Ontology()
    lexmap = LexicalMapEngine(config={'cardinality_weights': [
        {'prefix1':'Y',
         'prefix2':'X',
         'cardinality':'m1',
         'weights':[1.0, -1.0, -2.0, 0.0]
         }
        ]})
    
    ont.add_node('X:1', 'foo 1')
    ont.add_node('Y:1a', 'foo 1a')
    ont.add_synonym(Synonym('Y:1a', val='foo 1', pred='hasRelatedSynonym'))
    ont.add_node('Y:1b', 'foo 1b')
    ont.add_synonym(Synonym('Y:1b', val='foo 1', pred='hasExactSynonym'))
    lexmap.index_ontology(ont)
    xg = lexmap.get_xref_graph()
    df = lexmap.as_dataframe(xg)
    print(df.to_csv(sep="\t"))
    P = lexmap.weighted_axioms('X:1','Y:1a', xg)
    logging.info('P={}'.format(P))
    assert P[0] < P[1]
    assert P[1] > P[2]

def test_awe_1_to_many_default():
    """
    As previous test, but with defaults
    """
    ont = Ontology()
    lexmap = LexicalMapEngine(config={'cardinality_weights': [
        {'cardinality':'m1',
         'weights':[1.0, -1.0, -2.0, 0.0]
         }
        ]})
    
    ont.add_node('X:1', 'foo 1')
    ont.add_node('Y:1a', 'foo 1a')
    ont.add_synonym(Synonym('Y:1a', val='foo 1', pred='hasRelatedSynonym'))
    ont.add_node('Y:1b', 'foo 1b')
    ont.add_synonym(Synonym('Y:1b', val='foo 1', pred='hasExactSynonym'))
    lexmap.index_ontology(ont)
    xg = lexmap.get_xref_graph()
    df = lexmap.as_dataframe(xg)
    print(df.to_csv(sep="\t"))
    P = lexmap.weighted_axioms('X:1','Y:1a', xg)
    logging.info('P={}'.format(P))
    assert P[0] < P[1]
    assert P[1] > P[2]

def test_awe_1_to_many_hier():
    """
    Text axiom weight estimation
    """
    ont = Ontology()
    assert isinstance(ont.nodes(), nx.classes.reportviews.NodeView)
    lexmap = LexicalMapEngine()
    
    ont.add_node('X:1', 'foo 1')
    ont.add_node('Z:1a', 'foo 1')
    ont.add_node('Z:1b', 'foo 1')
    ont.add_parent('Z:1b','Z:1a')
    
    lexmap.index_ontology(ont)
    xg = lexmap.get_xref_graph()
    df = lexmap.as_dataframe(xg)
    print(df.to_csv(sep="\t"))
    P_a = lexmap.weighted_axioms('X:1','Z:1a', xg)
    P_b = lexmap.weighted_axioms('X:1','Z:1b', xg)
    logging.info('P_a={} P_b={}'.format(P_a, P_b))
    assert P_a[0] > P_a[1]
    assert P_b[0] < P_b[1]
    assert P_a[0] > P_b[0]
    
def test_awe_1_to_1():
    """
    Text axiom weight estimation
    """
    ont = Ontology()
    assert isinstance(ont.nodes(), nx.classes.reportviews.NodeView)
    lexmap = LexicalMapEngine(config={'cardinality_weights': [
        {'prefix1':'X',
         'prefix2':'Y',
         'cardinality':'11',
         'weights':[-1.0, -1.0, 2.0, 0.0]
         }
        ]})
    
    ont.add_node('X:1', 'foo 1')
    ont.add_node('Y:1', 'foo 1')
    ont.add_node('Z:1a', 'foo 1')
    ont.add_node('Z:1b', 'foo 1')
    
    lexmap.index_ontology(ont)
    xg = lexmap.get_xref_graph()
    df = lexmap.as_dataframe(xg)
    print(df.to_csv(sep="\t"))
    P_XY = lexmap.weighted_axioms('X:1','Y:1', xg)
    P_XZ = lexmap.weighted_axioms('X:1','Z:1a', xg)
    logging.info('P_XY={} P_XZ={}'.format(P_XY, P_XZ))
    assert P_XY[2] > P_XZ[2]
    
def test_awe_match_pairs():
    """
    Text axiom weight estimation
    """
    ont = Ontology()
    assert isinstance(ont.nodes(), nx.classes.reportviews.NodeView)
    lexmap = LexicalMapEngine(config={'match_weights': [
        {'prefix1':'X',
         'prefix2':'Y',
         'weights':[1.0, -1.0, 2.0, 0.0]
         }
        ]})
    
    ont.add_node('X:1', 'foo 1')
    ont.add_node('Y:1', 'foo 1')
    
    lexmap.index_ontology(ont)
    xg = lexmap.get_xref_graph()
    df = lexmap.as_dataframe(xg)
    print(df.to_csv(sep="\t"))
    
    P_XY = lexmap.weighted_axioms('X:1','Y:1', xg)
    P_YX = lexmap.weighted_axioms('Y:1','X:1', xg)
    logging.info('P_XY={} P_YX={}'.format(P_XY, P_YX))
    assert P_XY[0] > P_XY[1]
    assert P_XY[0] == P_YX[1]
    
def test_awe_scope_map():
    """
    Text axiom weight estimation, syn scopes
    """
    ont = Ontology()
    assert isinstance(ont.nodes(), nx.classes.reportviews.NodeView)
    lexmap = LexicalMapEngine()    
    ont.add_node('X:1', 'x1')
    ont.add_node('Y:1', 'y1')
    ont.add_node('Z:1', 'z1')
    ont.add_synonym(Synonym('X:1', val='related', pred='hasRelatedSynonym'))
    ont.add_synonym(Synonym('Y:1', val='related', pred='hasRelatedSynonym'))
    
    ont.add_synonym(Synonym('Y:1', val='exact', pred='hasExactSynonym'))
    ont.add_synonym(Synonym('Z:1', val='exact', pred='hasExactSynonym'))
    
    lexmap.index_ontology(ont)
    xg = lexmap.get_xref_graph()
    df = lexmap.as_dataframe(xg)
    print(df.to_csv(sep="\t"))
    P_XY = lexmap.weighted_axioms('X:1','Y:1', xg)
    P_YZ = lexmap.weighted_axioms('Y:1','Z:1', xg)
    logging.info('P_XY={} P_XZ={}'.format(P_XY, P_YZ))
    assert P_XY[2] > P_XY[0]
    assert P_XY[2] > P_XY[1]
    assert P_XY[2] > P_XY[3]
    assert P_XY[2] < P_YZ[2]


def test_awe_xref_weights():
    """
    Text axiom weight estimation, when provided with defaults
    """
    ont = Ontology()
    assert isinstance(ont.nodes(), nx.classes.reportviews.NodeView)
    lexmap = LexicalMapEngine(config={'xref_weights':[
        {'left':'X:1',
         'right':'Y:1',
         'weights':[100.0, 0.0 ,0.0 ,0.0]},
        {'left':'Z:1',
         'right':'Y:1',
         'weights':[0.0, 100.0, 0.0, 0.0]},
        
    ]})    
    ont.add_node('X:1', 'foo')
    ont.add_node('Y:1', 'foo')
    ont.add_node('Z:1', 'foo')
    
    lexmap.index_ontology(ont)
    xg = lexmap.get_xref_graph()
    df = lexmap.as_dataframe(xg)
    print(df.to_csv(sep="\t"))
    P_XY = lexmap.weighted_axioms('X:1','Y:1', xg)
    P_YZ = lexmap.weighted_axioms('Y:1','Z:1', xg)
    logging.info('P_XY={} P_XZ={}'.format(P_XY, P_YZ))
    assert P_XY[0] > P_XY[1]
    assert P_XY[0] > P_XY[2]
    assert P_XY[0] > P_XY[3]
    assert P_YZ[0] > P_YZ[1]
    assert P_YZ[0] > P_YZ[2]
    assert P_YZ[0] > P_YZ[3]
    
