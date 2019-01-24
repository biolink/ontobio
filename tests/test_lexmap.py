from ontobio.ontol_factory import OntologyFactory
from ontobio.lexmap import LexicalMapEngine
import logging

HAS_PART = 'BFO:0000051'
PART_OF = 'BFO:0000050'

QUALITY = 'PATO:0000001'
PLOIDY = 'PATO:0001374'
EUPLOID = 'PATO:0001393'
SHAPE = 'PATO:0000052'
Y_SHAPED = 'PATO:0001201'
PENTAPLOID = 'PATO:0001383'
SWOLLEN = 'PATO:0001851'
DILATED = 'PATO:0001571'
INCREASED_SIZE = 'PATO:0000586'
PROTRUDING = 'PATO:0001598'
MORPHOLOGY = 'PATO:0000051'
ABSENT = 'PATO:0000462'

def test_align():
    """
    Text lexical mapping
    """
    factory = OntologyFactory()
    print("Creating ont")
    ont1 = factory.create('ma')
    ont2 = factory.create('zfa')
    lexmap = LexicalMapEngine()

    lexmap.index_ontology(ont1)
    lexmap.index_ontology(ont2)

    print(lexmap.lmap)
    print(ont1.all_synonyms())
    print(ont2.all_synonyms())
    g = lexmap.get_xref_graph()
    for (x,y,d) in g.edges(data=True):
        print("{}<->{} :: {}".format(x,y,d))
    for x in g.nodes():
        print("{} --> {}".format(x,lexmap.grouped_mappings(x)))
