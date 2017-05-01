import rdflib
from rdflib import Namespace
from rdflib.namespace import RDF
from rdflib.namespace import RDFS
from rdflib.namespace import OWL
from rdflib import URIRef
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
        return uri.toPython()

class RdfMapper():
    def __init__(self, rdfgraph=None, tbox_ontology=None):
        self.rdfgraph = rdfgraph
        self.tbox_ontology = tbox_ontology

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
        Adds triples to an ontology object.

        Currently assumes gocam/lego-style
        """
        rg = self.rdfgraph
        g = ontol.get_graph()
        typemap = {}
        inds = rg.subjects(RDF.type, OWL.NamedIndividual)
        for s in inds:
            for (s,p,o) in rg.triples((s,None,None)):
                s_id = id(s)
                p_id = id(p)
                g.add_node(s_id)
                if isinstance(o,URIRef):
                    o_id = id(o)
                    if p == RDF.type:
                        if o != OWL.NamedIndividual:
                            if s_id not in typemap:
                                typemap[s_id] = []
                            typemap[s_id].append(o_id)
                    else:
                        g.add_edge(o_id,s_id,pred=p_id)

        # propagate label from type
        for s in typemap.keys():
            g[s]['types'] = typemap[s]
            if self.tbox_ontology is not None:
                if 'label' not in g[s]:
                    g[s]['label'] = ";".join([self.tbox_ontology.label(x) for x in typemap[s] if self.tbox_ontology.label(x) is not None])
            
        
