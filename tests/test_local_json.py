from ontobio.ontol_factory import OntologyFactory
import logging

PART_OF = 'BFO:0000050'

QUALITY = 'PATO:0000001'
PLOIDY = 'PATO:0001374'
EUPLOID = 'PATO:0001393'
SHAPE = 'PATO:0000052'
Y_SHAPED = 'PATO:0001201'

def test_local_json_parse():
    """
    Load ontology from JSON
    """
    factory = OntologyFactory()
    print("Creating ont")
    ont = factory.create('tests/resources/pato.json')

    ploidy = ont.node(PLOIDY)
    print("PLOIDY: {}".format(ploidy))
    assert ont.label(PLOIDY) == 'ploidy'

    # exact match
    search_results = ont.search('shape')
    print("SEARCH (exact): {}".format(search_results))
    assert [SHAPE] == search_results

    # implicit regexp
    search_results = ont.search('%shape%')
    print("SEARCH (re, implicit): {}".format(search_results))
    assert SHAPE in search_results
    assert len(search_results)>10

    # explicit regexp
    search_results = ont.search('.*shape.*', is_regex=True)
    print("SEARCH (re, explicit): {}".format(search_results))
    assert SHAPE in search_results
    assert len(search_results)>10
    
    num_nodes = 0
    for n in ont.nodes():
        num_nodes = num_nodes+1
    assert num_nodes > 100

NUCLEUS='GO:0005634'
INTRACELLULAR='GO:0005622'
INTRACELLULAR_PART='GO:0044424'
CELL = 'GO:0005623'
CELLULAR_COMPONENT = 'GO:0005575'
WIKIPEDIA_CELL = 'Wikipedia:Cell_(biology)'
NIF_CELL = 'NIF_Subcellular:sao1813327414'
CELL_PART = 'GO:0044464'

def test_graph():
    """
    Load ontology from JSON
    """
    factory = OntologyFactory()
    print("Creating ont")
    ont = factory.create('tests/resources/nucleus.json')

    icp = ont.node(INTRACELLULAR_PART)
    print("ICP: {}".format(icp))
    assert ont.label(INTRACELLULAR_PART) == 'intracellular part'

    graph = ont.get_graph()
    print("GRAPH: {}".format(graph.nodes))

    ancs = ont.ancestors(NUCLEUS)
    print("ANCS nucleus (all): {}".format(ancs))
    assert CELL in ancs
    assert CELLULAR_COMPONENT in ancs
    assert INTRACELLULAR in ancs
    assert NUCLEUS not in ancs
    
    ancs = ont.ancestors(INTRACELLULAR_PART)
    print("ANCS intracellular part(all): {}".format(ancs))
    assert CELL in ancs
    assert CELLULAR_COMPONENT in ancs
    assert NUCLEUS not in ancs
    
    ancs = ont.ancestors(INTRACELLULAR_PART, relations=['subClassOf'])
    print("ANCS intracellular part(subclass): {}".format(ancs))
    assert CELLULAR_COMPONENT in ancs
    assert CELL not in ancs
    assert NUCLEUS not in ancs

    # note: queries over *only* part_of are a non-use case, as we
    # typically always include subClassOf, due to how these chain
    # together according to OWL semantics
    ancs = ont.ancestors(INTRACELLULAR_PART, relations=[PART_OF])
    print("ANCS intracellular part(part_of): {}".format(ancs))
    assert INTRACELLULAR in ancs
    assert CELL not in ancs
    assert NUCLEUS not in ancs
    
    decs = ont.descendants(INTRACELLULAR_PART)
    print("DECS: {}".format(decs))
    assert NUCLEUS in decs
    assert CELL not in decs

    decs = ont.descendants(INTRACELLULAR, relations=[PART_OF])
    print("DECS: {}".format(decs))
    assert INTRACELLULAR_PART in decs
    assert NUCLEUS not in decs
    assert CELL not in decs

    xrefs = ont.xrefs(CELL)
    print("XREFS (from GO): {}".format(xrefs))
    assert WIKIPEDIA_CELL in xrefs
    assert NIF_CELL in xrefs
    assert len(xrefs) == 2

    
    # xrefs are bidirectional
    xrefs = ont.xrefs(WIKIPEDIA_CELL, bidirectional=True)
    print("XREFS (from WP, bidi): {}".format(xrefs))
    assert CELL in xrefs
    assert len(xrefs) == 1
    
    # xrefs queries unidirectional by default
    xrefs = ont.xrefs(WIKIPEDIA_CELL)
    print("XREFS (from WP): {}".format(xrefs))
    assert len(xrefs) == 0
    
    [ldef] = ont.logical_definitions(INTRACELLULAR_PART)
    print("LDEF: {}".format(ldef))
    assert ldef.genus_ids == [CELLULAR_COMPONENT]
    assert ldef.restrictions == [(PART_OF, INTRACELLULAR)]

    syns = ont.synonyms(CELL_PART, include_label=True)
    print("SYNS: {}".format(syns))
    [s1] = [x for x in syns if x.val == 'protoplast']
    assert s1.pred == 'hasRelatedSynonym'
    assert s1.xrefs == ['GOC:mah']

    GOSLIM = 'goslim_generic'
    subsets = ont.subsets(NUCLEUS)
    print("SUBSETS: {}".format(subsets))
    assert GOSLIM in subsets
    assert len(subsets) > 0

    in_slim = ont.extract_subset(GOSLIM)
    print("IN SLIM: {}".format(in_slim))
    assert len(in_slim) > 0
    assert NUCLEUS in in_slim
    
    #logging.basicConfig(level=logging.DEBUG)

    assert [] == ont.search('protoplast', synonyms=False)
    assert {CELL_PART,INTRACELLULAR} == set(ont.search('protoplast', synonyms=True))

    assert ont.has_node(CELL_PART)
    assert not ont.has_node('FOO:123')
    
def test_subontology():
    """
    Load extracting subontology
    """
    factory = OntologyFactory()
    print("Creating ont")
    ont = factory.create('tests/resources/go-truncated-pombase.json')
    print("ONT NODES: {}".format(ont.nodes()))
    subont = ont.subontology(relations=['subClassOf'])
    PERM = 'GO:1990578'
    print("NODES: {}".format(subont.nodes()))
    ancs = subont.ancestors(PERM)
    print(str(ancs))
    assert len(ancs) > 0
