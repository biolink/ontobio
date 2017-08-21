from ontobio.ontol_factory import OntologyFactory
from ontobio.sparql.skos import Skos
from ontobio import GraphRenderer
import logging

def test_skos():
    """
    Load ontology from SKOS
    """
    prefixmap = {'LTER': 'http://vocab.lternet.edu?tema=', 'SKOS': 'http://www.w3.org/2004/02/skos/core#'}
    skos = Skos(prefixmap=prefixmap)

    
    fn = 'tests/resources/skos_example.rdf'
    ont = skos.process_file(fn, format='ttl')

    for n in ont.nodes():
        print('{}'.format(n))

    w = GraphRenderer.create('obo')
    w.write(ont)

