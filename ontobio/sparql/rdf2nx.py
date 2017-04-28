import rdflib
from rdflib import Namespace
from rdflib.namespace import RDF
from rdflib.namespace import RDFS
from rdflib.namespace import OWL
import networkx

from prefixcommons.curie_util import contract_uri
from ontobio.ontol import LogicalDefinition
from ontobio.ontol import Ontology
import ontobio.ontol

def id(uri):
    curies = contract_uri(uri)
    if len(curies) > 0:
        return curies[0]
    else:
        return uri

class RdfMapper():
    def __init__(self, rdfgraph=None):
        self.rdfgraph = rdfgraph

    def parse_rdf(self,filename=None, format='ttl'):
        self.rdfgraph = rdflib.Graph()
        self.rdfgraph.parse(filename, format=format)

    def convert(self, filename=None, format='ttl'):
        if filename is not None:
            self.parse_rdf(filename=filename, format=format)
        g = networkx.MultiDiGraph()
        ont = Ontology(graph=g)
        self.add_triples(ont)
        return ont
        
    def add_triples(self, ontol):
        """
        Adds triples to an ontology object
        """
        rg = self.rdfgraph
        g = ontol.get_graph()
        for (s,p,o) in rg.triples((None,None,None)):
            g.add_edge(id(o),id(s),predicate=id(p))
            
        
