from ontobio.ontol_factory import OntologyFactory
from ontobio.io.ontol_renderers import GraphRenderer
import logging


def test_write():
    """
    write obo from json
    """
    factory = OntologyFactory()
    print("Creating ont")
    ont = factory.create('tests/resources/nucleus.json')
    w = GraphRenderer.create('obo')
    w.write(ont)
    
